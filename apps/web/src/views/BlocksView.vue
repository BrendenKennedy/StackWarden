<template>
  <div>
    <PageEntityTable
      title="Blocks"
      create-label="Create New Block"
      :loading="loading"
      loading-message="Loading blocks..."
      empty-message="No blocks yet."
      :error-message="errorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/blocks"
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
      entity="blocks"
      :id="specModalId"
      @close="closeSpecModal"
      @edit="openEditFromView"
    />
    <SpecEditModal
      :show="showEditModal"
      entity="blocks"
      :id="editModalId"
      @close="closeEditModal"
      @saved="onEditSaved"
    />
    <BlockCreateFlowModal
      :show="showCreateModal"
      @cancel="closeCreateModal"
      @created="onBlockCreated"
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
import type { BlockSummary } from '@/api/types'
import { blocks as blocksApi } from '@/api/endpoints'
import BlockCreateFlowModal from '@/components/BlockCreateFlowModal.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'
import SpecDetailModal from '@/components/SpecDetailModal.vue'
import SpecEditModal from '@/components/SpecEditModal.vue'
import { useEntityListPageWithModals } from '@/composables/useEntityListPageWithModals'

const {
  loading,
  items: blocksList,
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
} = useEntityListPageWithModals<BlockSummary>({
  entity: 'blocks',
  list: () => blocksApi.list(),
  remove: (id) => blocksApi.remove(id),
  getId: (block) => block.id,
})

const tableColumns = [
  { key: 'id', label: 'ID' },
  { key: 'display_name', label: 'Display Name' },
  { key: 'source', label: 'Source' },
  { key: 'tags', label: 'Tags' },
]
const tableRows = computed(() =>
  blocksList.value.map((b) => ({
    id: b.id,
    display_name: b.display_name,
    source: b.source === 'remote'
      ? `remote${b.source_repo_owner ? ` (${b.source_repo_owner})` : ''}`
      : (b.source || 'local'),
    tags: b.tags.join(', '),
  })),
)

onMounted(fetchItems)

function onBlockCreated() {
  closeCreateModal()
  fetchItems()
}
</script>
