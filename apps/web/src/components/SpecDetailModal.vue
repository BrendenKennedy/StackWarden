<template>
  <Teleport to="body">
  <div
    v-if="show"
    class="spec-modal-overlay"
    @click.self="close"
    @keydown="onKeydown"
  >
    <div ref="modalRef" class="spec-modal card" role="dialog" aria-modal="true" :aria-labelledby="`spec-modal-title-${entity}`">
      <div class="spec-modal-header">
        <h2 :id="`spec-modal-title-${entity}`" class="spec-modal-title">{{ title }}</h2>
        <div class="spec-modal-actions">
          <button v-if="id" class="btn btn-primary" @click="openEdit">Edit</button>
          <button class="btn" @click="close">Close</button>
        </div>
      </div>

      <div v-if="loading" class="empty-state">Loading...</div>
      <div v-else-if="errorMessage" class="auth-warning">{{ errorMessage }}</div>
      <div v-else-if="!data" class="empty-state">No data found.</div>
      <div v-else class="details-layout">
        <section class="details-section">
          <h3 class="section-title">Overview</h3>
          <dl class="detail-grid">
            <template v-for="item in overviewFields" :key="item.key">
              <dt>{{ item.label }}</dt>
              <dd>{{ formatValue(item.value) }}</dd>
            </template>
          </dl>
        </section>

        <section v-if="chipGroups.length > 0" class="details-section">
          <h3 class="section-title">Highlights</h3>
          <div v-for="group in chipGroups" :key="group.label" class="chip-group">
            <div class="chip-group-title">{{ group.label }}</div>
            <div class="pill-wrap">
              <span v-for="chip in group.values" :key="`${group.label}-${chip}`" class="fact-pill">
                {{ chip }}
              </span>
            </div>
          </div>
        </section>

        <section v-if="tableSections.length > 0" class="details-section">
          <h3 class="section-title">Tables</h3>
          <div v-for="table in tableSections" :key="table.label" class="table-section">
            <div class="table-title">{{ table.label }}</div>
            <table class="facts-table">
              <thead>
                <tr>
                  <th v-for="col in table.columns" :key="col">{{ col }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in table.rows" :key="`${table.label}-${idx}`">
                  <td v-for="col in table.columns" :key="`${table.label}-${idx}-${col}`">
                    {{ formatValue(row[col]) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="mapSections.length > 0" class="details-section">
          <h3 class="section-title">Mappings</h3>
          <div v-for="section in mapSections" :key="section.label" class="map-section">
            <div class="map-title">{{ section.label }}</div>
            <dl class="detail-grid">
              <template v-for="entry in section.entries" :key="`${section.label}-${entry.key}`">
                <dt>{{ entry.key }}</dt>
                <dd>{{ formatValue(entry.value) }}</dd>
              </template>
            </dl>
          </div>
        </section>

        <details class="raw-data">
          <summary>Raw Data</summary>
          <pre class="json-viewer">{{ pretty }}</pre>
        </details>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { blocks as blocksApi, profiles as profilesApi, stacks as stacksApi } from '@/api/endpoints'
import { toUserErrorMessage } from '@/utils/errors'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const props = defineProps<{
  show: boolean
  entity: 'profiles' | 'stacks' | 'blocks'
  id: string | null
}>()

const emit = defineEmits<{
  close: []
  edit: []
}>()

const modalRef = ref<HTMLElement | null>(null)
const { onKeydown } = useModalFocusTrap(modalRef, () => props.show, () => emit('close'))

const loading = ref(false)
const data = ref<any>(null)
const errorMessage = ref<string | null>(null)

const title = computed(() =>
  props.id ? `${props.entity.slice(0, -1)}: ${props.id}` : '',
)
const pretty = computed(() => JSON.stringify(data.value || {}, null, 2))

const overviewFields = computed(() => {
  const d = data.value || {}
  if (props.entity === 'profiles') {
    return [
      { key: 'id', label: 'ID', value: d.id },
      { key: 'display_name', label: 'Display Name', value: d.display_name },
      { key: 'arch', label: 'Arch', value: d.arch },
      { key: 'os', label: 'OS', value: d.os },
      { key: 'os_family', label: 'OS Family', value: d.os_family || d.os_family_id },
      { key: 'os_version', label: 'OS Version', value: d.os_version || d.os_version_id },
      { key: 'container_runtime', label: 'Runtime', value: d.container_runtime },
      { key: 'cuda', label: 'CUDA', value: d.cuda ? `${d.cuda.major}.${d.cuda.minor} (${d.cuda.variant})` : 'n/a' },
      { key: 'gpu', label: 'GPU', value: d.gpu ? `${d.gpu.vendor}/${d.gpu.family}` : 'n/a' },
    ]
  }
  if (props.entity === 'stacks') {
    return [
      { key: 'id', label: 'ID', value: d.id },
      { key: 'display_name', label: 'Display Name', value: d.display_name },
      { key: 'description', label: 'Description', value: d.description },
      { key: 'task', label: 'Task', value: d.task },
      { key: 'serve', label: 'Serve', value: d.serve },
      { key: 'api', label: 'API', value: d.api },
      { key: 'build_strategy', label: 'Build Strategy', value: d.build_strategy },
    ]
  }
  return [
    { key: 'id', label: 'ID', value: d.id },
    { key: 'display_name', label: 'Display Name', value: d.display_name },
    { key: 'description', label: 'Description', value: d.description },
    { key: 'build_strategy', label: 'Build Strategy', value: d.build_strategy || 'n/a' },
    { key: 'pip_count', label: 'Pip Count', value: d.pip_count },
    { key: 'apt_count', label: 'Apt Count', value: d.apt_count },
  ]
})

const chipGroups = computed(() => {
  const d = data.value || {}
  const groups: Array<{ label: string; values: string[] }> = []
  if (props.entity === 'profiles') {
    groups.push({ label: 'Derived Capabilities', values: (d.derived_capabilities || []).map(String) })
  } else if (props.entity === 'stacks') {
    groups.push({ label: 'Env', values: (d.env || []).map(String) })
    groups.push({ label: 'Ports', values: (d.ports || []).map((p: unknown) => String(p)) })
  } else {
    groups.push({ label: 'Tags', values: (d.tags || []).map(String) })
    groups.push({ label: 'Env', values: (d.env || []).map(String) })
    groups.push({ label: 'Ports', values: (d.ports || []).map((p: unknown) => String(p)) })
  }
  return groups.filter(g => g.values.length > 0)
})

const tableSections = computed(() => {
  const d = data.value || {}
  const tables: Array<{ label: string; columns: string[]; rows: Array<Record<string, unknown>> }> = []
  if (props.entity === 'profiles' && Array.isArray(d.base_candidates) && d.base_candidates.length > 0) {
    tables.push({
      label: 'Base Candidates',
      columns: ['name', 'tags', 'score_bias'],
      rows: d.base_candidates.map((c: any) => ({
        name: c.name,
        tags: Array.isArray(c.tags) ? c.tags.join(', ') : '',
        score_bias: c.score_bias,
      })),
    })
  }
  if (props.entity === 'stacks' && d.variants && typeof d.variants === 'object') {
    const rows = Object.entries(d.variants).map(([key, val]: [string, any]) => ({
      name: key,
      type: val?.type,
      options: Array.isArray(val?.options) ? val.options.join(', ') : '',
      default: val?.default,
    }))
    if (rows.length > 0) {
      tables.push({ label: 'Variants', columns: ['name', 'type', 'options', 'default'], rows })
    }
  }
  return tables
})

const mapSections = computed(() => {
  const d = data.value || {}
  const sections: Array<{ label: string; entries: Array<{ key: string; value: unknown }> }> = []
  if (props.entity === 'profiles') {
    const disallow = d.constraints?.disallow || {}
    const require = d.constraints?.require || {}
    if (Object.keys(disallow).length > 0) {
      sections.push({
        label: 'Constraints: Disallow',
        entries: Object.entries(disallow).map(([k, v]) => ({ key: k, value: Array.isArray(v) ? v.join(', ') : v })),
      })
    }
    if (Object.keys(require).length > 0) {
      sections.push({
        label: 'Constraints: Require',
        entries: Object.entries(require).map(([k, v]) => ({ key: k, value: Array.isArray(v) ? v.join(', ') : v })),
      })
    }
  } else if (props.entity === 'stacks' || props.entity === 'blocks') {
    if (d.policy_overrides && typeof d.policy_overrides === 'object') {
      sections.push({
        label: 'Tuple Policy Overrides',
        entries: Object.entries(d.policy_overrides).map(([k, v]) => ({ key: k, value: v })),
      })
    }
    const aptConstraints = d.components?.apt_constraints || {}
    if (aptConstraints && typeof aptConstraints === 'object' && Object.keys(aptConstraints).length > 0) {
      sections.push({
        label: 'Apt Constraints',
        entries: Object.entries(aptConstraints).map(([k, v]) => ({ key: k, value: v })),
      })
    }
  }
  return sections
})

async function fetchData() {
  if (!props.id) return
  loading.value = true
  errorMessage.value = null
  data.value = null
  try {
    if (props.entity === 'profiles') data.value = await profilesApi.getSpec(props.id)
    else if (props.entity === 'stacks') data.value = await stacksApi.getSpec(props.id)
    else data.value = await blocksApi.getSpec(props.id)
  } catch (err) {
    errorMessage.value = toUserErrorMessage(err)
  } finally {
    loading.value = false
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

function close() {
  emit('close')
}

function openEdit() {
  emit('edit')
}

watch(() => [props.show, props.entity, props.id] as const, ([show, , id]) => {
  if (show && id) {
    fetchData()
  } else {
    data.value = null
    errorMessage.value = null
  }
}, { immediate: true })
</script>

<style scoped>
.spec-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
}

.spec-modal {
  width: min(760px, 95vw);
  max-height: 90vh;
  overflow-y: auto;
}

.spec-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
  gap: var(--space-2);
}

.spec-modal-title {
  font-size: var(--font-size-lg);
  margin: 0;
}

.spec-modal-actions {
  display: flex;
  gap: var(--space-2);
}

.details-layout {
  display: grid;
  gap: 1rem;
}

.details-section {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem;
}

.section-title {
  margin: 0 0 0.6rem;
  font-size: 0.9rem;
  color: var(--accent);
}

.chip-group {
  margin-bottom: 0.55rem;
}

.chip-group-title {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.pill-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.fact-pill {
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  background: var(--bg-tertiary);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(170px, 220px) 1fr;
  gap: 0.25rem 0.75rem;
  margin: 0;
}

.detail-grid dt {
  color: var(--text-secondary);
}

.detail-grid dd {
  margin: 0;
}

.table-section + .table-section {
  margin-top: 0.7rem;
}

.table-title,
.map-title {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
}

.facts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.facts-table th,
.facts-table td {
  padding: 0.3rem 0.45rem;
  border: 1px solid var(--border);
  text-align: left;
}

.map-section + .map-section {
  margin-top: 0.7rem;
}

.raw-data summary {
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.82rem;
}

.raw-data .json-viewer {
  margin-top: 0.5rem;
}
</style>
