<template>
  <div>
    <h1 class="page-title">
      Artifact Detail
      <span v-if="artifact" class="artifact-tag">
        {{ artifact.tag }}
      </span>
    </h1>

    <div v-if="loading" class="empty-state">Loading...</div>
    <div v-else-if="loadError" class="auth-warning">{{ loadError }}</div>
    <div v-else-if="!artifact" class="empty-state">Artifact not found.</div>
    <template v-else>
      <!-- Summary card -->
      <div class="card">
        <dl class="detail-grid">
          <dt>Tag</dt>
          <dd>
            {{ artifact.tag }}
            <button class="btn copy-btn" @click="copy(artifact.tag)">Copy</button>
          </dd>
          <dt>Fingerprint</dt>
          <dd>
            {{ artifact.fingerprint }}
            <button class="btn copy-btn" @click="copy(artifact.fingerprint)">Copy</button>
          </dd>
          <dt>Status</dt>
          <dd><JobBadge :status="artifact.status" /></dd>
          <dt>Profile</dt>
          <dd>{{ artifact.profile_id }}</dd>
          <dt>Stack</dt>
          <dd>{{ artifact.stack_id }}</dd>
          <dt>Base Image</dt>
          <dd>{{ artifact.base_image }}</dd>
          <dt>Strategy</dt>
          <dd>{{ artifact.build_strategy }}</dd>
          <dt>Created</dt>
          <dd>{{ new Date(artifact.created_at).toLocaleString() }}</dd>
          <template v-if="artifact.image_id">
            <dt>Image ID</dt>
            <dd>{{ artifact.image_id }}</dd>
          </template>
          <template v-if="artifact.digest">
            <dt>Digest</dt>
            <dd>{{ artifact.digest }}</dd>
          </template>
          <template v-if="artifact.stale_reason">
            <dt>Stale Reason</dt>
            <dd class="text-warning">{{ artifact.stale_reason }}</dd>
          </template>
          <template v-if="artifact.error_detail">
            <dt>Error</dt>
            <dd class="text-error">{{ artifact.error_detail }}</dd>
          </template>
          <template v-if="tupleSummary">
            <dt>Tuple</dt>
            <dd>{{ tupleSummary }}</dd>
          </template>
        </dl>
      </div>

      <!-- Actions -->
      <div class="artifact-actions">
        <button class="btn" @click="runVerify" :disabled="verifying">
          {{ verifying ? 'Verifying...' : 'Verify' }}
        </button>
        <button class="btn" @click="markStale">Mark Stale</button>
        <button class="btn btn-danger" @click="deleteArtifact" :disabled="deleting">
          {{ deleting ? 'Deleting...' : 'Delete' }}
        </button>
      </div>

      <!-- Verify result -->
      <div v-if="verifyResult" class="card verify-card">
        <h3 class="verify-title">
          Verify: <span :class="verifyResult.ok ? 'text-success' : 'text-error'">
            {{ verifyResult.ok ? 'PASS' : 'FAIL' }}
          </span>
        </h3>
        <div v-if="verifyResult.errors.length">
          <div v-for="e in verifyResult.errors" :key="e" class="verify-error">{{ e }}</div>
        </div>
        <div v-if="verifyResult.warnings.length" class="verify-warnings">
          <div v-for="w in verifyResult.warnings" :key="w" class="verify-warning">{{ w }}</div>
        </div>
      </div>

      <!-- Tabs for files -->
      <div class="tabs" role="tablist">
        <button
          v-for="t in tabs"
          :key="t.key"
          :class="['tab', { active: activeTab === t.key }]"
          role="tab"
          type="button"
          :tabindex="activeTab === t.key ? 0 : -1"
          :aria-selected="activeTab === t.key"
          @click="loadTab(t.key)"
          @keydown.enter="loadTab(t.key)"
          @keydown.space.prevent="loadTab(t.key)"
        >
          {{ t.label }}
        </button>
      </div>
      <JsonViewer :data="tabData" :loading="tabLoading" :error="tabError" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ArtifactDetail, VerifyResponse } from '@/api/types'
import { artifacts as artifactsApi, verify as verifyApi } from '@/api/endpoints'
import JobBadge from '@/components/JobBadge.vue'
import JsonViewer from '@/components/JsonViewer.vue'

const props = defineProps<{ id: string }>()
const router = useRouter()

const artifact = ref<ArtifactDetail | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const verifying = ref(false)
const deleting = ref(false)
const verifyResult = ref<VerifyResponse | null>(null)

const tabs = [
  { key: 'manifest', label: 'Manifest' },
  { key: 'plan', label: 'Plan' },
  { key: 'profile', label: 'Profile' },
  { key: 'stack', label: 'Stack' },
  { key: 'sbom', label: 'SBOM' },
]
const activeTab = ref('manifest')
const tabData = ref<unknown>(null)
const tabLoading = ref(false)
const tabError = ref<string | null>(null)
let tabRequestId = 0
const tupleSummary = computed(() => {
  const d = tabData.value as Record<string, any> | null
  if (!d || activeTab.value !== 'manifest') return ''
  const tupleId = d.tuple_id || ''
  if (!tupleId) return ''
  return `${tupleId} (${d.tuple_status || 'unknown'}, mode=${d.tuple_mode || 'unknown'})`
})

onMounted(async () => {
  loadError.value = null
  try {
    artifact.value = await artifactsApi.get(props.id)
    await loadTab('manifest')
  } catch (e: any) {
    loadError.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
})

async function loadTab(key: string) {
  activeTab.value = key
  tabLoading.value = true
  tabError.value = null
  tabData.value = null
  const reqId = ++tabRequestId
  try {
    const data = await artifactsApi.getFile(props.id, key)
    if (reqId !== tabRequestId) return
    tabData.value = data
  } catch (e: any) {
    if (reqId !== tabRequestId) return
    tabError.value = e.message?.includes('404') ? `${key}.json not found` : e.message
  } finally {
    if (reqId === tabRequestId) tabLoading.value = false
  }
}

async function runVerify() {
  if (!artifact.value) return
  verifying.value = true
  try {
    const tagOrId = artifact.value.id || artifact.value.tag
    verifyResult.value = await verifyApi.run({ tag_or_id: tagOrId })
  } catch (e: any) {
    verifyResult.value = {
      ok: false,
      errors: [e.message],
      warnings: [],
      facts: {},
      recomputed_fingerprint: null,
      label_fingerprint: null,
      catalog_fingerprint: null,
      actions: [],
    }
  } finally {
    verifying.value = false
  }
}

async function markStale() {
  if (!artifact.value) return
  try {
    await artifactsApi.markStale(props.id)
    artifact.value = await artifactsApi.get(props.id)
  } catch (e: any) {
    console.error('Failed to mark stale:', e)
  }
}

async function deleteArtifact() {
  if (!artifact.value) return
  deleting.value = true
  try {
    await artifactsApi.remove(props.id)
    router.push({ name: 'catalog' })
  } catch (e: any) {
    console.error('Failed to delete artifact:', e)
    loadError.value = e?.message || String(e)
  } finally {
    deleting.value = false
  }
}

function copy(text: string) {
  navigator.clipboard.writeText(text).catch(() => {})
}
</script>

<style scoped>
.artifact-tag {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-left: var(--space-2);
}

.copy-btn {
  margin-left: var(--space-2);
  padding: 0.2rem 0.5rem;
  font-size: var(--font-size-xs);
}

.text-warning {
  color: var(--warning);
}

.text-error {
  color: var(--error);
}

.text-success {
  color: var(--success);
}

.artifact-actions {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.verify-card {
  margin-bottom: var(--space-4);
}

.verify-title {
  margin-bottom: var(--space-2);
}

.verify-error,
.verify-warning {
  font-size: var(--font-size-sm);
}

.verify-error {
  color: var(--error);
}

.verify-warnings {
  margin-top: var(--space-1);
}

.verify-warning {
  color: var(--warning);
}
</style>
