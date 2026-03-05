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
      :show-delete="true"
      :deleting-id="deletingId"
      @create="openCreateModal"
      @refresh="fetchBlocks"
      @delete="requestDelete"
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
      entity-label="block"
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
import { useEntityListPage } from '@/composables/useEntityListPage'
import { useQueryModal } from '@/composables/useQueryModal'

const {
  loading,
  items: blocksList,
  errorMessage,
  deletingId,
  pendingDeleteId,
  fetchItems: fetchBlocks,
  requestDelete,
  cancelDelete,
  confirmDelete,
} = useEntityListPage<BlockSummary>({
  list: () => blocksApi.list(),
  remove: (id) => blocksApi.remove(id),
  getId: (block) => block.id,
})
const { isOpen: showCreateModal, open: openCreateModal, close: closeCreateModal } = useQueryModal('create')

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

onMounted(fetchBlocks)

function onBlockCreated() {
  closeCreateModal()
  fetchBlocks()
}
</script>
