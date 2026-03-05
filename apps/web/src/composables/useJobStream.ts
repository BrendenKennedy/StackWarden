import { ref, onUnmounted, watch, type Ref } from 'vue'
import { toUserErrorMessage } from '@/utils/errors'

export interface LogLine {
  ts: string
  line: string
}

function safeParse(raw: string): unknown | null {
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function streamHeaders(): HeadersInit | undefined {
  const token = localStorage.getItem('stackwarden_token')
  if (!token) return undefined
  return { Authorization: `Bearer ${token}` }
}

export function useJobStream(jobIdRef: Ref<string> | string) {
  const lines = ref<LogLine[]>([])
  const status = ref<string>('connecting')
  const result = ref<{ artifact_id: string; tag: string } | null>(null)
  const error = ref<string | null>(null)
  const connected = ref(false)

  let streamAbort: AbortController | null = null
  let streamToken = 0

  function applyEvent(eventType: string, rawData: string) {
    if (!rawData) return
    const data = safeParse(rawData) as { ts: string; payload: string } | { payload: string } | null
    if (!data || typeof data !== 'object' || !('payload' in data)) return

    if (eventType === 'log') {
      const logData = data as { ts: string; payload: string }
      lines.value.push({ ts: logData.ts, line: logData.payload })
      return
    }
    if (eventType === 'status') {
      status.value = String(data.payload)
      return
    }
    if (eventType === 'progress') {
      const progressData = data as { ts: string; payload: string }
      if (progressData.payload !== 'keepalive') {
        lines.value.push({ ts: progressData.ts, line: `[progress] ${progressData.payload}` })
      }
      return
    }
    if (eventType === 'result') {
      const inner = safeParse(String(data.payload)) as { artifact_id: string; tag: string } | null
      result.value = inner ?? { artifact_id: '', tag: String(data.payload) }
      return
    }
    if (eventType === 'error') {
      const inner = safeParse(String(data.payload)) as { message?: string } | null
      error.value = inner?.message || String(data.payload)
    }
  }

  async function streamEvents(jobId: string, token: number, controller: AbortController) {
    const res = await fetch(`/api/jobs/${jobId}/events`, {
      method: 'GET',
      headers: streamHeaders(),
      signal: controller.signal,
    })
    if (!res.ok) {
      throw new Error(`Failed to stream logs: ${res.status} ${res.statusText}`)
    }
    if (!res.body) {
      throw new Error('Streaming unavailable: response body is empty')
    }
    if (token !== streamToken) return

    connected.value = true
    status.value = 'connected'

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let eventType = 'message'
    let dataLines: string[] = []

    const flushEvent = () => {
      if (dataLines.length === 0) return
      applyEvent(eventType, dataLines.join('\n'))
      eventType = 'message'
      dataLines = []
    }

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      if (token !== streamToken) return
      buffer += decoder.decode(value, { stream: true })
      const linesBuffer = buffer.split('\n')
      buffer = linesBuffer.pop() ?? ''

      for (const rawLine of linesBuffer) {
        const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
        if (line === '') {
          flushEvent()
          continue
        }
        if (line.startsWith(':')) continue

        const separatorIdx = line.indexOf(':')
        const field = separatorIdx === -1 ? line : line.slice(0, separatorIdx)
        const valuePart = separatorIdx === -1 ? '' : line.slice(separatorIdx + 1).replace(/^ /, '')

        if (field === 'event') {
          eventType = valuePart || 'message'
        } else if (field === 'data') {
          dataLines.push(valuePart)
        }
      }
    }

    buffer += decoder.decode()
    if (buffer.trim().length > 0 && !buffer.includes('\n')) {
      const separatorIdx = buffer.indexOf(':')
      const field = separatorIdx === -1 ? buffer : buffer.slice(0, separatorIdx)
      const valuePart = separatorIdx === -1 ? '' : buffer.slice(separatorIdx + 1).replace(/^ /, '')
      if (field === 'event') eventType = valuePart || 'message'
      if (field === 'data') dataLines.push(valuePart)
    }
    flushEvent()
  }

  function connect(jobId: string) {
    if (!jobId) return
    disconnect()
    lines.value = []
    status.value = 'connecting'
    result.value = null
    error.value = null

    streamToken += 1
    const token = streamToken
    const controller = new AbortController()
    streamAbort = controller
    void streamEvents(jobId, token, controller).catch((err: unknown) => {
      if (token !== streamToken || controller.signal.aborted) return
      connected.value = false
      if (status.value !== 'succeeded' && status.value !== 'failed' && status.value !== 'canceled') {
        error.value = toUserErrorMessage(err)
      }
    })
  }

  function disconnect() {
    streamAbort?.abort()
    streamAbort = null
    streamToken += 1
    connected.value = false
  }

  function reconnect(jobId: string) {
    connect(jobId)
  }

  if (typeof jobIdRef === 'string') {
    if (jobIdRef) {
      connect(jobIdRef)
    }
  } else {
    watch(
      () => jobIdRef.value,
      (jobId) => {
        if (jobId) {
          connect(jobId)
        } else {
          disconnect()
        }
      },
      { immediate: true },
    )
  }
  onUnmounted(disconnect)

  return { lines, status, result, error, connected, disconnect, reconnect }
}
