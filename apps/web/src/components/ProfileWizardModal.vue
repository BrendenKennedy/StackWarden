<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('cancel')">
      <div
        class="wizard-dialog modal-wizard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="profile-wizard-title"
        ref="dialogRef"
        @keydown="onKeydown"
      >
        <div class="wizard-header">
          <h3 id="profile-wizard-title">Guided Profile Setup</h3>
          <button class="btn" @click="$emit('cancel')">Close</button>
        </div>

        <p class="wizard-subtitle" aria-live="polite">
          Step {{ step }} of {{ totalSteps }} — {{ stepLabel }}
        </p>

        <div v-if="currentStep === 'hardware'" class="wizard-step">
          <h4>Hardware</h4>
          <div class="hardware-actions">
            <button class="btn btn-primary" :disabled="detectingHints" @click="autofillHardware">
              {{ detectingHints ? 'Detecting...' : 'Detect & Autofill Hardware' }}
            </button>
            <p class="help">
              Detection pre-fills fields from the StackWarden server host. You can still edit any value manually.
            </p>
          </div>
          <div v-if="dependencyIssues.length > 0" class="wizard-warning">
            Missing or inaccessible detection dependencies:
            <ul class="compact-list">
              <li v-for="issue in dependencyIssues" :key="issue.key">
                <strong>{{ issue.label }}</strong>: {{ issue.reason }}
                <a :href="issue.docs" target="_blank" rel="noopener noreferrer">Docs</a>
              </li>
            </ul>
          </div>
          <label class="required">Architecture</label>
          <select v-model="form.arch" @change="handleSelectChange('arch')">
            <option value="">Select arch</option>
            <option v-for="v in enums.arch" :key="v" :value="v">{{ v }}</option>
            <option :value="ADD_CUSTOM_VALUE">+ Add your own architecture...</option>
          </select>
          <label class="required">Container Runtime</label>
          <select v-model="form.container_runtime" @change="handleSelectChange('container_runtime')">
            <option value="">Select runtime</option>
            <option v-for="v in enums.container_runtime" :key="v" :value="v">{{ v }}</option>
            <option :value="ADD_CUSTOM_VALUE">+ Add your own runtime...</option>
          </select>
          <label>OS Family</label>
          <select v-model="form.os_family_id" @change="handleSelectChange('os_family_id')">
            <option value="">Select OS family</option>
            <option v-for="v in catalogs?.os_family || []" :key="v.id" :value="v.id">{{ v.label }}</option>
            <option :value="ADD_CUSTOM_VALUE">+ Add your own OS family...</option>
          </select>
          <label>OS Version</label>
          <select v-model="form.os_version_id" @change="handleSelectChange('os_version_id')">
            <option value="">Select OS version</option>
            <option v-for="v in osVersionOptions" :key="v.id" :value="v.id">{{ v.label }}</option>
            <option :value="ADD_CUSTOM_VALUE">+ Add your own OS version...</option>
          </select>
          <div class="row">
            <div>
              <label>GPU Vendor</label>
              <select v-model="form.gpu.vendor_id" @change="handleSelectChange('gpu.vendor_id')">
                <option value="">Select GPU vendor</option>
                <option v-for="v in catalogs?.gpu_vendor || []" :key="v.id" :value="v.id">{{ v.label }}</option>
                <option :value="ADD_CUSTOM_VALUE">+ Add your own GPU vendor...</option>
              </select>
            </div>
            <div>
              <label>GPU Family</label>
              <select v-model="form.gpu.family_id" @change="handleSelectChange('gpu.family_id')">
                <option value="">Select GPU family</option>
                <option v-for="v in gpuFamilyOptions" :key="v.id" :value="v.id">{{ v.label }}</option>
                <option :value="ADD_CUSTOM_VALUE">+ Add your own GPU family...</option>
              </select>
            </div>
            <div>
              <label>GPU Model</label>
              <select v-model="form.gpu.model_id" @change="handleSelectChange('gpu.model_id')">
                <option value="">Select GPU model</option>
                <option v-for="v in gpuModelOptions" :key="v.id" :value="v.id">{{ v.label }}</option>
                <option :value="ADD_CUSTOM_VALUE">+ Add your own GPU model...</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="currentStep === 'review'" class="wizard-step">
          <h4>Review</h4>
          <p class="help">
            Confirm identity and hardware summary before dry-run and confirm write.
          </p>
          <div class="wizard-warning">
            <strong>Tuple Preflight</strong>
            <ul class="compact-list">
              <li>Status: {{ tupleReadiness }}</li>
              <li>Arch/runtime/vendor: {{ form.arch || '-' }} / {{ form.container_runtime || '-' }} / {{ form.gpu.vendor_id || form.gpu.vendor || '-' }}</li>
            </ul>
          </div>
          <label :class="{ required: requiresField('display_name') }">Display Name</label>
          <input
            v-model="form.display_name"
            @input="onDisplayNameInput"
            type="text"
            placeholder="My New Profile"
          />
          <label :class="{ required: requiresField('id') }">ID</label>
          <input
            v-model="form.id"
            @input="onIdInput"
            type="text"
            placeholder="my-new-profile"
            maxlength="64"
            autocapitalize="off"
            spellcheck="false"
          />
          <p v-if="idError" class="field-error">{{ idError }}</p>
          <div class="wizard-warning profile-summary-warning">
            <strong>Summary</strong>
            <ul class="compact-list">
              <li>Arch: {{ form.arch || '-' }}</li>
              <li>Runtime: {{ form.container_runtime || '-' }}</li>
              <li>OS family/version: {{ form.os_family_id || '-' }} / {{ form.os_version_id || '-' }}</li>
              <li>GPU vendor/family/model: {{ form.gpu.vendor_id || '-' }} / {{ form.gpu.family_id || '-' }} / {{ form.gpu.model_id || '-' }}</li>
            </ul>
          </div>
        </div>

        <div class="wizard-footer">
          <button class="btn" @click="prevStep" :disabled="step === 1">Back</button>
          <button v-if="step < totalSteps" class="btn btn-primary" @click="nextStep" :disabled="!canProceed">
            Next
          </button>
          <button v-else class="btn btn-primary" @click="$emit('complete')" :disabled="!canProceed">
            Continue to Confirm
          </button>
        </div>

        <div v-if="customModal.open" class="coming-soon-backdrop" @click.self="closeCustomModal">
          <div class="coming-soon-modal" role="dialog" aria-modal="true" aria-labelledby="custom-entry-title">
            <h4 id="custom-entry-title">Add custom option — coming soon</h4>
            <p>
              Custom catalog entry is planned for a follow-up release. You will be able to add a new
              <strong>{{ customModal.catalogLabel }}</strong>
              with IDs, labels, aliases, and parent linkage directly from this flow.
            </p>
            <p class="help">
              For now, choose one of the predefined options from the dropdown.
            </p>
            <div class="coming-soon-actions">
              <button class="btn btn-primary" @click="closeCustomModal">Got it</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type {
  CreateContractsResponse,
  DetectionHints,
  EnumsMeta,
  HardwareCatalog,
  ProfileCreatePayload,
} from '@/api/types'
import { SPEC_ID_RE, sanitizeSpecIdInput } from '@/utils/specId'
const props = defineProps<{
  show: boolean
  form: ProfileCreatePayload
  enums: EnumsMeta
  hints: DetectionHints | null
  detectingHints?: boolean
  detectHardware?: () => Promise<DetectionHints | null> | DetectionHints | null | void
  contracts: CreateContractsResponse | null
  catalogs: HardwareCatalog | null
}>()

const emit = defineEmits<{
  cancel: []
  complete: []
}>()

const ADD_CUSTOM_VALUE = '__add_custom__'
const dialogRef = ref<HTMLElement | null>(null)
const step = ref(1)
const previousSelections = ref<Record<string, string>>({})
const customModal = ref<{ open: boolean; catalog: string; catalogLabel: string }>({
  open: false,
  catalog: '',
  catalogLabel: '',
})
const wizardSteps = computed(() => ['hardware', 'review'])
const totalSteps = computed(() => wizardSteps.value.length)
const currentStep = computed(() => wizardSteps.value[step.value - 1] || 'review')

const stepLabel = computed(() => {
  const labels: Record<string, string> = {
    hardware: 'Hardware',
    review: 'Review',
  }
  return labels[currentStep.value] || 'Review'
})

const idError = computed(() => {
  if (!props.form.id) return ''
  return SPEC_ID_RE.test(props.form.id)
    ? ''
    : 'Must be 3–64 chars, start with a lowercase letter, and use only lowercase letters, digits, hyphens, and underscores'
})

const canProceed = computed(() => {
  const required = new Set(props.contracts?.profile?.required_fields || [])
  if (currentStep.value === 'hardware') {
    if (required.has('arch') && !props.form.arch) return false
    if (required.has('container_runtime') && !props.form.container_runtime) return false
    return true
  }
  if (currentStep.value === 'review') {
    if (required.has('id') && !props.form.id) return false
    if (required.has('id') && !!idError.value) return false
    if (required.has('display_name') && !props.form.display_name) return false
    return true
  }
  if (step.value === totalSteps.value) {
    return true
  }
  return true
})
const tupleReadiness = computed(() => {
  if (props.form.arch && props.form.container_runtime && (props.form.gpu.vendor_id || props.form.gpu.vendor)) {
    return 'Ready for tuple resolution.'
  }
  return 'Incomplete tuple facts; resolver may warn or fall back.'
})

watch(
  () => props.show,
  async (open) => {
    if (!open) return
    step.value = 1
    previousSelections.value = snapshotSelections()
    customModal.value = { open: false, catalog: '', catalogLabel: '' }
    await nextTick()
    focusFirst()
  },
)

function nextStep() {
  if (!canProceed.value) return
  step.value = Math.min(totalSteps.value, step.value + 1)
  nextTick(focusFirst)
}

function onIdInput(event: Event) {
  const input = event.target as HTMLInputElement
  props.form.id = sanitizeSpecIdInput(input.value)
}

function suggestedIdFromDisplayName(value: string): string {
  const compact = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  const candidate = compact && /^[a-z]/.test(compact) ? compact : `p_${compact || 'profile'}`
  return sanitizeSpecIdInput(candidate)
}

function onDisplayNameInput(event: Event) {
  const input = event.target as HTMLInputElement
  props.form.display_name = input.value
  if (!props.form.id.trim()) {
    props.form.id = suggestedIdFromDisplayName(props.form.display_name)
  }
}

function prevStep() {
  step.value = Math.max(1, step.value - 1)
  nextTick(focusFirst)
}

function requiresField(field: string): boolean {
  const required = new Set(props.contracts?.profile?.required_fields || [])
  return required.has(field)
}

function snapshotSelections(): Record<string, string> {
  return {
    arch: props.form.arch || '',
    container_runtime: props.form.container_runtime || '',
    os_family_id: props.form.os_family_id || '',
    os_version_id: props.form.os_version_id || '',
    'gpu.vendor_id': props.form.gpu.vendor_id || '',
    'gpu.family_id': props.form.gpu.family_id || '',
    'gpu.model_id': props.form.gpu.model_id || '',
  }
}

function setFieldValue(field: string, value: string) {
  if (field === 'arch') props.form.arch = value
  else if (field === 'container_runtime') props.form.container_runtime = value
  else if (field === 'os_family_id') props.form.os_family_id = value
  else if (field === 'os_version_id') props.form.os_version_id = value
  else if (field === 'gpu.vendor_id') props.form.gpu.vendor_id = value
  else if (field === 'gpu.family_id') props.form.gpu.family_id = value
  else if (field === 'gpu.model_id') props.form.gpu.model_id = value
}

function getFieldLabel(field: string): string {
  const labels: Record<string, string> = {
    arch: 'architecture',
    container_runtime: 'container runtime',
    os_family_id: 'OS family',
    os_version_id: 'OS version',
    'gpu.vendor_id': 'GPU vendor',
    'gpu.family_id': 'GPU family',
    'gpu.model_id': 'GPU model',
  }
  return labels[field] || field
}

function handleSelectChange(field: string) {
  const currentValue = snapshotSelections()[field]
  if (currentValue === ADD_CUSTOM_VALUE) {
    const previous = previousSelections.value[field] || ''
    setFieldValue(field, previous)
    customModal.value = {
      open: true,
      catalog: field,
      catalogLabel: getFieldLabel(field),
    }
    return
  }
  previousSelections.value[field] = currentValue
}

function closeCustomModal() {
  customModal.value = { open: false, catalog: '', catalogLabel: '' }
}

const detectingHints = computed(() => Boolean(props.detectingHints))
function resolveCatalogId(
  items: Array<{ id: string; label: string; aliases?: string[]; parent_id?: string | null }>,
  raw: string | null | undefined,
  parentId?: string | null,
): string | null {
  if (!raw) return null
  const needle = raw.trim().toLowerCase()
  if (!needle) return null
  const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
  const needleNorm = normalize(needle)
  const scoped = parentId ? items.filter(i => !i.parent_id || i.parent_id === parentId) : items
  const exact = scoped.find(i => i.id.toLowerCase() === needle || i.label.toLowerCase() === needle)
  if (exact) return exact.id
  const alias = scoped.find(i => (i.aliases || []).some(a => a.toLowerCase() === needle))
  if (alias) return alias.id
  const fuzzy = scoped.find(i => {
    const candidates = [i.id, i.label, ...(i.aliases || [])]
    return candidates.some(c => {
      const cn = normalize(String(c))
      if (!cn) return false
      return needleNorm.includes(cn) || cn.includes(needleNorm)
    })
  })
  return fuzzy?.id || null
}

const osVersionOptions = computed(() =>
  (props.catalogs?.os_version || []).filter(v => !v.parent_id || v.parent_id === props.form.os_family_id),
)
const gpuFamilyOptions = computed(() =>
  (props.catalogs?.gpu_family || []).filter(v => !v.parent_id || v.parent_id === props.form.gpu.vendor_id),
)
const gpuModelOptions = computed(() =>
  (props.catalogs?.gpu_model || []).filter(v => !v.parent_id || v.parent_id === props.form.gpu.family_id),
)
const dependencyIssues = computed(() => {
  const hints = props.hints
  if (!hints) return []
  const probes = hints.probes || []
  const getProbe = (name: string) => probes.find(p => p.name === name)
  const issues: Array<{ key: string; label: string; reason: string; docs: string }> = []

  const nvidiaProbe = getProbe('nvidia_smi')
  if (nvidiaProbe?.status === 'warn') {
    const skipped = nvidiaProbe.message.includes('Skipped by capability/OS gate')
    issues.push({
      key: 'nvidia_smi',
      label: 'nvidia-smi',
      reason: skipped
        ? 'Tool is not available on the server host PATH, so GPU/driver/CUDA facts cannot be read.'
        : `Probe warning: ${nvidiaProbe.message || 'nvidia-smi could not run on this host.'}`,
      docs: 'https://docs.nvidia.com/deploy/nvidia-smi/',
    })
  }

  const dockerProbe = getProbe('docker')
  if (dockerProbe?.status === 'warn') {
    const skipped = dockerProbe.message.includes('Skipped by capability/OS gate')
    issues.push({
      key: 'docker',
      label: 'Docker Engine',
      reason: skipped
        ? 'Docker CLI/socket was not detected, so runtime facts may be incomplete.'
        : `Probe warning: ${dockerProbe.message || 'Docker daemon could not be queried.'}`,
      docs: 'https://docs.docker.com/engine/install/ubuntu/',
    })
  }

  if (hints.container_runtime === 'nvidia' && !hints.gpu) {
    issues.push({
      key: 'nvidia_toolkit',
      label: 'NVIDIA Container Toolkit',
      reason:
        'Runtime is set to nvidia, but no GPU facts were detected. Verify toolkit/driver wiring and device visibility.',
      docs: 'https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html',
    })
  }

  return issues
})

async function autofillHardware() {
  let latestHints: DetectionHints | null | undefined
  if (props.detectHardware) {
    const detected = await props.detectHardware()
    if (detected) latestHints = detected
    await nextTick()
  }
  applyHintsInternal(latestHints || props.hints)
}

function applyHintsInternal(hints: DetectionHints | null | undefined) {
  if (!hints) return
  if (hints.arch) props.form.arch = hints.arch
  if (hints.os) props.form.os = hints.os
  props.form.os_family_id = hints.resolved_ids?.os_family_id
    || resolveCatalogId(props.catalogs?.os_family || [], hints.os_family)
    || props.form.os_family_id
  props.form.os_version_id = hints.resolved_ids?.os_version_id
    || resolveCatalogId(props.catalogs?.os_version || [], hints.os_version, props.form.os_family_id)
    || props.form.os_version_id
  if (hints.container_runtime) {
    props.form.container_runtime = hints.container_runtime
  }
  if (hints.gpu) {
    props.form.gpu.vendor = hints.gpu.vendor
    props.form.gpu.family = hints.gpu.family
  }
  props.form.gpu.vendor_id = hints.resolved_ids?.gpu_vendor_id
    || resolveCatalogId(props.catalogs?.gpu_vendor || [], hints.gpu?.vendor)
    || props.form.gpu.vendor_id
  props.form.gpu.family_id = hints.resolved_ids?.gpu_family_id
    || resolveCatalogId(props.catalogs?.gpu_family || [], hints.gpu?.family, props.form.gpu.vendor_id)
    || props.form.gpu.family_id
  if (hints.resolved_ids?.gpu_model_id) {
    props.form.gpu.model_id = hints.resolved_ids.gpu_model_id
  }

  // If only model is resolved, derive parent family/vendor IDs for dropdowns.
  if (!props.form.gpu.family_id && props.form.gpu.model_id) {
    const model = (props.catalogs?.gpu_model || []).find(m => m.id === props.form.gpu.model_id)
    if (model?.parent_id) props.form.gpu.family_id = model.parent_id
  }
  if (!props.form.gpu.vendor_id && props.form.gpu.family_id) {
    const family = (props.catalogs?.gpu_family || []).find(f => f.id === props.form.gpu.family_id)
    if (family?.parent_id) props.form.gpu.vendor_id = family.parent_id
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    emit('cancel')
    return
  }
  if (e.key !== 'Tab') return
  const root = dialogRef.value
  if (!root) return
  const focusables = Array.from(
    root.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    ),
  ).filter(el => !el.hasAttribute('disabled'))
  if (!focusables.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

function focusFirst() {
  const root = dialogRef.value
  if (!root) return
  const first = root.querySelector<HTMLElement>('input, select, button')
  first?.focus()
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9200;
}

.wizard-dialog {
  width: min(820px, 92vw);
  max-height: 86vh;
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
}

.wizard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.wizard-subtitle {
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
  font-size: 0.8125rem;
}

.wizard-step label {
  display: block;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-top: 0.6rem;
  margin-bottom: 0.2rem;
}

.wizard-step .required::after {
  content: ' *';
  color: var(--error);
}

.field-error {
  margin-top: 0.25rem;
  color: var(--error);
  font-size: 0.75rem;
}

.wizard-step input,
.wizard-step select {
  width: 100%;
}

.row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
}

.hardware-actions {
  margin-bottom: 0.6rem;
}

.hint-grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 0.25rem 0.75rem;
  margin-bottom: 0.75rem;
}

.help {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.wizard-warning {
  background: #3b2e10;
  border: 1px solid var(--warning);
  border-radius: var(--radius);
  padding: 0.5rem 0.75rem;
  color: var(--warning);
  font-size: 0.8rem;
  margin-bottom: 0.65rem;
}

.hints-more {
  margin-bottom: 0.5rem;
  font-size: 0.8rem;
}

.compact-list {
  margin: 0.35rem 0 0 1rem;
  padding: 0;
}

.wizard-footer {
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
}

.coming-soon-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: grid;
  place-items: center;
  z-index: 9300;
}

.coming-soon-modal {
  width: min(480px, 92vw);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
}

.coming-soon-actions {
  margin-top: 0.75rem;
  display: flex;
  justify-content: flex-end;
}

.profile-summary-warning {
  margin-top: 0.75rem;
}
</style>
