<template>
  <div>
    <h1 class="page-title">Settings</h1>

    <div class="card">
      <h3 class="settings-card-title">Build Logs</h3>
      <p class="settings-description settings-description-tight">
        View logs for recent build jobs. Catalog shows artifacts only; job logs are accessed here.
      </p>
      <div v-if="jobsLoading" class="empty-state">Loading jobs...</div>
      <div v-else-if="jobsList.length === 0" class="empty-state">No build jobs yet.</div>
      <div v-else class="settings-jobs-list">
        <div
          v-for="job in jobsList"
          :key="job.job_id"
          class="settings-job-row"
        >
          <div class="settings-job-summary" @click="expandedJobId = expandedJobId === job.job_id ? null : job.job_id">
            <span class="settings-job-id">{{ job.job_id }}</span>
            <JobBadge :status="job.status" />
            <span class="settings-job-meta">{{ job.profile_id }} / {{ job.stack_id }}</span>
            <span class="settings-job-created">{{ formatJobDate(job.created_at) }}</span>
            <span class="settings-job-toggle">{{ expandedJobId === job.job_id ? '▼' : '▶' }}</span>
          </div>
          <div v-if="expandedJobId === job.job_id" class="settings-job-log">
            <LogStream :jobId="job.job_id" />
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="settings-card-title">Server Configuration</h3>
      <div v-if="loading" class="empty-state">Loading...</div>
      <dl v-else class="detail-grid settings-detail-grid">
        <dt>Catalog Path</dt>
        <dd>{{ config?.catalog_path || 'default' }}</dd>
        <dt>Log Directory</dt>
        <dd>{{ config?.log_dir || 'default' }}</dd>
        <dt>Default Profile</dt>
        <dd>{{ config?.default_profile || 'none' }}</dd>
        <dt>Registry Allow</dt>
        <dd>{{ config?.registry_allow?.length ? config.registry_allow.join(', ') : 'all' }}</dd>
        <dt>Registry Deny</dt>
        <dd>{{ config?.registry_deny?.length ? config.registry_deny.join(', ') : 'none' }}</dd>
        <dt>Tuple Layer Mode</dt>
        <dd>
          <select v-model="tupleLayerMode" class="settings-select">
            <option value="enforce">enforce</option>
            <option value="warn">warn</option>
            <option value="off">off</option>
          </select>
          <input
            type="password"
            v-model="adminTokenInput"
            placeholder="Admin token"
            autocomplete="off"
            class="settings-token-inline"
          />
          <button
            class="btn settings-inline-btn"
            @click="saveTupleLayerMode"
            :disabled="savingTupleMode"
          >
            {{ savingTupleMode ? 'Saving...' : 'Save' }}
          </button>
        </dd>
      </dl>
      <p class="settings-muted-text settings-tuple-hint">
        When <strong>enforce</strong>, builds are blocked if the profile does not match a supported tuple (arch/OS/runtime). Use <strong>warn</strong> or <strong>off</strong> to allow builds on unsupported combinations (e.g. ARM + Ubuntu 24).
      </p>
    </div>

    <div class="card">
      <h3 class="settings-card-title">Remote Catalog Repository</h3>
      <p class="settings-description">
        Configure a git repo containing `specs/profiles/`, `specs/stacks/`, `specs/blocks/`, and `specs/rules/`.
        When enabled, StackWarden reads catalog data from the local checkout path.
      </p>
      <div class="detail-grid settings-detail-grid">
        <dt>Enable Remote Catalog</dt>
        <dd><input type="checkbox" v-model="remoteEnabled" /></dd>
        <dt>Repository URL</dt>
        <dd><input type="text" v-model="remoteRepoUrl" placeholder="https://github.com/org/stackwarden-data.git" /></dd>
        <dt>Branch</dt>
        <dd><input type="text" v-model="remoteBranch" placeholder="main" /></dd>
        <dt>Local Checkout Path</dt>
        <dd><input type="text" v-model="remoteLocalPath" placeholder="~/.local/share/stackwarden/remote-catalog" /></dd>
        <dt>Local Overrides Path</dt>
        <dd><input type="text" v-model="remoteLocalOverridesPath" placeholder="~/.local/share/stackwarden/local-catalog" /></dd>
        <dt>Auto Pull During Ensure</dt>
        <dd><input type="checkbox" v-model="remoteAutoPull" /></dd>
      </div>
      <div class="settings-actions">
        <input
          type="password"
          v-model="adminTokenInput"
          placeholder="Admin token (optional)"
          autocomplete="off"
          class="settings-admin-input"
        />
        <button class="btn" @click="saveRemoteConfig" :disabled="savingRemoteConfig">
          {{ savingRemoteConfig ? 'Saving...' : 'Save Remote Config' }}
        </button>
        <button class="btn" @click="saveAndPullRemote" :disabled="savingRemoteConfig">
          {{ savingRemoteConfig ? 'Syncing...' : 'Save + Pull Now' }}
        </button>
      </div>
      <p v-if="remoteSyncMessage" class="settings-muted-text">
        {{ remoteSyncMessage }}
      </p>
    </div>

    <div class="card">
      <h3 class="settings-card-title">Access via SSH Tunnel</h3>
      <p class="settings-description">
        The StackWarden web UI binds to <code class="settings-accent-code">127.0.0.1:8765</code> only.
        To access it from your local machine, forward the port over SSH:
      </p>
      <pre class="json-viewer settings-command">ssh -L 8765:127.0.0.1:8765 user@your-server</pre>
      <p class="settings-muted-text settings-top-gap">
        Then open <code>http://localhost:8765</code> in your browser.
      </p>
    </div>

    <div class="card" v-if="!hasToken">
      <h3 class="settings-card-title">Authentication Token</h3>
      <p class="settings-description settings-description-tight">
        If the server requires a token, enter it here. It will be stored in localStorage.
      </p>
      <div class="settings-actions">
        <input type="password" v-model="tokenInput" placeholder="Bearer token" class="settings-flex-input" autocomplete="off" />
        <button class="btn" @click="saveToken">Save</button>
      </div>
    </div>
    <div class="card" v-else>
      <h3 class="settings-card-title settings-card-title-tight">Authentication Token</h3>
      <p class="settings-token-set">Token is set.</p>
      <button class="btn settings-top-gap" @click="clearToken">Clear Token</button>
    </div>

    <div class="card">
      <h3 class="settings-card-title">Tuple Catalog</h3>
      <div v-if="tupleCatalog">
        <dl class="detail-grid">
          <dt>Schema Version</dt>
          <dd>{{ tupleCatalog.schema_version }}</dd>
          <dt>Revision</dt>
          <dd>{{ tupleCatalog.revision }}</dd>
          <dt>Total Tuples</dt>
          <dd>{{ tupleCatalog.tuples.length }}</dd>
          <dt>Supported</dt>
          <dd>{{ tupleCounts.supported }}</dd>
          <dt>Experimental</dt>
          <dd>{{ tupleCounts.experimental }}</dd>
          <dt>Unsupported</dt>
          <dd>{{ tupleCounts.unsupported }}</dd>
        </dl>
        <details class="settings-details-block">
          <summary>Tuple Entries</summary>
          <ul class="compact-list">
            <li v-for="item in tupleCatalog.tuples" :key="item.id">
              <code>{{ item.id }}</code> — {{ item.status }} — {{ item.selector.arch }} / {{ item.selector.container_runtime }} / {{ item.selector.gpu_vendor_id }}
            </li>
          </ul>
        </details>
      </div>
      <div v-else class="empty-state">Tuple catalog unavailable.</div>
    </div>

    <div class="card">
      <div class="host-facts-header">
        <h3 class="settings-card-title settings-card-title-no-margin">Discovered Host Facts</h3>
        <button class="btn" @click="refreshDetectionHints" :disabled="detectingHints">
          {{ detectingHints ? 'Detecting...' : 'Refresh Detection' }}
        </button>
      </div>
      <div
        v-if="dependencyIssues.length > 0"
        class="auth-warning settings-warning-block"
      >
        Detection dependencies need attention:
        <ul class="dependency-list">
          <li v-for="issue in dependencyIssues" :key="issue.key">
            <strong>{{ issue.label }}</strong>: {{ issue.reason }}
            <a :href="issue.docs" target="_blank" rel="noopener noreferrer">Docs</a>
          </li>
        </ul>
      </div>
      <div v-if="detectionHints">
        <dl class="detail-grid">
          <dt>Scope</dt><dd>{{ detectionHints.host_scope || '-' }}</dd>
          <dt>Arch</dt><dd>{{ detectionHints.arch || '-' }}</dd>
          <dt>OS</dt><dd>{{ detectionHints.os_family || detectionHints.os || '-' }} {{ detectionHints.os_version || '' }}</dd>
          <dt>Runtime</dt><dd>{{ detectionHints.container_runtime || '-' }}</dd>
          <dt>CUDA Runtime Range</dt>
          <dd>
            {{
              detectionHints.supported_cuda_min || detectionHints.supported_cuda_max
                ? `${detectionHints.supported_cuda_min || '?'} - ${detectionHints.supported_cuda_max || '?'}`
                : 'not detected'
            }}
          </dd>
          <dt>Driver Version</dt><dd>{{ detectionHints.driver_version || '-' }}</dd>
          <dt>GPU</dt>
          <dd>
            {{
              detectionHints.gpu
                ? `${detectionHints.gpu.vendor}/${detectionHints.gpu.family}${detectionHints.gpu.compute_capability ? ` (cc ${detectionHints.gpu.compute_capability})` : ''}`
                : 'not detected'
            }}
          </dd>
          <dt>CPU</dt><dd>{{ detectionHints.cpu_model || '-' }}</dd>
          <dt>CPU Cores</dt>
          <dd>
            {{
              detectionHints.cpu_cores_logical || detectionHints.cpu_cores_physical
                ? `${detectionHints.cpu_cores_logical ?? '?'} logical / ${detectionHints.cpu_cores_physical ?? '?'} physical`
                : '-'
            }}
          </dd>
          <dt>Memory</dt><dd>{{ detectionHints.memory_gb_total != null ? `${detectionHints.memory_gb_total} GiB` : '-' }}</dd>
          <dt>Disk</dt><dd>{{ detectionHints.disk_gb_total != null ? `${detectionHints.disk_gb_total} GiB` : '-' }}</dd>
        </dl>

        <details v-if="(detectionHints.gpu_devices?.length || 0) > 0" class="settings-details-block">
          <summary>GPU Devices ({{ detectionHints.gpu_devices?.length || 0 }})</summary>
          <ul class="compact-list">
            <li v-for="gpu in detectionHints.gpu_devices || []" :key="gpu.index">
              #{{ gpu.index }} {{ gpu.model || '-' }} / {{ gpu.family || '-' }}
              (cc {{ gpu.compute_capability || '?' }}, {{ gpu.memory_gb ?? '?' }} GiB)
            </li>
          </ul>
        </details>

        <details v-if="Object.keys(detectionHints.confidence || {}).length > 0" class="settings-details-block">
          <summary>Confidence</summary>
          <ul class="compact-list">
            <li v-for="([field, level]) in Object.entries(detectionHints.confidence || {})" :key="field">
              {{ field }}: {{ level }}
            </li>
          </ul>
        </details>

        <details v-if="Object.keys(detectionHints.resolved_ids || {}).length > 0" class="settings-details-block">
          <summary>Resolved Hardware IDs</summary>
          <ul class="compact-list">
            <li v-for="([key, val]) in Object.entries(detectionHints.resolved_ids || {})" :key="key">
              {{ key }} -> {{ val }}
            </li>
          </ul>
        </details>
      </div>
      <div v-else class="empty-state">No host facts loaded yet.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { DetectionHints, JobSummary, SystemConfig, TupleCatalog } from '@/api/types'
import { jobs as jobsApi, settings, system } from '@/api/endpoints'
import JobBadge from '@/components/JobBadge.vue'
import LogStream from '@/components/LogStream.vue'
import { useToast } from '@/composables/useToast'
import { toUserErrorMessage } from '@/utils/errors'
import { formatProbeIssues } from '@/utils/probeWarnings'

const config = ref<SystemConfig | null>(null)
const loading = ref(true)
const jobsList = ref<JobSummary[]>([])
const jobsLoading = ref(false)
const expandedJobId = ref<string | null>(null)
const tokenInput = ref('')
const hasToken = ref(!!localStorage.getItem('stackwarden_token'))
const detectionHints = ref<DetectionHints | null>(null)
const tupleCatalog = ref<TupleCatalog | null>(null)
const detectingHints = ref(false)
const { showToast } = useToast()
const tupleLayerMode = ref('enforce')
const savingTupleMode = ref(false)
const remoteEnabled = ref(false)
const remoteRepoUrl = ref('')
const remoteBranch = ref('main')
const remoteLocalPath = ref('~/.local/share/stackwarden/remote-catalog')
const remoteLocalOverridesPath = ref('~/.local/share/stackwarden/local-catalog')
const remoteAutoPull = ref(true)
const adminTokenInput = ref('')
const savingRemoteConfig = ref(false)
const remoteSyncMessage = ref('')
const dependencyIssues = computed(() => formatProbeIssues(detectionHints.value))
const tupleCounts = computed(() => {
  const tuples = tupleCatalog.value?.tuples || []
  return {
    supported: tuples.filter(t => t.status === 'supported').length,
    experimental: tuples.filter(t => t.status === 'experimental').length,
    unsupported: tuples.filter(t => t.status === 'unsupported').length,
  }
})

function formatJobDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

onMounted(async () => {
  try {
    const [cfg, hints, tuples] = await Promise.all([
      system.config(),
      system.detectionHints(),
      settings.tupleCatalog().catch(() => null),
    ])
    config.value = cfg
    tupleLayerMode.value = cfg.tuple_layer_mode || 'enforce'
    remoteEnabled.value = !!cfg.remote_catalog_enabled
    remoteRepoUrl.value = cfg.remote_catalog_repo_url || ''
    remoteBranch.value = cfg.remote_catalog_branch || 'main'
    remoteLocalPath.value = cfg.remote_catalog_local_path || '~/.local/share/stackwarden/remote-catalog'
    remoteLocalOverridesPath.value = cfg.remote_catalog_local_overrides_path || '~/.local/share/stackwarden/local-catalog'
    remoteAutoPull.value = cfg.remote_catalog_auto_pull ?? true
    detectionHints.value = hints
    tupleCatalog.value = tuples
  } catch (e) {
    console.error('Failed to load config:', e)
  } finally {
    loading.value = false
  }

  jobsLoading.value = true
  try {
    jobsList.value = await jobsApi.list(50)
  } catch (e) {
    console.error('Failed to load jobs:', e)
  } finally {
    jobsLoading.value = false
  }
})

function saveToken() {
  if (tokenInput.value.trim()) {
    localStorage.setItem('stackwarden_token', tokenInput.value.trim())
    hasToken.value = true
    tokenInput.value = ''
  }
}

function clearToken() {
  localStorage.removeItem('stackwarden_token')
  hasToken.value = false
}

async function refreshDetectionHints() {
  detectingHints.value = true
  try {
    detectionHints.value = await system.detectionHints(true)
    showToast('Host detection refreshed', 'success')
  } catch (err) {
    showToast(`Detection refresh failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    detectingHints.value = false
  }
}

async function updateRemoteConfig(syncNow = false) {
  savingRemoteConfig.value = true
  try {
    const updated = await settings.updateConfig(
      {
        remote_catalog_enabled: remoteEnabled.value,
        remote_catalog_repo_url: remoteRepoUrl.value.trim() || null,
        remote_catalog_branch: remoteBranch.value.trim() || 'main',
        remote_catalog_local_path: remoteLocalPath.value.trim() || '~/.local/share/stackwarden/remote-catalog',
        remote_catalog_local_overrides_path:
          remoteLocalOverridesPath.value.trim() || '~/.local/share/stackwarden/local-catalog',
        remote_catalog_auto_pull: remoteAutoPull.value,
        sync_now: syncNow,
      },
      adminTokenInput.value.trim() || undefined,
    )
    config.value = updated
    remoteSyncMessage.value = updated.remote_catalog_last_sync_detail || ''
    showToast(syncNow ? 'Remote catalog synced' : 'Remote config saved', 'success')
  } catch (err) {
    showToast(`Remote config update failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    savingRemoteConfig.value = false
  }
}

async function saveRemoteConfig() {
  await updateRemoteConfig(false)
}

async function saveTupleLayerMode() {
  savingTupleMode.value = true
  try {
    const updated = await settings.updateConfig(
      { tuple_layer_mode: tupleLayerMode.value },
      adminTokenInput.value.trim() || undefined,
    )
    config.value = updated
    showToast('Tuple layer mode saved', 'success')
  } catch (err) {
    showToast(`Save failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    savingTupleMode.value = false
  }
}

async function saveAndPullRemote() {
  await updateRemoteConfig(true)
}
</script>

<style scoped>
.host-facts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.settings-card-title {
  margin-bottom: 0.75rem;
}

.settings-card-title-tight {
  margin-bottom: 0.5rem;
}

.settings-card-title-no-margin {
  margin-bottom: 0;
}

.settings-description {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.settings-description-tight {
  margin-bottom: 0.5rem;
}

.settings-detail-grid {
  margin-bottom: 0.75rem;
}

.settings-select {
  padding: 0.25rem 0.5rem;
  margin-right: 0.5rem;
  font-size: var(--font-size-sm);
}

.settings-inline-btn {
  margin-left: 0.25rem;
}

.settings-token-inline {
  width: 140px;
  margin-left: 0.5rem;
  padding: 0.25rem 0.5rem;
  font-size: var(--font-size-sm);
}

.settings-tuple-hint {
  margin-top: 0.5rem;
}

.settings-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.settings-admin-input {
  min-width: 280px;
  flex: 1;
}

.settings-flex-input {
  flex: 1;
}

.settings-muted-text {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

.settings-top-gap {
  margin-top: 0.5rem;
}

.settings-accent-code {
  color: var(--accent);
}

.settings-command {
  font-size: var(--font-size-sm);
}

.settings-token-set {
  font-size: var(--font-size-md);
  color: var(--success);
}

.settings-details-block,
.settings-warning-block {
  margin-top: 0.75rem;
}

.auth-warning {
  background: #3b2e10;
  border: 1px solid var(--warning);
  border-radius: var(--radius);
  padding: 0.625rem 1rem;
  color: var(--warning);
  font-size: 0.8125rem;
  margin-bottom: 1rem;
}

.dependency-list {
  margin: 0.4rem 0 0 1.1rem;
  padding: 0;
}

.dependency-list li {
  margin-bottom: 0.2rem;
}

.dependency-list a {
  margin-left: 0.35rem;
}

.compact-list {
  margin: 0.4rem 0 0 1.2rem;
  padding: 0;
}

.settings-jobs-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.settings-job-row {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.settings-job-summary {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  background: var(--bg-tertiary);
  font-size: var(--font-size-sm);
}

.settings-job-summary:hover {
  background: var(--bg-hover);
}

.settings-job-id {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  min-width: 10rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.settings-job-meta {
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.settings-job-created {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.settings-job-toggle {
  color: var(--text-muted);
  font-size: 0.7rem;
}

.settings-job-log {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border);
  background: var(--bg-primary);
}

@media (max-width: 768px) {
  .host-facts-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .settings-admin-input {
    min-width: 100%;
  }
}
</style>
