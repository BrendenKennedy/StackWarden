<template>
  <div>
    <h1 class="page-title page-title-with-icon">
      <svg viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15A1.66 1.66 0 0 0 19.73 16.82L19.79 16.88A2 2 0 1 1 16.96 19.71L16.9 19.65A1.66 1.66 0 0 0 15.08 19.32A1.66 1.66 0 0 0 14 20.85V21A2 2 0 1 1 10 21V20.91A1.66 1.66 0 0 0 8.92 19.38A1.66 1.66 0 0 0 7.1 19.71L7.04 19.77A2 2 0 1 1 4.21 16.94L4.27 16.88A1.66 1.66 0 0 0 4.6 15.06A1.66 1.66 0 0 0 3.07 14H3A2 2 0 1 1 3 10H3.09A1.66 1.66 0 0 0 4.62 8.92A1.66 1.66 0 0 0 4.29 7.1L4.23 7.04A2 2 0 1 1 7.06 4.21L7.12 4.27A1.66 1.66 0 0 0 8.94 4.6H9A1.66 1.66 0 0 0 10 3.09V3A2 2 0 1 1 14 3V3.09A1.66 1.66 0 0 0 15.08 4.62A1.66 1.66 0 0 0 16.9 4.29L16.96 4.23A2 2 0 1 1 19.79 7.06L19.73 7.12A1.66 1.66 0 0 0 19.4 8.94V9A1.66 1.66 0 0 0 20.93 10H21A2 2 0 1 1 21 14H20.91A1.66 1.66 0 0 0 19.38 15Z" />
      </svg>
      <span>Settings</span>
    </h1>

    <div class="card settings-nav-card">
      <div class="settings-nav-header">
        <h3 class="settings-nav-title">Navigator</h3>
        <p class="settings-nav-subtitle">Select a section to view and edit in the window below.</p>
      </div>
      <div class="settings-nav-grid">
        <button
          v-for="section in settingsSections"
          :key="section.id"
          class="btn settings-nav-btn"
          :class="{ 'settings-nav-btn-active': selectedSectionId === section.id }"
          @click="selectedSectionId = section.id"
        >
          {{ section.label }}
        </button>
      </div>
    </div>

    <div class="card settings-panel-card">
      <div class="settings-section-summary">
        <span class="settings-section-title">{{ selectedSectionMeta.label }}</span>
        <span class="settings-section-subtitle">{{ selectedSectionMeta.subtitle }}</span>
      </div>
      <div class="settings-section-body">
        <template v-if="selectedSectionId === 'build-logs'">
          <div v-if="jobsLoading" class="empty-state">Loading jobs...</div>
          <div v-else-if="jobsList.length === 0" class="empty-state">No build jobs yet.</div>
          <div v-else class="settings-jobs-list">
            <div
              v-for="job in jobsList"
              :key="job.job_id"
              class="settings-job-row"
            >
              <button
                type="button"
                class="settings-job-summary"
                @click="expandedJobId = expandedJobId === job.job_id ? null : job.job_id"
              >
                <span class="settings-job-id">{{ job.job_id }}</span>
                <JobBadge :status="job.status" />
                <span class="settings-job-meta">{{ job.profile_id }} / {{ job.stack_id }}</span>
                <span class="settings-job-created">{{ formatJobDate(job.created_at) }}</span>
                <span class="settings-job-toggle">{{ expandedJobId === job.job_id ? '▼' : '▶' }}</span>
              </button>
              <div v-if="expandedJobId === job.job_id" class="settings-job-log">
                <LogStream :jobId="job.job_id" />
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="selectedSectionId === 'server-configuration'">
          <div v-if="loading" class="empty-state">Loading...</div>
          <template v-else>
            <dl class="detail-grid settings-detail-grid">
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
                <button class="btn settings-inline-btn" @click="saveTupleLayerMode" :disabled="savingTupleMode">
                  {{ savingTupleMode ? 'Saving...' : 'Save' }}
                </button>
              </dd>
            </dl>
            <p class="settings-muted-text settings-tuple-hint">
              When <strong>enforce</strong>, builds are blocked if the profile does not match a supported tuple (arch/OS/runtime). Use <strong>warn</strong> or <strong>off</strong> to allow builds on unsupported combinations.
            </p>
          </template>
        </template>

        <template v-else-if="selectedSectionId === 'environment-mode'">
          <p class="settings-muted-text">
            API/UI access now uses secure server-side sessions with admin username/password login.
          </p>
          <div class="settings-security-panel">
            <h4 class="settings-security-title">Account Security</h4>
            <div class="detail-grid settings-detail-grid">
              <dt>Current User</dt>
              <dd>{{ authUsername || 'admin' }}</dd>
            </div>
            <div class="settings-actions settings-password-grid">
              <input
                v-model="currentPasswordInput"
                type="password"
                placeholder="Current password"
                autocomplete="current-password"
              />
              <input
                v-model="newPasswordInput"
                type="password"
                placeholder="New password (min 10 chars)"
                autocomplete="new-password"
              />
              <input
                v-model="confirmPasswordInput"
                type="password"
                placeholder="Confirm new password"
                autocomplete="new-password"
              />
            </div>
            <div class="settings-actions">
              <button class="btn" @click="changePasswordFromSettings" :disabled="changingPassword">
                {{ changingPassword ? 'Updating password...' : 'Change Password' }}
              </button>
              <button class="btn" @click="logoutFromSettings" :disabled="loggingOut">
                {{ loggingOut ? 'Signing out...' : 'Sign Out' }}
              </button>
              <button class="btn" @click="recycleServicesFromUi" :disabled="recyclingServices">
                {{ recyclingServices ? 'Starting recycle...' : 'Recycle Services' }}
              </button>
            </div>
          </div>
        </template>

        <template v-else-if="selectedSectionId === 'profile-defaults'">
          <div class="detail-grid settings-detail-grid">
            <dt>Enable Default Profile</dt>
            <dd><input type="checkbox" v-model="useDefaultProfile" /></dd>
            <dt>Default Profile</dt>
            <dd>
              <select
                v-model="defaultProfileSelection"
                :disabled="!useDefaultProfile || profilesList.length === 0 || profilesLoading"
                class="settings-select settings-default-profile-select"
              >
                <option value="">Select profile</option>
                <option v-for="profile in profilesList" :key="profile.id" :value="profile.id">
                  {{ profile.display_name }} ({{ profile.id }})
                </option>
              </select>
            </dd>
          </div>
          <div class="settings-actions">
            <button class="btn" @click="loadProfiles(true)" :disabled="profilesLoading">
              {{ profilesLoading ? 'Refreshing profiles...' : 'Refresh Profiles' }}
            </button>
          </div>
          <p v-if="profilesLoadError" class="settings-muted-text">{{ profilesLoadError }}</p>
          <p v-else-if="profilesEmpty" class="settings-muted-text">No profiles loaded yet.</p>
          <div class="settings-actions">
            <button class="btn" @click="saveDefaultProfile" :disabled="savingDefaultProfile">
              {{ savingDefaultProfile ? 'Saving...' : 'Save Default Profile' }}
            </button>
          </div>
          <p class="settings-muted-text">When enabled, this profile prepopulates new Catalog build forms and appears as the default on the Dashboard.</p>
        </template>

        <template v-else-if="selectedSectionId === 'ssh-tunnel'">
          <p class="settings-description">
            By default, the StackWarden web API listens on <code class="settings-accent-code">127.0.0.1:8765</code>. Host/port are configurable via web server settings.
          </p>
          <pre class="json-viewer settings-command">ssh -L 8765:127.0.0.1:8765 user@your-server</pre>
          <p class="settings-muted-text settings-top-gap">Then open <code>http://localhost:8765</code> in your browser.</p>
        </template>

        <template v-else-if="selectedSectionId === 'tuple-catalog'">
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
        </template>

        <template v-else-if="selectedSectionId === 'host-facts'">
          <div class="host-facts-header">
            <button class="btn" @click="refreshDetectionHints" :disabled="detectingHints">
              {{ detectingHints ? 'Detecting...' : 'Refresh Detection' }}
            </button>
          </div>
          <div v-if="dependencyIssues.length > 0" class="auth-warning settings-warning-block">
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
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { DetectionHints, JobSummary, ProfileSummary, SystemConfig, TupleCatalog } from '@/api/types'
import { jobs as jobsApi, profiles as profilesApi, settings, system } from '@/api/endpoints'
import JobBadge from '@/components/JobBadge.vue'
import LogStream from '@/components/LogStream.vue'
import { useAuthSession } from '@/composables/useAuthSession'
import { useToast } from '@/composables/useToast'
import { toUserErrorMessage } from '@/utils/errors'
import { formatProbeIssues } from '@/utils/probeWarnings'

type SettingsSectionId =
  | 'environment-mode'
  | 'profile-defaults'
  | 'server-configuration'
  | 'tuple-catalog'
  | 'host-facts'
  | 'build-logs'
  | 'ssh-tunnel'

const settingsSections: Array<{ id: SettingsSectionId; label: string; subtitle: string }> = [
  { id: 'environment-mode', label: 'Account & Security', subtitle: 'Session account controls and service lifecycle actions.' },
  { id: 'profile-defaults', label: 'Profile Defaults', subtitle: 'Default profile preselection for new catalog builds.' },
  { id: 'server-configuration', label: 'Server Configuration', subtitle: 'Core paths, registry policy, and tuple behavior.' },
  { id: 'tuple-catalog', label: 'Tuple Catalog', subtitle: 'Compatibility matrix status and tuple entries.' },
  { id: 'host-facts', label: 'Host Facts', subtitle: 'Hardware/runtime detection output and confidence.' },
  { id: 'build-logs', label: 'Build Logs', subtitle: 'Recent build jobs and streaming logs.' },
  { id: 'ssh-tunnel', label: 'SSH Tunnel', subtitle: 'Secure local access instructions for the web UI.' },
]

const config = ref<SystemConfig | null>(null)
const router = useRouter()
const loading = ref(true)
const jobsList = ref<JobSummary[]>([])
const jobsLoading = ref(false)
const expandedJobId = ref<string | null>(null)
const detectionHints = ref<DetectionHints | null>(null)
const tupleCatalog = ref<TupleCatalog | null>(null)
const detectingHints = ref(false)
const { showToast } = useToast()
const { username: authUsername, changePassword, logout } = useAuthSession()
const tupleLayerMode = ref('enforce')
const savingTupleMode = ref(false)
const profilesList = ref<ProfileSummary[]>([])
const profilesLoading = ref(false)
const profilesLoadError = ref<string | null>(null)
const profilesEmpty = ref(false)
const useDefaultProfile = ref(false)
const defaultProfileSelection = ref('')
const savingDefaultProfile = ref(false)
const recyclingServices = ref(false)
const changingPassword = ref(false)
const loggingOut = ref(false)
const currentPasswordInput = ref('')
const newPasswordInput = ref('')
const confirmPasswordInput = ref('')
const selectedSectionId = ref<SettingsSectionId>('environment-mode')
const dependencyIssues = computed(() => formatProbeIssues(detectionHints.value))
const selectedSectionMeta = computed(() =>
  settingsSections.find((section) => section.id === selectedSectionId.value) ?? settingsSections[0],
)
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
    const [cfg, hints, tuples, profiles] = await Promise.all([
      system.config(),
      system.detectionHints(),
      settings.tupleCatalog().catch(() => null),
      profilesApi.list().catch(() => [] as ProfileSummary[]),
    ])
    config.value = cfg
    tupleLayerMode.value = cfg.tuple_layer_mode || 'enforce'
    profilesList.value = profiles
    profilesLoadError.value = null
    profilesEmpty.value = profiles.length === 0
    useDefaultProfile.value = !!cfg.default_profile
    defaultProfileSelection.value = cfg.default_profile || ''
    detectionHints.value = hints
    tupleCatalog.value = tuples
  } catch (e) {
    showToast(`Failed to load settings config: ${toUserErrorMessage(e)}`, 'error')
  } finally {
    loading.value = false
  }

  jobsLoading.value = true
  try {
    jobsList.value = await jobsApi.list(50)
  } catch (e) {
    showToast(`Failed to load jobs: ${toUserErrorMessage(e)}`, 'error')
  } finally {
    jobsLoading.value = false
  }
})

watch(selectedSectionId, (sectionId) => {
  if (sectionId === 'profile-defaults' && (profilesList.value.length === 0 || profilesLoadError.value)) {
    void loadProfiles(true)
  }
})

async function loadProfiles(force = false) {
  if (profilesLoading.value) return
  if (!force && profilesList.value.length > 0) return
  profilesLoading.value = true
  try {
    profilesList.value = await profilesApi.list()
    profilesLoadError.value = null
    profilesEmpty.value = profilesList.value.length === 0
  } catch (err) {
    profilesLoadError.value = toUserErrorMessage(err)
    profilesEmpty.value = false
  } finally {
    profilesLoading.value = false
  }
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

async function saveTupleLayerMode() {
  savingTupleMode.value = true
  try {
    const updated = await settings.updateConfig(
      { tuple_layer_mode: tupleLayerMode.value },
    )
    config.value = updated
    showToast('Tuple layer mode saved', 'success')
  } catch (err) {
    showToast(`Save failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    savingTupleMode.value = false
  }
}

async function saveDefaultProfile() {
  if (useDefaultProfile.value && !defaultProfileSelection.value) {
    showToast('Select a default profile or disable the toggle', 'warning')
    return
  }
  savingDefaultProfile.value = true
  try {
    const updated = await settings.updateConfig(
      { default_profile: useDefaultProfile.value ? defaultProfileSelection.value : null },
    )
    config.value = updated
    useDefaultProfile.value = !!updated.default_profile
    defaultProfileSelection.value = updated.default_profile || ''
    showToast('Default profile saved', 'success')
  } catch (err) {
    showToast(`Save failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    savingDefaultProfile.value = false
  }
}

async function recycleServicesFromUi() {
  recyclingServices.value = true
  try {
    const result = await settings.recycleServices()
    showToast(`Recycle started (pid ${result.pid}). UI may briefly disconnect while services restart.`, 'success')
  } catch (err) {
    showToast(`Recycle failed to start: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    recyclingServices.value = false
  }
}

async function changePasswordFromSettings() {
  if (!currentPasswordInput.value || !newPasswordInput.value) {
    showToast('Provide current and new passwords', 'warning')
    return
  }
  if (newPasswordInput.value !== confirmPasswordInput.value) {
    showToast('New password confirmation does not match', 'warning')
    return
  }
  changingPassword.value = true
  try {
    await changePassword(currentPasswordInput.value, newPasswordInput.value)
    currentPasswordInput.value = ''
    newPasswordInput.value = ''
    confirmPasswordInput.value = ''
    showToast('Password updated', 'success')
  } catch (err) {
    showToast(`Password update failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    changingPassword.value = false
  }
}

async function logoutFromSettings() {
  loggingOut.value = true
  try {
    await logout()
    await router.replace('/login')
  } catch (err) {
    showToast(`Logout failed: ${toUserErrorMessage(err)}`, 'error')
  } finally {
    loggingOut.value = false
  }
}
</script>

<style scoped>
.page-title-with-icon {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.page-title-icon {
  width: 1.3rem;
  height: 1.3rem;
  flex: 0 0 1.3rem;
  stroke: var(--accent);
  stroke-width: 1.9;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.settings-nav-card {
  margin-bottom: 1rem;
}

.settings-panel-card {
  padding: 0;
  overflow: hidden;
}

.settings-nav-header {
  margin-bottom: 0.75rem;
}

.settings-nav-title {
  font-size: var(--font-size-md);
  margin-bottom: 0.2rem;
}

.settings-nav-subtitle {
  color: var(--text-muted);
  font-size: var(--font-size-xs);
}

.settings-nav-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.settings-nav-btn {
  justify-content: flex-start;
}

.settings-nav-btn-active {
  background: color-mix(in srgb, var(--accent) 18%, var(--bg-tertiary));
  border-color: color-mix(in srgb, var(--accent) 30%, var(--border));
  color: var(--accent);
}

.settings-section-summary {
  list-style: none;
  cursor: pointer;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg-tertiary) 75%, transparent);
  user-select: none;
}

.settings-section-summary::-webkit-details-marker {
  display: none;
}

.settings-section-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-primary);
}

.settings-section-subtitle {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}

.settings-section-body {
  padding: 0.95rem 1rem 1rem;
}

.host-facts-header {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 0.75rem;
}

.settings-description {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.settings-password-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
}

.settings-security-panel {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}

.settings-security-title {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.settings-detail-grid {
  margin-bottom: 0.75rem;
}

.settings-select {
  padding: 0.25rem 0.5rem;
  margin-right: 0.5rem;
  font-size: var(--font-size-sm);
}

.settings-default-profile-select {
  width: min(560px, 100%);
  margin-right: 0;
}

.settings-inline-btn {
  margin-left: 0.25rem;
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
  width: 100%;
  border: 0;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  background: var(--bg-tertiary);
  text-align: left;
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
  .settings-nav-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .host-facts-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .settings-actions {
    flex-direction: column;
    align-items: stretch;
  }

}
</style>
