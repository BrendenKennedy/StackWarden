<template>
  <div>
    <h1 class="page-title page-title-with-icon">
      <svg v-if="titleIcon === 'catalog'" viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <path d="M4 6H20" />
        <path d="M4 12H20" />
        <path d="M4 18H20" />
      </svg>
      <svg v-else-if="titleIcon === 'profiles'" viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <path d="M16 21V19C16 17.34 14.66 16 13 16H7C5.34 16 4 17.34 4 19V21" />
        <circle cx="10" cy="10" r="3" />
        <path d="M20 8V14" />
        <path d="M23 11H17" />
      </svg>
      <svg v-else-if="titleIcon === 'stacks'" viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <path d="M12 3L3 8L12 13L21 8L12 3Z" />
        <path d="M3 12L12 17L21 12" />
        <path d="M3 16L12 21L21 16" />
      </svg>
      <svg v-else-if="titleIcon === 'layers'" viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <rect x="4" y="4" width="7" height="7" rx="1.5" />
        <rect x="13" y="4" width="7" height="7" rx="1.5" />
        <rect x="4" y="13" width="7" height="7" rx="1.5" />
        <rect x="13" y="13" width="7" height="7" rx="1.5" />
      </svg>
      <svg v-else-if="titleIcon === 'settings'" viewBox="0 0 24 24" class="page-title-icon" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15A1.66 1.66 0 0 0 19.73 16.82L19.79 16.88A2 2 0 1 1 16.96 19.71L16.9 19.65A1.66 1.66 0 0 0 15.08 19.32A1.66 1.66 0 0 0 14 20.85V21A2 2 0 1 1 10 21V20.91A1.66 1.66 0 0 0 8.92 19.38A1.66 1.66 0 0 0 7.1 19.71L7.04 19.77A2 2 0 1 1 4.21 16.94L4.27 16.88A1.66 1.66 0 0 0 4.6 15.06A1.66 1.66 0 0 0 3.07 14H3A2 2 0 1 1 3 10H3.09A1.66 1.66 0 0 0 4.62 8.92A1.66 1.66 0 0 0 4.29 7.1L4.23 7.04A2 2 0 1 1 7.06 4.21L7.12 4.27A1.66 1.66 0 0 0 8.94 4.6H9A1.66 1.66 0 0 0 10 3.09V3A2 2 0 1 1 14 3V3.09A1.66 1.66 0 0 0 15.08 4.62A1.66 1.66 0 0 0 16.9 4.29L16.96 4.23A2 2 0 1 1 19.79 7.06L19.73 7.12A1.66 1.66 0 0 0 19.4 8.94V9A1.66 1.66 0 0 0 20.93 10H21A2 2 0 1 1 21 14H20.91A1.66 1.66 0 0 0 19.38 15Z" />
      </svg>
      <span>{{ title }}</span>
    </h1>
    <div class="page-entity-table-toolbar">
      <div class="page-entity-table-toolbar-left">
        <button
          v-if="createLabel"
          class="btn page-entity-table-circle-btn"
          @click="$emit('create')"
          :title="createLabel"
          :aria-label="createLabel"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 5V19" />
            <path d="M5 12H19" />
          </svg>
        </button>
        <button class="btn page-entity-table-circle-btn" @click="$emit('refresh')" title="Refresh" aria-label="Refresh">
          <IconReload />
        </button>
      </div>
      <input
        v-model="searchQuery"
        type="text"
        class="page-entity-table-search"
        placeholder="Search..."
        aria-label="Search table rows"
      />
    </div>

    <div class="card">
      <div v-if="loading" class="empty-state">{{ loadingMessage }}</div>
      <div v-else-if="errorMessage" class="auth-warning">{{ errorMessage }}</div>
      <div v-else-if="filteredRows.length === 0" class="empty-state">{{ computedEmptyMessage }}</div>
      <div v-else class="page-entity-table-wrap">
        <table class="page-entity-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col.key" scope="col" :style="columnStyle(col)">{{ col.label }}</th>
              <th v-if="showActions" scope="col" :style="actionsColumnStyle">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredRows" :key="String(row[idKey])">
              <td
                v-for="col in columns"
                :key="`${String(row[idKey])}-${col.key}`"
                :style="columnStyle(col)"
                :class="{ 'page-entity-table-cell-truncate-td': col.truncate }"
              >
                <span
                  class="page-entity-table-cell-text"
                  :class="{
                    'page-entity-table-cell-multiline': col.multiline,
                    'page-entity-table-cell-truncate': col.truncate,
                    'page-entity-table-cell-badge': col.badge,
                    badge: col.badge,
                    [`badge-${String(row[col.key] ?? '').toLowerCase()}`]: col.badge,
                  }"
                  :data-tooltip="String(row[col.key] ?? '')"
                >
                  {{ row[col.key] }}
                </span>
              </td>
              <td v-if="showActions" class="page-entity-table-actions-cell" :style="actionsColumnStyle">
                <div class="page-entity-table-actions">
                  <button
                    v-if="showView && hasViewTarget(row) && onView"
                    class="btn btn-icon"
                    title="View"
                    aria-label="View"
                    @click="onView(row)"
                  >
                    <IconEye />
                  </button>
                  <router-link
                    v-else-if="showView && hasViewTarget(row)"
                    class="btn btn-icon"
                    :to="resolveViewTo(row)"
                    title="View"
                    aria-label="View"
                  >
                    <IconEye />
                  </router-link>
                  <button
                    v-if="showEdit && onEdit"
                    class="btn btn-icon"
                    title="Edit"
                    aria-label="Edit"
                    @click="onEdit(row)"
                  >
                    <IconPen />
                  </button>
                  <router-link
                    v-else-if="showEdit"
                    class="btn btn-icon"
                    :to="`${routeBase}/${row[idKey]}/edit`"
                    title="Edit"
                    aria-label="Edit"
                  >
                    <IconPen />
                  </router-link>
                  <button
                    v-if="showRetry && isRowRetryable(row)"
                    class="btn btn-icon"
                    :title="retryingId === getRetryId(row) ? 'Starting...' : 'Retry'"
                    :aria-label="retryingId === getRetryId(row) ? 'Starting...' : 'Retry'"
                    :disabled="retryingId === getRetryId(row)"
                    @click="$emit('retry', getRetryId(row))"
                  >
                    <IconReload :class="{ 'icon-spin': retryingId === getRetryId(row) }" />
                  </button>
                  <button
                    v-if="showDelete && isRowDeletable(row)"
                    class="btn btn-icon btn-danger"
                    :title="deletingId === String(row[idKey]) ? 'Deleting...' : 'Delete'"
                    :aria-label="deletingId === String(row[idKey]) ? 'Deleting...' : 'Delete'"
                    :disabled="deletingId === String(row[idKey])"
                    @click="$emit('delete', String(row[idKey]))"
                  >
                    <IconTrash />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import IconEye from '@/components/icons/IconEye.vue'
import IconPen from '@/components/icons/IconPen.vue'
import IconTrash from '@/components/icons/IconTrash.vue'
import IconReload from '@/components/icons/IconReload.vue'

type TableColumn = {
  key: string
  label: string
  width?: string
  multiline?: boolean
  truncate?: boolean
  badge?: boolean
}
type RowData = Record<string, string | number | null | undefined>

const props = withDefaults(defineProps<{
  title: string
  titleIcon?: 'catalog' | 'profiles' | 'stacks' | 'layers' | 'settings'
  createLabel?: string
  loading: boolean
  loadingMessage?: string
  emptyMessage: string
  errorMessage?: string | null
  rows: RowData[]
  columns: TableColumn[]
  routeBase?: string
  viewPathKey?: string
  /** When provided, View button calls onView(row) instead of navigating. */
  onView?: (row: RowData) => void
  /** When provided, Edit button calls onEdit(row) instead of navigating. */
  onEdit?: (row: RowData) => void
  idKey?: string
  showView?: boolean
  showEdit?: boolean
  showDelete?: boolean
  /** When provided, only rows where deletable(row) is true show the Delete button. */
  deletable?: (row: RowData) => boolean
  deletingId?: string | null
  showRetry?: boolean
  /** When provided, only rows where retryable(row) is true show the Retry button. */
  retryable?: (row: RowData) => boolean
  /** Key to use for retry id (e.g. 'job_id'). Defaults to idKey. */
  retryIdKey?: string
  retryingId?: string | null
}>(), {
  loadingMessage: 'Loading...',
  errorMessage: null,
  routeBase: '',
  idKey: 'id',
  showView: true,
  showEdit: true,
  showDelete: false,
  deletable: undefined,
  deletingId: null,
  showRetry: false,
  retryable: undefined,
  retryIdKey: undefined,
  retryingId: null,
})

function isRowDeletable(row: RowData): boolean {
  return props.deletable ? props.deletable(row) : true
}

function isRowRetryable(row: RowData): boolean {
  return props.retryable ? props.retryable(row) : true
}

function getRetryId(row: RowData): string {
  const key = props.retryIdKey || props.idKey
  return String(row[key] ?? '')
}

const showActions = computed(() =>
  props.showView || props.showEdit || props.showDelete || props.showRetry,
)
const searchQuery = ref('')
const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return props.rows
  return props.rows.filter((row) =>
    Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(query)),
  )
})
const computedEmptyMessage = computed(() =>
  searchQuery.value.trim() ? 'No matching rows.' : props.emptyMessage,
)
const actionButtonCount = computed(() =>
  Number(Boolean(props.showView)) +
  Number(Boolean(props.showEdit)) +
  Number(Boolean(props.showDelete)) +
  Number(Boolean(props.showRetry)),
)
const actionsColumnStyle = computed(() => {
  const count = actionButtonCount.value
  if (count <= 0) return {}
  if (count === 1) return { minWidth: '2.5rem', width: '1%' }
  if (count === 2) return { minWidth: '5rem', width: '1%' }
  if (count === 3) return { minWidth: '7.5rem', width: '1%' }
  return { minWidth: '10rem', width: '1%' }
})

function hasViewTarget(row: RowData): boolean {
  if (props.viewPathKey) {
    const value = row[props.viewPathKey]
    return typeof value === 'string' && value.trim().length > 0
  }
  return props.routeBase.trim().length > 0
}

function resolveViewTo(row: RowData): string {
  if (props.viewPathKey) {
    const value = row[props.viewPathKey]
    if (typeof value === 'string' && value.trim().length > 0) return value
  }
  return `${props.routeBase}/${row[props.idKey]}`
}

function columnStyle(col: TableColumn): Record<string, string> {
  if (!col.width) return {}
  const style: Record<string, string> = {
    width: col.width,
  }
  if (col.truncate) {
    style.maxWidth = col.width
  }
  return style
}

defineEmits<{
  create: []
  refresh: []
  delete: [id: string]
  retry: [id: string]
}>()
</script>

<style scoped>
.page-entity-table-toolbar {
  margin-bottom: 1rem;
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: nowrap;
}

.page-entity-table-toolbar-left {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex-shrink: 0;
}

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

.page-entity-table-circle-btn {
  width: 2rem;
  min-width: 2rem;
  height: 2rem;
  padding: 0.35rem;
  border-radius: 999px;
}

.page-entity-table-circle-btn svg {
  width: 1rem;
  height: 1rem;
  stroke: currentColor;
  stroke-width: 1.9;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.page-entity-table-search {
  flex: 1;
  min-width: 0;
  border-radius: 9999px;
  padding-left: 0.9rem;
  padding-right: 0.9rem;
}

.page-entity-table {
  width: 100%;
  table-layout: auto;
}

.page-entity-table-wrap {
  overflow: auto;
}

.page-entity-table thead th {
  position: sticky;
  top: 0;
  background: var(--bg-secondary);
  z-index: 1;
}

.page-entity-table-cell-text {
  display: block;
  position: relative;
  width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.page-entity-table-cell-multiline {
  white-space: pre-line;
}

.page-entity-table-cell-truncate {
  display: block;
  width: 100%;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-entity-table-cell-truncate-td {
  overflow: visible;
}

.page-entity-table-cell-badge {
  display: inline-block;
  width: auto;
  white-space: nowrap;
  overflow-wrap: normal;
  word-break: normal;
}

.page-entity-table-cell-text::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.35rem 0.5rem;
  font-size: 0.75rem;
  line-height: 1.25;
  white-space: normal;
  overflow-wrap: anywhere;
  max-width: 420px;
  min-width: max-content;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
  transition-delay: 0s;
  pointer-events: none;
  z-index: 20;
}

.page-entity-table-cell-text::before {
  content: '';
  position: absolute;
  left: 10px;
  bottom: 100%;
  border: 6px solid transparent;
  border-top-color: var(--border);
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease;
  transition-delay: 0s;
  pointer-events: none;
  z-index: 20;
}

.page-entity-table-cell-text:hover::after,
.page-entity-table-cell-text:hover::before,
.page-entity-table-cell-text:focus-visible::after,
.page-entity-table-cell-text:focus-visible::before {
  opacity: 1;
  transform: translateY(0);
  transition-delay: 1s;
}

.page-entity-table-actions-cell {
  vertical-align: middle;
  white-space: nowrap;
}

.page-entity-table-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.page-entity-table-actions .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 2rem;
}

.page-entity-table-actions .btn-icon {
  width: 2rem;
  min-width: 2rem;
  padding: 0.35rem;
}

.page-entity-table-actions .btn-icon svg {
  flex-shrink: 0;
}

.icon-spin {
  animation: icon-spin 0.8s linear infinite;
}

@keyframes icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .page-entity-table-toolbar {
    flex-wrap: wrap;
  }

  .page-entity-table-search {
    min-width: 14rem;
  }
}
</style>
