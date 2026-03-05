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
      :show-delete="true"
      :deleting-id="deletingId"
      @create="showCreateModal = true"
      @refresh="fetchProfiles"
      @delete="deleteProfile"
    />
    <ProfileCreateFlowModal
      :show="showCreateModal"
      @cancel="showCreateModal = false"
      @created="onProfileCreated"
    />
    <ConfirmDeleteModal
      :show="pendingDeleteId !== null"
      :target-id="pendingDeleteId || ''"
      :loading="deletingId !== null"
      @cancel="cancelDelete"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { ProfileSummary } from '@/api/types'
import { profiles as profilesApi } from '@/api/endpoints'
import ProfileCreateFlowModal from '@/components/ProfileCreateFlowModal.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'
import { useEntityListPage } from '@/composables/useEntityListPage'

const {
  loading,
  items: profilesList,
  errorMessage,
  deletingId,
  pendingDeleteId,
  fetchItems: fetchProfiles,
  requestDelete: deleteProfile,
  cancelDelete,
  confirmDelete,
} = useEntityListPage<ProfileSummary>({
  list: () => profilesApi.list(),
  remove: (id) => profilesApi.remove(id),
  getId: (profile) => profile.id,
})
const showCreateModal = ref(false)
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

onMounted(fetchProfiles)

function onProfileCreated() {
  showCreateModal.value = false
  fetchProfiles()
}

</script>
