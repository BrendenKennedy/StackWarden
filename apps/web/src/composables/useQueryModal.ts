import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useQueryModal(flag = 'create') {
  const route = useRoute()
  const router = useRouter()
  const isOpen = ref(false)

  watch(
    () => route.query[flag],
    (value) => {
      isOpen.value = String(value || '') === '1'
    },
    { immediate: true },
  )

  function open() {
    router.replace({ path: route.path, query: { ...route.query, [flag]: '1' } })
  }

  function close() {
    const nextQuery = { ...route.query }
    delete nextQuery[flag]
    router.replace({ path: route.path, query: nextQuery })
  }

  return {
    isOpen,
    open,
    close,
  }
}
