import { nextTick, onUnmounted, type Ref, watch } from 'vue'

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export function useModalFocusTrap(
  dialogRef: Ref<HTMLElement | null>,
  show: Ref<boolean> | (() => boolean),
  onClose: () => void,
) {
  function focusFirst() {
    const root = dialogRef.value
    if (!root) return
    const el = root.querySelector<HTMLElement>('input, select, button, textarea')
    el?.focus()
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
      return
    }
    if (e.key !== 'Tab') return
    const root = dialogRef.value
    if (!root) return
    const focusables = Array.from(
      root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter(el => !el.hasAttribute('disabled'))
    if (!focusables.length) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  const showGetter = typeof show === 'function' ? show : () => show.value

  const stopWatch = watch(
    showGetter,
    async (open) => {
      if (open) {
        await nextTick()
        focusFirst()
      }
    },
    { immediate: true },
  )

  onUnmounted(stopWatch)

  return { focusFirst, onKeydown }
}
