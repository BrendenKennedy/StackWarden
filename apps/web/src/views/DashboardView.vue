<template>
  <div class="dashboard-page">
    <div class="dashboard-heading-row">
      <h1 class="page-title page-title-with-icon dashboard-title">
        <svg viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
          <rect x="3" y="3" width="8" height="8" rx="1.5" />
          <rect x="13" y="3" width="8" height="5" rx="1.5" />
          <rect x="13" y="10" width="8" height="11" rx="1.5" />
          <rect x="3" y="13" width="8" height="8" rx="1.5" />
        </svg>
        <span>Dashboard</span>
      </h1>
      <div class="dashboard-heading-actions">
        <button
          class="btn dashboard-refresh-btn"
          :disabled="refreshing"
          :title="refreshing ? 'Refreshing...' : 'Refresh'"
          aria-label="Refresh"
          @click="refreshData"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
      </div>
    </div>
    <p class="page-subtitle dashboard-subtitle">
      Operational overview of inventory, build activity, and host snapshot.
    </p>

    <div v-if="loading" class="empty-state">Loading dashboard...</div>
    <div v-else class="dashboard-content">
      <div v-if="sectionErrors.inventory" class="message-warning dashboard-message dashboard-top-message">
        Inventory metrics are unavailable: {{ sectionErrors.inventory }}
      </div>

      <section class="card dashboard-section">
        <h2 class="card-title">Inventory Counts</h2>
        <p class="section-subtitle">Core catalog and build volume metrics.</p>
        <div class="dashboard-kpi-grid">
          <article class="inventory-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="4" y="4" width="7" height="7" rx="1.5" />
                <rect x="13" y="4" width="7" height="7" rx="1.5" />
                <rect x="4" y="13" width="7" height="7" rx="1.5" />
                <rect x="13" y="13" width="7" height="7" rx="1.5" />
              </svg>
            </div>
            <p class="kpi-label">Layers</p>
            <p class="kpi-value">{{ layerCount }}</p>
          </article>
          <article class="inventory-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 3L3 8L12 13L21 8L12 3Z" />
                <path d="M3 12L12 17L21 12" />
                <path d="M3 16L12 21L21 16" />
              </svg>
            </div>
            <p class="kpi-label">Stacks</p>
            <p class="kpi-value">{{ stackCount }}</p>
          </article>
          <article class="inventory-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M16 21V19C16 17.34 14.66 16 13 16H7C5.34 16 4 17.34 4 19V21" />
                <circle cx="10" cy="10" r="3" />
                <path d="M20 8V14" />
                <path d="M23 11H17" />
              </svg>
            </div>
            <p class="kpi-label">Profiles</p>
            <p class="kpi-value">{{ profileCount }}</p>
          </article>
          <article class="inventory-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
                <path d="M8 2.5V6.5M16 2.5V6.5M3.5 10.5H20.5" />
              </svg>
            </div>
            <p class="kpi-label">Build Runs (24h)</p>
            <p class="kpi-value">{{ jobsLast24hCount }}</p>
          </article>
        </div>
      </section>

      <section class="card dashboard-section">
        <h2 class="card-title">Host Hardware Overview</h2>
        <p class="section-subtitle">Visual map of this host's core components.</p>
        <div class="hardware-visual-grid">
          <article class="hardware-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="5" y="5" width="14" height="14" rx="2" />
                <rect x="9" y="9" width="6" height="6" rx="1" />
                <path d="M3 9H5M3 15H5M19 9H21M19 15H21M9 3V5M15 3V5M9 19V21M15 19V21" />
              </svg>
            </div>
            <p class="hardware-title">CPU</p>
            <p class="hardware-value">{{ detectionHints?.cpu_model || '-' }}</p>
          </article>
          <article class="hardware-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="7" width="18" height="10" rx="2" />
                <path d="M7 17V19M12 17V19M17 17V19M7 7V5M12 7V5M17 7V5" />
              </svg>
            </div>
            <p class="hardware-title">GPU</p>
            <p class="hardware-value">{{ formatGpu() }}</p>
          </article>
          <article class="hardware-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="4" y="6" width="16" height="12" rx="2" />
                <path d="M8 10H16M8 14H13" />
              </svg>
            </div>
            <p class="hardware-title">Memory</p>
            <p class="hardware-value">{{ formatGiB(detectionHints?.memory_gb_total) }}</p>
          </article>
          <article class="hardware-visual-card">
            <div class="hardware-icon">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="4" y="5" width="16" height="14" rx="2" />
                <circle cx="9" cy="12" r="1.6" />
                <circle cx="15" cy="12" r="1.6" />
              </svg>
            </div>
            <p class="hardware-title">Disk</p>
            <p class="hardware-value">{{ formatGiB(detectionHints?.disk_gb_total) }}</p>
          </article>
        </div>
      </section>

      <section class="card dashboard-section">
        <h2 class="card-title">Host Details</h2>
        <p class="section-subtitle">Clean snapshot of system health, configuration, and runtime facts.</p>
        <div v-if="sectionErrors.system" class="message-warning dashboard-message">
          {{ sectionErrors.system }}
        </div>
        <div v-else-if="!detectionHints && !systemConfig" class="empty-state dashboard-empty">
          No system data available.
        </div>
        <div v-else class="host-detail-grid">
          <article class="host-detail-card">
            <p class="host-detail-label">Service Health</p>
            <p class="host-detail-value">{{ healthOk === true ? 'ok' : healthOk === false ? 'degraded' : '-' }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">Tuple Layer Mode</p>
            <p class="host-detail-value">{{ systemConfig?.tuple_layer_mode || '-' }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">Catalog Local Path</p>
            <p class="host-detail-value">{{ systemConfig?.catalog_local_path || '-' }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">Default Profile</p>
            <p class="host-detail-value">{{ systemConfig?.default_profile || 'none' }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">Runtime</p>
            <p class="host-detail-value">{{ detectionHints?.container_runtime || '-' }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">CPU Cores</p>
            <p class="host-detail-value">{{ formatCpuCores() }}</p>
          </article>
          <article class="host-detail-card">
            <p class="host-detail-label">Host Scope</p>
            <p class="host-detail-value">{{ detectionHints?.host_scope || '-' }}</p>
          </article>
        </div>
      </section>

      <section class="card dashboard-section">
        <h2 class="card-title">Build Activity</h2>
        <p class="section-subtitle">Jobs created in the last 24 hours by status.</p>
        <div v-if="sectionErrors.jobs" class="message-warning dashboard-message">
          {{ sectionErrors.jobs }}
        </div>
        <div v-else-if="jobsLast24hCount === 0" class="empty-state dashboard-empty">
          No build jobs in the last 24 hours.
        </div>
        <div v-else class="status-chip-row">
          <span
            v-for="(count, status) in jobsLast24hByStatus"
            :key="status"
            class="status-chip"
          >
            <span class="status-chip-label">{{ status }}</span>
            <span class="status-chip-count">{{ count }}</span>
          </span>
        </div>
      </section>

      <section class="card dashboard-section">
        <h2 class="card-title">Live Build Log Stream</h2>
        <p class="section-subtitle">Streaming output from the selected job log file/event stream.</p>
        <div v-if="jobsList.length === 0" class="empty-state dashboard-empty">
          No jobs available to stream logs.
        </div>
        <div v-else class="log-stream-section">
          <label class="log-stream-label" for="dashboard-log-job">Job</label>
          <select id="dashboard-log-job" v-model="selectedLogJobId" class="settings-select log-stream-select">
            <option v-for="job in jobsList" :key="job.job_id" :value="job.job_id">
              {{ job.job_id }} — {{ job.status }} — {{ formatJobCreated(job.created_at) }}
            </option>
          </select>
          <LogStream :jobId="selectedLogJobId" />
        </div>
      </section>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { DetectionHints, JobSummary, SystemConfig } from '@/api/types'
import { layers, jobs, profiles, stacks, system } from '@/api/endpoints'
import LogStream from '@/components/LogStream.vue'
import { toUserErrorMessage } from '@/utils/errors'

const loading = ref(true)
const refreshing = ref(false)

const layerCount = ref(0)
const stackCount = ref(0)
const profileCount = ref(0)
const jobsList = ref<JobSummary[]>([])
const selectedLogJobId = ref('')
const detectionHints = ref<DetectionHints | null>(null)
const systemConfig = ref<SystemConfig | null>(null)
const healthOk = ref<boolean | null>(null)

const sectionErrors = ref<{
  inventory: string | null
  jobs: string | null
  system: string | null
}>({
  inventory: null,
  jobs: null,
  system: null,
})

const jobsLast24h = computed(() => {
  const now = Date.now()
  const dayAgo = now - 24 * 60 * 60 * 1000
  return jobsList.value.filter((job) => {
    const ts = new Date(job.created_at).getTime()
    return !Number.isNaN(ts) && ts >= dayAgo
  })
})

const jobsLast24hCount = computed(() => jobsLast24h.value.length)

const jobsLast24hByStatus = computed<Record<string, number>>(() => {
  const counts: Record<string, number> = {}
  for (const job of jobsLast24h.value) {
    counts[job.status] = (counts[job.status] || 0) + 1
  }
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1]))
})

function formatGiB(value: number | null | undefined): string {
  if (value == null) return '-'
  return `${value} GiB`
}

function formatCpuCores(): string {
  const logical = detectionHints.value?.cpu_cores_logical
  const physical = detectionHints.value?.cpu_cores_physical
  if (logical == null && physical == null) return '-'
  return `${logical ?? '?'} logical / ${physical ?? '?'} physical`
}

function formatGpu(): string {
  if (!detectionHints.value?.gpu) return 'not detected'
  const gpu = detectionHints.value.gpu
  if (gpu.compute_capability) {
    return `${gpu.vendor}/${gpu.family} (cc ${gpu.compute_capability})`
  }
  return `${gpu.vendor}/${gpu.family}`
}

function formatJobCreated(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function fetchData() {
  sectionErrors.value = { inventory: null, jobs: null, system: null }

  const [inventoryResult, jobsResult, systemResult] = await Promise.allSettled([
    Promise.all([layers.list(), stacks.list(), profiles.list()]),
    jobs.list(200),
    Promise.all([system.health(), system.detectionHints(), system.config()]),
  ])

  if (inventoryResult.status === 'fulfilled') {
    const [layerRows, stackRows, profileRows] = inventoryResult.value
    layerCount.value = layerRows.length
    stackCount.value = stackRows.length
    profileCount.value = profileRows.length
  } else {
    sectionErrors.value.inventory = toUserErrorMessage(inventoryResult.reason)
    layerCount.value = 0
    stackCount.value = 0
    profileCount.value = 0
  }

  if (jobsResult.status === 'fulfilled') {
    jobsList.value = jobsResult.value
    if (jobsList.value.length > 0 && !jobsList.value.some((job) => job.job_id === selectedLogJobId.value)) {
      selectedLogJobId.value = jobsList.value[0].job_id
    }
  } else {
    sectionErrors.value.jobs = toUserErrorMessage(jobsResult.reason)
    jobsList.value = []
    selectedLogJobId.value = ''
  }

  if (systemResult.status === 'fulfilled') {
    const [health, hints, config] = systemResult.value
    healthOk.value = health.ok
    detectionHints.value = hints
    systemConfig.value = config
  } else {
    sectionErrors.value.system = toUserErrorMessage(systemResult.reason)
    healthOk.value = null
    detectionHints.value = null
    systemConfig.value = null
  }
}

async function refreshData() {
  refreshing.value = true
  try {
    await fetchData()
  } finally {
    refreshing.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchData()
  } finally {
    loading.value = false
  }
})
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

.dashboard-page {
  padding: var(--space-2);
}

.dashboard-heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.dashboard-heading-actions {
  display: flex;
  align-items: center;
}

.dashboard-refresh-btn {
  width: 2rem;
  height: 2rem;
  min-width: 2rem;
  padding: 0.35rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.dashboard-title {
  margin-bottom: 0;
}

.dashboard-subtitle {
  margin-top: var(--space-1);
  margin-bottom: var(--space-4);
}

.dashboard-content {
  padding: var(--space-2);
}

.dashboard-section {
  margin-bottom: var(--space-4);
}

.dashboard-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.inventory-visual-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-tertiary) 70%, transparent);
  padding: var(--space-4);
}

.kpi-label {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  margin-bottom: 0.25rem;
}

.kpi-value {
  font-size: var(--font-size-2xl);
  font-weight: 650;
  line-height: 1.15;
  margin-top: 0.2rem;
}

.section-subtitle {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  margin-top: -0.4rem;
  margin-bottom: var(--space-3);
}

.dashboard-empty {
  padding: var(--space-5) var(--space-3);
}

.dashboard-message {
  margin-top: var(--space-2);
}

.dashboard-top-message {
  margin-bottom: var(--space-4);
}

.hardware-visual-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.hardware-visual-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-tertiary) 70%, transparent);
  padding: var(--space-3);
}

.hardware-icon {
  width: 2.1rem;
  height: 2.1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  margin-bottom: var(--space-2);
}

.hardware-icon svg {
  width: 1.35rem;
  height: 1.35rem;
  stroke: var(--accent);
  stroke-width: 1.7;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.hardware-title {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.hardware-value {
  margin-top: 0.2rem;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-word;
}

.host-detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.host-detail-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  padding: var(--space-3);
}

.host-detail-label {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.host-detail-value {
  margin-top: 0.2rem;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-family: var(--font-mono);
  word-break: break-word;
}

.status-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--bg-tertiary);
  padding: 0.2rem 0.6rem;
}

.status-chip-label {
  color: var(--text-secondary);
  text-transform: uppercase;
  font-size: var(--font-size-xs);
  letter-spacing: 0.03em;
}

.status-chip-count {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.log-stream-section {
  display: grid;
  gap: var(--space-2);
}

.log-stream-label {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.log-stream-select {
  max-width: 100%;
}

@media (max-width: 1100px) {
  .hardware-visual-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .host-detail-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .dashboard-heading-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .host-detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hardware-visual-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
