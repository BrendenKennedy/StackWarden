import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { useJobStream } from '../src/composables/useJobStream'

describe('useJobStream', () => {
  it('connects to SSE endpoint with auth and processes status/result events', async () => {
    const chunks = [
      'event: status\n',
      'data: {"payload":"running"}\n\n',
      'event: result\n',
      'data: {"payload":"{\\"artifact_id\\":\\"art1\\",\\"tag\\":\\"tag1\\"}"}\n\n',
    ]
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      body: stream,
    })
    vi.stubGlobal('fetch', fetchMock)
    localStorage.setItem('stackwarden_token', 'abc123')

    const Comp = defineComponent({
      setup() {
        return useJobStream('job-123')
      },
      template: '<div />',
    })

    const wrapper = mount(Comp)
    await Promise.resolve()
    await Promise.resolve()
    await nextTick()

    expect(fetchMock).toHaveBeenCalledWith('/api/jobs/job-123/events', expect.objectContaining({
      method: 'GET',
      headers: { Authorization: 'Bearer abc123' },
    }))

    await vi.waitFor(() => {
      expect((wrapper.vm as any).connected).toBe(true)
      expect((wrapper.vm as any).status).toBe('running')
      expect((wrapper.vm as any).result).toEqual({ artifact_id: 'art1', tag: 'tag1' })
    })
    localStorage.removeItem('stackwarden_token')
  })
})
