import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}

const toasts = ref<Toast[]>([])
let nextId = 0
const timerIds = new Map<number, ReturnType<typeof setTimeout>>()

export function useToast() {
  function showToast(message: string, type: Toast['type'] = 'info', durationMs = 4000) {
    const id = nextId++
    toasts.value.push({ id, message, type })
    const timerId = setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
      timerIds.delete(id)
    }, durationMs)
    timerIds.set(id, timerId)
  }

  function dismissToast(id: number) {
    const timerId = timerIds.get(id)
    if (timerId !== undefined) {
      clearTimeout(timerId)
      timerIds.delete(id)
    }
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  return { toasts, showToast, dismissToast }
}
