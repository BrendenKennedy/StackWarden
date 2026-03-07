<template>
  <div>
    <PageEntityTable
      title="Layers"
      title-icon="layers"
      create-label="Create New Layer"
      :loading="loading"
      loading-message="Loading layers..."
      empty-message="No layers yet."
      :error-message="errorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/layers"
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
      entity="layers"
      :id="specModalId"
      @close="closeSpecModal"
      @edit="openEditFromView"
    />
    <SpecEditModal
      :show="showEditModal"
      entity="layers"
      :id="editModalId"
      @close="closeEditModal"
      @saved="onEditSaved"
    />
    <LayerCreateFlowModal
      :show="showCreateModal"
      @cancel="closeCreateModal"
      @created="onLayerCreated"
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
import type { LayerSummary } from '@/api/types'
import { layers as layersApi } from '@/api/endpoints'
import LayerCreateFlowModal from '@/components/LayerCreateFlowModal.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'
import SpecDetailModal from '@/components/SpecDetailModal.vue'
import SpecEditModal from '@/components/SpecEditModal.vue'
import { useEntityListPageWithModals } from '@/composables/useEntityListPageWithModals'

const {
  loading,
  items: layersList,
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
} = useEntityListPageWithModals<LayerSummary>({
  entity: 'layers',
  list: () => layersApi.list(),
  remove: (id) => layersApi.remove(id),
  getId: (layer) => layer.id,
})

const tableColumns = [
  { key: 'id', label: 'ID' },
  { key: 'display_name', label: 'Display Name' },
  { key: 'source', label: 'Source' },
  { key: 'tags', label: 'Tags' },
]
const tableRows = computed(() =>
  layersList.value.map((layer) => ({
    id: layer.id,
    display_name: layer.display_name,
    source: layer.source === 'remote'
      ? `remote${layer.source_repo_owner ? ` (${layer.source_repo_owner})` : ''}`
      : (layer.source || 'local'),
    tags: layer.tags.join(', '),
  })),
)

onMounted(fetchItems)

function onLayerCreated() {
  closeCreateModal()
  fetchItems()
}
</script>
