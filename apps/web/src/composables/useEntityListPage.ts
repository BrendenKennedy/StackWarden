import { ref } from 'vue'
import type { Ref } from 'vue'
import { toUserErrorMessage } from '@/utils/errors'

type UseEntityListPageOptions<T> = {
  list: () => Promise<T[]>
  remove?: (id: string) => Promise<unknown>
  getId: (item: T) => string
}

export function useEntityListPage<T>(options: UseEntityListPageOptions<T>) {
  const loading = ref(true)
  const items = ref([]) as Ref<T[]>
  const errorMessage = ref<string | null>(null)
  const deletingId = ref<string | null>(null)
  const pendingDeleteId = ref<string | null>(null)

  async function fetchItems() {
    loading.value = true
    errorMessage.value = null
    try {
      items.value = await options.list()
    } catch (err) {
      items.value = []
      errorMessage.value = toUserErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  function requestDelete(id: string) {
    pendingDeleteId.value = id
  }

  function cancelDelete() {
    if (deletingId.value) return
    pendingDeleteId.value = null
  }

  async function confirmDelete() {
    if (!options.remove || !pendingDeleteId.value) return
    const id = pendingDeleteId.value
    deletingId.value = id
    errorMessage.value = null
    try {
      await options.remove(id)
      items.value = items.value.filter((item) => options.getId(item) !== id)
    } catch (err) {
      errorMessage.value = toUserErrorMessage(err)
    } finally {
      deletingId.value = null
      pendingDeleteId.value = null
    }
  }

  return {
    loading,
    items,
    errorMessage,
    deletingId,
    pendingDeleteId,
    fetchItems,
    requestDelete,
    cancelDelete,
    confirmDelete,
  }
}
