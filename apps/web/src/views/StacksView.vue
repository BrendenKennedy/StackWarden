<template>
  <div>
    <PageEntityTable
      title="Stacks"
      create-label="Create New Stack"
      :loading="loading"
      loading-message="Loading stacks..."
      empty-message="No stacks yet."
      :error-message="errorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/stacks"
      :show-delete="true"
      :deleting-id="deletingId"
      @create="openCreateModal"
      @refresh="fetchStacks"
      @delete="requestDelete"
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
      entity-label="stack"
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
import { useEntityListPage } from '@/composables/useEntityListPage'
import { useQueryModal } from '@/composables/useQueryModal'

const {
  loading,
  items: stacksList,
  errorMessage,
  deletingId,
  pendingDeleteId,
  fetchItems: fetchStacks,
  requestDelete,
  cancelDelete,
  confirmDelete,
} = useEntityListPage<StackSummary>({
  list: () => stacksApi.list(),
  remove: (id) => stacksApi.remove(id),
  getId: (stack) => stack.id,
})
const { isOpen: showCreateModal, open: openCreateModal, close: closeCreateModal } = useQueryModal('create')
const tableColumns = [
  { key: 'id', label: 'ID' },
  { key: 'display_name', label: 'Display Name' },
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
    variants_count: Object.keys(s.variants || {}).length,
  })),
)

onMounted(fetchStacks)

function onStackCreated() {
  closeCreateModal()
  fetchStacks()
}
</script>
