<template>
  <div>
    <PageEntityTable
      title="Stacks"
      title-icon="stacks"
      create-label="Create New Stack"
      :loading="loading"
      loading-message="Loading stacks..."
      empty-message="No stacks yet."
      :error-message="errorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/stacks"
      id-key="id"
      :on-view="handleView"
      :on-edit="handleEdit"
      :show-delete="true"
      :deleting-id="deletingId"
      @create="openCreateModal"
      @refresh="fetchItems"
      @delete="requestDelete"
    />
    <SpecDetailModal
      :show="showSpecModal"
      entity="stacks"
      :id="specModalId"
      @close="closeSpecModal"
      @edit="openEditFromView"
    />
    <SpecEditModal
      :show="showEditModal"
      entity="stacks"
      :id="editModalId"
      @close="closeEditModal"
      @saved="onEditSaved"
    />
    <StackCreateFlowModal
      :show="showCreateModal"
      @cancel="closeCreateModal"
      @created="onStackCreated"
    />
    <ConfirmDeleteModal
      :show="pendingDeleteId !== null"
      :target-id="pendingDeleteId || ''"
      :loading="deletingId !== null"
      :entity-label="entityLabel"
      @cancel="cancelDelete"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { StackSummary } from '@/api/types'
import { stacks as stacksApi } from '@/api/endpoints'
import StackCreateFlowModal from '@/components/StackCreateFlowModal.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'
import SpecDetailModal from '@/components/SpecDetailModal.vue'
import SpecEditModal from '@/components/SpecEditModal.vue'
import { useEntityListPageWithModals } from '@/composables/useEntityListPageWithModals'

const {
  loading,
  items: stacksList,
  errorMessage,
  deletingId,
  pendingDeleteId,
  fetchItems,
  requestDelete,
  cancelDelete,
  confirmDelete,
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
} = useEntityListPageWithModals<StackSummary>({
  entity: 'stacks',
  list: () => stacksApi.list(),
  remove: (id) => stacksApi.remove(id),
  getId: (stack) => stack.id,
})

const tableColumns = [
  { key: 'id', label: 'ID' },
  { key: 'display_name', label: 'Display Name' },
  { key: 'certification', label: 'Certification', badge: true },
  { key: 'source', label: 'Source' },
  { key: 'variants_count', label: 'Variants' },
]
const tableRows = computed(() =>
  stacksList.value.map((s) => ({
    id: s.id,
    display_name: s.display_name,
    source: s.source === 'remote'
      ? `remote${s.source_repo_owner ? ` (${s.source_repo_owner})` : ''}`
      : (s.source || 'local'),
    certification: s.certification === 'dgx_certified' ? 'dgx_certified' : 'generic_best_effort',
    variants_count: Object.keys(s.variants || {}).length,
  })),
)

onMounted(fetchItems)

function onStackCreated() {
  closeCreateModal()
  fetchItems()
}
</script>
