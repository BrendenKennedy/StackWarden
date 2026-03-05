import { ref } from 'vue'
import type { Ref } from 'vue'
import { useEntityListPage } from '@/composables/useEntityListPage'
import { useQueryModal } from '@/composables/useQueryModal'

type EntityType = 'profiles' | 'stacks' | 'blocks'

type UseEntityListPageWithModalsOptions<T> = {
  entity: EntityType
  list: () => Promise<T[]>
  remove: (id: string) => Promise<unknown>
  getId: (item: T) => string
}

export function useEntityListPageWithModals<T>(
  options: UseEntityListPageWithModalsOptions<T>,
) {
  const listPage = useEntityListPage<T>({
    list: options.list,
    remove: options.remove,
    getId: options.getId,
  })

  const { isOpen: showCreateModal, open: openCreateModal, close: closeCreateModal } =
    useQueryModal('create')

  const showSpecModal = ref(false)
  const specModalId = ref<string | null>(null)
  const showEditModal = ref(false)
  const editModalId = ref<string | null>(null)

  const entityLabel = options.entity.slice(0, -1) as 'profile' | 'stack' | 'block'

  function handleView(row: Record<string, string | number | null | undefined>) {
    const id = row.id
    if (id) {
      specModalId.value = String(id)
      showSpecModal.value = true
    }
  }

  function handleEdit(row: Record<string, string | number | null | undefined>) {
    const id = row.id
    if (id) {
      editModalId.value = String(id)
      showEditModal.value = true
    }
  }

  function openEditFromView() {
    const id = specModalId.value
    if (id) {
      showSpecModal.value = false
      specModalId.value = null
      editModalId.value = id
      showEditModal.value = true
    }
  }

  function closeSpecModal() {
    showSpecModal.value = false
    specModalId.value = null
  }

  function closeEditModal() {
    showEditModal.value = false
    editModalId.value = null
  }

  function onEditSaved() {
    listPage.fetchItems()
  }

  return {
    ...listPage,
    showCreateModal,
    openCreateModal,
    closeCreateModal,
    showSpecModal,
    specModalId,
    showEditModal,
    editModalId,
    entityLabel,
    handleView,
    handleEdit,
    openEditFromView,
    closeSpecModal,
    closeEditModal,
    onEditSaved,
  }
}
