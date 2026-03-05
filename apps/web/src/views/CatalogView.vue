<template>
  <div>
    <PageEntityTable
      title="Catalog"
      title-icon="catalog"
      create-label="Create Build"
      :loading="loading"
      loading-message="Loading catalog items..."
      empty-message="No catalog items yet."
      :error-message="tableErrorMessage"
      :rows="tableRows"
      :columns="tableColumns"
      route-base="/catalog"
      id-key="row_id"
      view-path-key="view_path"
      :on-view="handleView"
      :show-edit="false"
      :show-delete="true"
      :deletable="(row) => !!row.artifact_id"
      :deleting-id="deletingId"
      :show-retry="true"
      :retryable="(row) => row.status === 'failed' && !!row.job_id"
      retry-id-key="job_id"
      :retrying-id="retryingId"
      @create="openBuildModal"
      @refresh="fetchItems"
      @delete="deleteCatalogItem"
      @retry="retryCatalogJob"
    />

    <ArtifactDetailModal
      :show="showArtifactModal"
      :artifact-id="artifactModalId"
      @close="closeArtifactModal"
      @deleted="fetchItems"
    />

    <Teleport to="body">
    <div v-if="showBuild" class="build-modal-overlay" @click.self="showBuild = false" @keydown="onKeydown">
      <div ref="buildDialogRef" class="build-modal card" role="dialog" aria-modal="true" aria-labelledby="catalog-build-title">
        <div class="build-modal-header">
          <h3 id="catalog-build-title">Catalog Build</h3>
          <button class="btn" @click="showBuild = false">Close</button>
        </div>
        <p class="build-help">
          Choose a runtime profile and stack recipe. This is the final resolve/build step.
        </p>
        <div class="build-form-fields">
          <div class="form-group">
            <label>Build Profile</label>
            <select v-model="buildProfileId">
              <option value="">Select profile</option>
              <option v-for="p in profilesList" :key="p.id" :value="p.id">{{ p.display_name }} ({{ p.id }})</option>
            </select>
          </div>
          <div class="form-group">
            <label>Stack</label>
            <select v-model="buildStackId">
              <option value="">Select stack</option>
              <option v-for="s in stacksList" :key="s.id" :value="s.id">{{ s.display_name }} ({{ s.id }})</option>
            </select>
          </div>
        </div>
        <div class="catalog-actions">
          <button class="btn btn-primary" :disabled="!canBuild || startingBuild" @click="startBuild">
            {{ startingBuild ? 'Starting...' : 'Start Build' }}
          </button>
        </div>
        <div v-if="compatibilityErrors.length" class="catalog-message catalog-error">
          <div v-for="(e, idx) in compatibilityErrors" :key="idx">{{ e }}</div>
        </div>
        <div v-if="compatibilityWarnings.length" class="catalog-message catalog-warning">
          <div v-for="(w, idx) in compatibilityWarnings" :key="`w-${idx}`">{{ w }}</div>
        </div>
        <div v-if="compatibilityInfo.length" class="catalog-message catalog-info">
          <div v-for="(i, idx) in compatibilityInfo" :key="`i-${idx}`">{{ i }}</div>
        </div>
        <div v-if="compatibilitySuggestedFixes.length" class="catalog-section">
          <div class="catalog-section-title">Suggested fixes</div>
          <ul class="catalog-fix-list">
            <li v-for="(f, idx) in compatibilitySuggestedFixes" :key="`f-${idx}`" class="catalog-fix-item">{{ f }}</li>
          </ul>
        </div>
        <details v-if="compatibilityDecisionTrace.length" class="catalog-section">
          <summary class="catalog-summary">Why this was chosen</summary>
          <div class="catalog-trace">
            <div v-for="(line, idx) in compatibilityDecisionTrace" :key="`t-${idx}`">{{ line }}</div>
          </div>
        </details>
        <details v-if="Object.keys(tupleDecision).length" class="catalog-section">
          <summary class="catalog-summary">Tuple Decision</summary>
          <pre class="json-viewer catalog-json">{{ JSON.stringify(tupleDecision, null, 2) }}</pre>
        </details>
        <div v-if="modalError" class="catalog-message catalog-error">{{ modalError }}</div>
      </div>
    </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { CatalogItem, ProfileSummary, StackSummary } from '@/api/types'
import {
  artifacts as artifactsApi,
  catalog as catalogApi,
  compatibility as compatibilityApi,
  jobs as jobsApi,
  profiles as profilesApi,
  stacks as stacksApi,
  system as systemApi,
} from '@/api/endpoints'
import { toUserErrorMessage } from '@/utils/errors'
import PageEntityTable from '@/components/PageEntityTable.vue'
import ArtifactDetailModal from '@/components/ArtifactDetailModal.vue'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const router = useRouter()

const items = ref<CatalogItem[]>([])
const loading = ref(true)
const showBuild = ref(false)
const showArtifactModal = ref(false)
const artifactModalId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const retryingId = ref<string | null>(null)
const profilesList = ref<ProfileSummary[]>([])
const stacksList = ref<StackSummary[]>([])
const defaultProfileId = ref('')
const buildProfileId = ref('')
const buildStackId = ref('')
const startingBuild = ref(false)
const tableError = ref('')
const rowActionError = ref('')
const modalError = ref('')
const compatibilityErrors = ref<string[]>([])
const compatibilityWarnings = ref<string[]>([])
const compatibilityInfo = ref<string[]>([])
const compatibilitySuggestedFixes = ref<string[]>([])
const compatibilityDecisionTrace = ref<string[]>([])
const tupleDecision = ref<Record<string, any>>({})
const buildDialogRef = ref<HTMLElement | null>(null)
const { onKeydown } = useModalFocusTrap(buildDialogRef, showBuild, () => { showBuild.value = false })

const canBuild = computed(() =>
  buildProfileId.value !== '' &&
  buildStackId.value !== '' &&
  compatibilityErrors.value.length === 0
)
const tableErrorMessage = computed(() => rowActionError.value || tableError.value)
const tableColumns = [
  { key: 'profile_id', label: 'Profile', width: '145px' },
  { key: 'stack_id', label: 'Stack', width: '145px' },
  { key: 'tag', label: 'Tag' },
  { key: 'created', label: 'Created', multiline: true },
  { key: 'status', label: 'Status', badge: true },
]
const tableRows = computed(() =>
  items.value.map((i) => ({
    row_id: i.row_id,
    status: i.status,
    source: i.source,
    profile_id: i.profile_id,
    stack_id: i.stack_id,
    tag: i.tag || '-',
    created: formatDate(i.created_at),
    artifact_id: i.artifact_id,
    job_id: i.job_id,
    view_path: i.artifact_id
      ? `/artifacts/${i.artifact_id}`
      : (i.job_id ? `/jobs/${i.job_id}` : ''),
  })),
)

async function fetchItems() {
  loading.value = true
  try {
    const rows = await catalogApi.items({})
    items.value = rows
    tableError.value = ''
    rowActionError.value = ''
  } catch (e: unknown) {
    tableError.value = toUserErrorMessage(e)
  } finally {
    loading.value = false
  }
}

async function deleteCatalogItem(rowId: string) {
  const row = items.value.find((item) => item.row_id === rowId)
  if (!row) return
  if (!row.artifact_id) {
    rowActionError.value = 'Cannot delete: no artifact to remove.'
    return
  }
  deletingId.value = rowId
  rowActionError.value = ''
  try {
    await artifactsApi.remove(row.artifact_id)
    await fetchItems()
  } catch (e: unknown) {
    rowActionError.value = toUserErrorMessage(e)
  } finally {
    deletingId.value = null
  }
}

function handleView(row: Record<string, string | number | null | undefined>) {
  const artifactId = row.artifact_id
  const jobId = row.job_id
  if (artifactId) {
    artifactModalId.value = String(artifactId)
    showArtifactModal.value = true
  } else if (jobId) {
    router.push({ name: 'job-detail', params: { id: String(jobId) } })
  }
}

function closeArtifactModal() {
  showArtifactModal.value = false
  artifactModalId.value = null
}

async function retryCatalogJob(jobId: string) {
  if (!jobId) return
  retryingId.value = jobId
  rowActionError.value = ''
  try {
    await jobsApi.retry(jobId)
    await fetchItems()
  } catch (e: unknown) {
    rowActionError.value = toUserErrorMessage(e)
  } finally {
    retryingId.value = null
  }
}

async function loadBuildInputs() {
  try {
    const [profiles, stacks, cfg] = await Promise.all([
      profilesApi.list(),
      stacksApi.list(),
      systemApi.config().catch(() => null),
    ])
    profilesList.value = profiles
    stacksList.value = stacks
    defaultProfileId.value = cfg?.default_profile || ''
    if (!buildProfileId.value && defaultProfileId.value && profilesList.value.some((p) => p.id === defaultProfileId.value)) {
      buildProfileId.value = defaultProfileId.value
    }
  } catch {
    // best-effort
  }
}

function openBuildModal() {
  showBuild.value = true
  modalError.value = ''
  if (defaultProfileId.value && profilesList.value.some((p) => p.id === defaultProfileId.value)) {
    buildProfileId.value = defaultProfileId.value
  }
}

async function startBuild() {
  if (!canBuild.value) return
  startingBuild.value = true
  modalError.value = ''
  try {
    await jobsApi.ensure({
      profile_id: buildProfileId.value,
      stack_id: buildStackId.value,
      flags: {},
    })
    showBuild.value = false
    await fetchItems()
  } catch (e: unknown) {
    modalError.value = toUserErrorMessage(e)
  } finally {
    startingBuild.value = false
  }
}

async function refreshCompatibility() {
  compatibilityErrors.value = []
  compatibilityWarnings.value = []
  compatibilityInfo.value = []
  compatibilitySuggestedFixes.value = []
  compatibilityDecisionTrace.value = []
  tupleDecision.value = {}
  if (!buildProfileId.value || !buildStackId.value) return
  try {
    const report = await compatibilityApi.preview({
      profile_id: buildProfileId.value,
      stack_id: buildStackId.value,
    })
    compatibilityErrors.value = report.errors.map(e => `${e.code}: ${e.message}`)
    compatibilityWarnings.value = report.warnings.map(w => `${w.code}: ${w.message}`)
    compatibilityInfo.value = report.info.map(i => `${i.code}: ${i.message}`)
    compatibilitySuggestedFixes.value = report.suggested_fixes || []
    compatibilityDecisionTrace.value = report.decision_trace || []
    tupleDecision.value = report.tuple_decision || {}
  } catch (e: unknown) {
    compatibilityErrors.value = [toUserErrorMessage(e)]
    compatibilityWarnings.value = []
    compatibilityInfo.value = []
    compatibilitySuggestedFixes.value = []
    compatibilityDecisionTrace.value = []
    tupleDecision.value = {}
  }
}

function formatDate(iso: string) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const [ymd, hms] = date.toISOString().replace('.000Z', '').split('T')
  return `${ymd}\n${hms} UTC`
}

onMounted(async () => {
  await Promise.all([fetchItems(), loadBuildInputs()])
})

watch([buildProfileId, buildStackId], () => {
  refreshCompatibility()
})
</script>

<style scoped>
.catalog-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.build-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
}

.build-modal {
  width: min(760px, 95vw);
  max-height: 88vh;
  overflow-x: hidden;
  overflow-y: auto;
}

.build-form-fields select {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.build-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.build-form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.build-form-fields .form-group {
  margin-bottom: 0;
}

.build-help {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.catalog-message {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
}

.catalog-error {
  color: var(--error);
}

.catalog-warning {
  color: var(--warning);
}

.catalog-info {
  color: var(--text-secondary);
}

.catalog-section {
  margin-top: var(--space-3);
}

.catalog-section-title,
.catalog-summary {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.catalog-summary {
  cursor: pointer;
}

.catalog-fix-list {
  margin: 0;
  padding-left: 1rem;
}

.catalog-fix-item {
  font-size: var(--font-size-sm);
}

.catalog-trace {
  margin-top: 0.4rem;
  font-size: var(--font-size-sm);
  font-family: var(--font-mono);
}

.catalog-json {
  margin-top: 0.4rem;
}
</style>
