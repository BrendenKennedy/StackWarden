<template>
  <div>
    <h1 v-if="selectedJobId" class="page-title">Jobs</h1>

    <!-- Job detail view when :id is in route -->
    <template v-if="selectedJobId">
      <button class="btn jobs-back-btn" @click="backToList">&larr; Back to Catalog</button>

      <div v-if="selectedJobLoading" class="empty-state">Loading job...</div>
      <div v-else-if="selectedJobError" class="auth-warning">{{ selectedJobError }}</div>
      <div v-else-if="!selectedJob" class="empty-state">Job not found.</div>
      <template v-else>
        <div class="card">
          <dl class="detail-grid">
            <dt>Job ID</dt>
            <dd>{{ selectedJob.job_id }}</dd>
            <dt>Status</dt>
            <dd><JobBadge :status="selectedJob.status" /></dd>
            <dt>Profile</dt>
            <dd>{{ selectedJob.profile_id }}</dd>
            <dt>Stack</dt>
            <dd>{{ selectedJob.stack_id }}</dd>
            <dt>Created</dt>
            <dd>{{ new Date(selectedJob.created_at).toLocaleString() }}</dd>
            <template v-if="selectedJob.started_at">
              <dt>Started</dt>
              <dd>{{ new Date(selectedJob.started_at).toLocaleString() }}</dd>
            </template>
            <template v-if="selectedJob.ended_at">
              <dt>Ended</dt>
              <dd>{{ new Date(selectedJob.ended_at).toLocaleString() }}</dd>
            </template>
            <template v-if="selectedJob.result_tag">
              <dt>Result</dt>
              <dd>
                <router-link
                  v-if="selectedJob.result_artifact_id"
                  :to="{ name: 'artifact-detail', params: { id: selectedJob.result_artifact_id } }"
                >
                  {{ selectedJob.result_tag }}
                </router-link>
                <span v-else>{{ selectedJob.result_tag }}</span>
              </dd>
            </template>
            <template v-if="selectedJob.error_message">
              <dt>Error</dt>
              <dd class="job-error">{{ selectedJob.error_message }}</dd>
            </template>
          </dl>
        </div>
        <div
          v-if="selectedJob.build_optimization && Object.keys(selectedJob.build_optimization).length"
          class="card jobs-section-card"
        >
          <h3 class="jobs-section-title">
            Build Optimization
          </h3>
          <pre class="json-viewer">{{ JSON.stringify(selectedJob.build_optimization, null, 2) }}</pre>
        </div>

        <LogStream
          v-if="selectedJob.status === 'running' || selectedJob.status === 'queued'"
          :jobId="selectedJob.job_id"
        />
        <!-- For completed jobs, show the log file content if available -->
        <div v-else-if="selectedJob.log_path" class="card jobs-section-card">
          <h3 class="jobs-section-title">Build Log</h3>
          <div class="log-panel">
            <div class="log-line jobs-log-path">
              Log file: {{ selectedJob.log_path }}
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- Job list view -->
    <template v-else>
      <PageEntityTable
        title="Jobs"
        :loading="loading"
        loading-message="Loading jobs..."
        empty-message="No jobs yet. Start a build from the Build page."
        :error-message="errorMessage"
        :rows="tableRows"
        :columns="tableColumns"
        route-base="/jobs"
        id-key="job_id"
        :show-edit="false"
        :show-delete="false"
        @refresh="fetchJobs"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { JobSummary, JobDetail } from '@/api/types'
import { jobs as jobsApi } from '@/api/endpoints'
import { toUserErrorMessage } from '@/utils/errors'
import LogStream from '@/components/LogStream.vue'
import JobBadge from '@/components/JobBadge.vue'
import PageEntityTable from '@/components/PageEntityTable.vue'

const props = defineProps<{ id?: string }>()
const route = useRoute()
const router = useRouter()

const jobList = ref<JobSummary[]>([])
const loading = ref(true)
const selectedJob = ref<JobDetail | null>(null)
const selectedJobLoading = ref(false)
const selectedJobError = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const tableColumns = [
  { key: 'job_id', label: 'Job ID', width: '18%', truncate: true },
  { key: 'profile_id', label: 'Profile', width: '14%', truncate: true },
  { key: 'stack_id', label: 'Stack', width: '14%', truncate: true },
  { key: 'created', label: 'Created', width: '18%' },
  { key: 'result', label: 'Result', width: '14%' },
  { key: 'status', label: 'Status', width: '10%', badge: true },
]
const tableRows = computed(() =>
  jobList.value.map((j) => ({
    job_id: j.job_id,
    status: j.status,
    profile_id: j.profile_id,
    stack_id: j.stack_id,
    created: formatDate(j.created_at),
    result: j.ended_at ? formatDuration(j.created_at, j.ended_at) : (j.started_at ? 'running...' : ''),
  })),
)

const selectedJobId = computed(() => props.id || (route.params.id as string | undefined))

async function fetchJobs() {
  loading.value = true
  errorMessage.value = null
  try {
    jobList.value = await jobsApi.list(100)
  } catch (e: unknown) {
    errorMessage.value = toUserErrorMessage(e)
  } finally {
    loading.value = false
  }
}

async function fetchJobDetail(id: string) {
  selectedJobLoading.value = true
  selectedJobError.value = null
  selectedJob.value = null
  try {
    selectedJob.value = await jobsApi.get(id)
  } catch (e: unknown) {
    selectedJobError.value = toUserErrorMessage(e)
  } finally {
    selectedJobLoading.value = false
  }
}

function backToList() {
  selectedJob.value = null
  router.push({ name: 'catalog' })
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

watch(selectedJobId, (id) => {
  if (id) fetchJobDetail(id)
  else fetchJobs()
}, { immediate: true })
</script>

<style scoped>
.jobs-back-btn {
  margin-bottom: var(--space-4);
}

.job-error {
  color: var(--error);
}

.jobs-section-card {
  margin-top: var(--space-4);
}

.jobs-section-title {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-md);
  color: var(--text-secondary);
}

.jobs-log-path {
  color: var(--text-muted);
}
</style>
