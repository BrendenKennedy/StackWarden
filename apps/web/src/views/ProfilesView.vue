<template>
  <div>
    <PageEntityTable
      title="Profiles"
      create-label="Create New Profile"
      :loading="loading"
      loading-message="Loading profiles..."
      empty-message="No profiles yet."
      :error-message="errorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/profiles"
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
      entity="profiles"
      :id="specModalId"
      @close="closeSpecModal"
      @edit="openEditFromView"
    />
    <SpecEditModal
      :show="showEditModal"
      entity="profiles"
      :id="editModalId"
      @close="closeEditModal"
      @saved="onEditSaved"
    />
    <ProfileCreateFlowModal
      :show="showCreateModal"
      @cancel="closeCreateModal"
      @created="onProfileCreated"
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
import type { ProfileSummary } from '@/api/types'
import { profiles as profilesApi } from '@/api/endpoints'
import ProfileCreateFlowModal from '@/components/ProfileCreateFlowModal.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'
import SpecDetailModal from '@/components/SpecDetailModal.vue'
import SpecEditModal from '@/components/SpecEditModal.vue'
import { useEntityListPageWithModals } from '@/composables/useEntityListPageWithModals'

const {
  loading,
  items: profilesList,
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
} = useEntityListPageWithModals<ProfileSummary>({
  entity: 'profiles',
  list: () => profilesApi.list(),
  remove: (id) => profilesApi.remove(id),
  getId: (profile) => profile.id,
})

const tableColumns = [
  { key: 'id', label: 'ID' },
  { key: 'display_name', label: 'Display Name' },
  { key: 'source', label: 'Source' },
  { key: 'arch', label: 'Arch' },
  { key: 'os', label: 'OS' },
  { key: 'cuda', label: 'CUDA' },
  { key: 'gpu', label: 'GPU' },
]
const tableRows = computed(() =>
  profilesList.value.map((p) => ({
    id: p.id,
    display_name: p.display_name,
    source: p.source === 'remote'
      ? `remote${p.source_repo_owner ? ` (${p.source_repo_owner})` : ''}`
      : (p.source || 'local'),
    arch: p.arch,
    os: p.os,
    cuda: p.cuda ? `${p.cuda.major}.${p.cuda.minor}` : 'n/a',
    gpu: `${p.gpu.vendor}/${p.gpu.family}`,
  })),
)

onMounted(fetchItems)

function onProfileCreated() {
  closeCreateModal()
  fetchItems()
}
</script>
