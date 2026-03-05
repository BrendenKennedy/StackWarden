<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('cancel')">
      <div
        class="wizard-dialog modal-wizard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="stack-wizard-title"
        ref="dialogRef"
        @keydown="onKeydown"
      >
        <div class="wizard-header">
          <h3 id="stack-wizard-title">Guided Stack Setup</h3>
          <button class="btn" @click="$emit('cancel')">Close</button>
        </div>
        <div class="wizard-scroll">
        <p class="wizard-subtitle" aria-live="polite">
          Step {{ step }} of {{ totalSteps }} - {{ stepLabel }}
        </p>

        <div v-if="!authEnabled" class="wizard-warning">
          Auth is disabled. Create operations are unprotected. Set STACKWARDEN_WEB_TOKEN to enable authentication.
        </div>

        <div v-if="currentStep === 'build_strategy'" class="wizard-step">
          <h4>Build Strategy</h4>
          <div class="wizard-detail stack-warning-top-md">
            <p>Choose how this stack should be assembled. Optional override; empty uses resolver defaults.</p>
            <ul class="compact-list">
              <li><strong>pull</strong>: prefer prebuilt artifacts; faster when compatible images exist.</li>
              <li><strong>overlay</strong>: compose changes on a resolved base; for custom layer composition.</li>
              <li><strong>default</strong>: resolver chooses from stack/profile context.</li>
            </ul>
          </div>
          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Strategy</label>
            </div>
            <select v-model="form.build_strategy" name="build_strategy">
              <option value="">Use default strategy</option>
              <option v-for="v in buildStrategyOptions" :key="v" :value="v">
                {{ v }} - {{ describeBuildStrategy(v) }}
              </option>
            </select>
          </div>
        </div>

        <div v-if="currentLayerStep" class="wizard-step">
          <div class="wizard-detail stack-warning-top-md">
            <p><strong>Purpose:</strong> {{ currentLayerStep.purpose }}</p>
            <p><strong>When used:</strong> {{ currentLayerStep.whenUsed }}</p>
            <p v-if="currentLayerStep.id === 'system_runtime_layer'">
              This layer is required. Pick a concrete OS/runtime baseline.
            </p>
            <p v-else>Recommendations are guided only. You can skip this layer and continue.</p>
          </div>
          <div
            class="dependency-group"
          >
            <div class="dependency-group-header">
              <label class="wizard-label-inline">{{ currentLayerStep.label }}</label>
            </div>
            <div class="form-row">
              <select v-model="selectedByLayer[currentLayerStep.id]" class="stack-layer-select">
                <option value="">Select block</option>
                <option v-for="opt in currentLayerStep.options" :key="opt.id" :value="opt.id">
                  {{ opt.id }} - {{ opt.display_name }}
                </option>
              </select>
              <button class="btn" @click="addBlockFromLayer(currentLayerStep.id)" :disabled="!selectedByLayer[currentLayerStep.id]">Add</button>
            </div>
            <p v-if="currentLayerStep.options.length === 0" class="help help-gap-sm">
              No recommended blocks mapped for this layer yet.
            </p>
          </div>
          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Selected Blocks (ordered)</label>
            </div>
            <p v-if="form.blocks.length === 0" class="help">No blocks selected yet.</p>
            <div
              v-for="(blockId, index) in form.blocks"
              :key="`${blockId}-${index}`"
              class="form-row stack-block-row"
            >
              <code class="stack-block-code">{{ index + 1 }}. {{ blockId }}</code>
              <button class="btn" @click="moveBlockUp(index)" :disabled="index === 0">↑</button>
              <button class="btn" @click="moveBlockDown(index)" :disabled="index === form.blocks.length - 1">↓</button>
              <button class="btn dynamic-list-remove" @click="removeBlock(index)" title="Remove">&times;</button>
            </div>
          </div>
        </div>

        <div v-if="currentStep === 'review'" class="wizard-step">
          <h4>Review</h4>
          <div class="row two">
            <div>
              <label :class="{ required: isStackRequired('id') }">ID</label>
              <input
                type="text"
                v-model="form.id"
                @input="onIdInput"
                name="id"
                placeholder="my-new-stack"
                maxlength="64"
                autocapitalize="off"
                spellcheck="false"
              />
              <p v-if="idError" class="field-error">{{ idError }}</p>
            </div>
            <div>
              <label :class="{ required: isStackRequired('display_name') }">Display Name</label>
              <input type="text" name="display_name" v-model="form.display_name" placeholder="My New Stack" />
            </div>
          </div>
          <div class="row full">
            <label>Description</label>
            <textarea
              v-model="form.description"
              name="description"
              placeholder="What this stack does and why it exists (human-readable)"
              rows="3"
            />
          </div>
          <div class="wizard-info stack-warning-top-lg">
            <strong>Summary</strong>
            <ul class="compact-list">
              <li>Build strategy: {{ form.build_strategy || 'default' }}</li>
              <li>Inferred env vars: {{ inferredEnv.length }}</li>
              <li>Inferred ports: {{ inferredPorts.length }}</li>
              <li>Files copied: {{ form.copy_items.length }}</li>
            </ul>
          </div>
          <div v-if="composing" class="wizard-detail">Updating composed runtime preview...</div>
          <div v-if="dependencyConflicts.length || tupleConflicts.length || runtimeConflicts.length" class="wizard-error stack-warning-top-70">
            <strong>Compose Conflicts</strong>
            <ul v-if="dependencyConflicts.length" class="compact-list">
              <li v-for="(c, idx) in dependencyConflicts" :key="`dep-${idx}`">
                [{{ c.severity }}] {{ c.type }} {{ c.name }}: {{ c.existing }} -> {{ c.incoming }}
              </li>
            </ul>
            <ul v-if="tupleConflicts.length" class="compact-list">
              <li v-for="(c, idx) in tupleConflicts" :key="`tuple-${idx}`">
                [{{ c.severity }}] {{ c.name }}: {{ c.existing }} -> {{ c.incoming }}
              </li>
            </ul>
            <ul v-if="runtimeConflicts.length" class="compact-list">
              <li v-for="(c, idx) in runtimeConflicts" :key="`runtime-${idx}`">
                [{{ c.severity }}] {{ c.type }} {{ c.name }}: {{ c.existing }} -> {{ c.incoming }}
              </li>
            </ul>
          </div>
          <div class="wizard-detail stack-dependency-top">
            <strong>Inferred Runtime Output</strong>
            <p>Env vars: {{ inferredEnv.length }} · Ports: {{ inferredPorts.length ? inferredPorts.join(', ') : 'none' }} · Entrypoint: {{ inferredEntrypoint || 'none' }}</p>
            <ul v-if="inferredEnv.length" class="compact-list">
              <li v-for="entry in inferredEnv.slice(0, 10)" :key="entry">{{ entry }}</li>
            </ul>
          </div>
        </div>

        </div>
        <div class="wizard-footer">
          <button class="btn" @click="prevStep" :disabled="step === 1">Back</button>
          <div class="wizard-footer-right">
            <button v-if="step < totalSteps" class="btn btn-primary" @click="nextStep" :disabled="!canProceed">
              Next
            </button>
            <button v-else class="btn btn-primary" @click="$emit('complete')" :disabled="!canComplete">
              Continue to Confirm
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { BlockPresetCatalog, BlockSummary, CreateContractsResponse } from '@/api/types'
import { SPEC_ID_RE, sanitizeSpecIdInput } from '@/utils/specId'
import { inferLayersFromTags, STACK_LAYERS, type StackLayerId } from '@/utils/stackLayers'

const props = defineProps<{
  show: boolean
  form: {
    id: string
    display_name: string
    description: string
    build_strategy: string
    base_role: string
    blocks: string[]
    copy_items: Array<{ src: string; dst: string }>
    variants: Record<string, { type: 'bool' | 'enum'; options: string[]; default: string | boolean }>
  }
  availableBlocks: BlockSummary[]
  blockCatalog: BlockPresetCatalog | null
  createContracts: CreateContractsResponse | null
  authEnabled: boolean
  canCreate: boolean
  composing: boolean
  dependencyConflicts: Array<Record<string, string>>
  tupleConflicts: Array<Record<string, string>>
  runtimeConflicts: Array<Record<string, string>>
  resolvedSpec: Record<string, any> | null
}>()

const emit = defineEmits<{
  cancel: []
  complete: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
const step = ref(1)
const selectedByLayer = ref<Record<StackLayerId, string>>({
  hardware_layer: '',
  system_runtime_layer: '',
  driver_accelerator_layer: '',
  core_compute_layer: '',
  model_runtime_layer: '',
  optimization_compilation_layer: '',
  serving_layer: '',
  application_orchestration_layer: '',
  observability_operations_layer: '',
})

const inferredEnv = computed<string[]>(() => {
  const raw = props.resolvedSpec?.env
  return Array.isArray(raw) ? raw.map(v => String(v)) : []
})

const inferredPorts = computed<number[]>(() => {
  const raw = props.resolvedSpec?.ports
  return Array.isArray(raw) ? raw.map(v => Number(v)).filter(v => Number.isFinite(v)) : []
})

const inferredEntrypoint = computed<string>(() => {
  const cmd = props.resolvedSpec?.entrypoint?.cmd
  return Array.isArray(cmd) ? cmd.join(' ') : ''
})

const presetLayerById = computed<Record<string, StackLayerId[]>>(() => {
  const out: Record<string, StackLayerId[]> = {}
  for (const preset of props.blockCatalog?.presets || []) {
    const layers = Array.isArray(preset.layers) && preset.layers.length
      ? (preset.layers.filter(Boolean) as StackLayerId[])
      : inferLayersFromTags(preset.tags || [])
    out[preset.id] = layers
  }
  return out
})

const blockLayers = computed<Record<string, StackLayerId[]>>(() => {
  const out: Record<string, StackLayerId[]> = {}
  for (const block of props.availableBlocks) {
    const resolved = presetLayerById.value[block.id] || inferLayersFromTags(block.tags || [])
    // Keep a single primary layer in the wizard to avoid duplicate listing noise.
    out[block.id] = resolved.length ? [resolved[0]] : []
  }
  return out
})

const layerRows = computed(() => STACK_LAYERS.map(layer => {
  const options = props.availableBlocks.filter(block => (blockLayers.value[block.id] || []).includes(layer.id))
  return { ...layer, options }
}).filter(layer => !layer.profileManaged))
const stepKeys = computed(() => [
  'build_strategy',
  ...layerRows.value.map(layer => `layer:${layer.id}`),
  'review',
])
const totalSteps = computed(() => stepKeys.value.length)
const currentStep = computed(() => stepKeys.value[step.value - 1] || 'review')
const currentLayerStep = computed(() => {
  const key = currentStep.value
  if (!key.startsWith('layer:')) return null
  const id = key.slice('layer:'.length)
  return layerRows.value.find(layer => layer.id === id) || null
})
const stepLabel = computed(() => {
  if (currentStep.value === 'build_strategy') return 'Build Strategy'
  if (currentStep.value === 'review') return 'Review'
  return currentLayerStep.value?.label || 'Layer'
})
const buildStrategyOptions = computed(() =>
  props.createContracts?.stack?.fields?.build_strategy?.enum_values || ['overlay', 'pull'],
)

const idError = computed(() => {
  if (!props.form.id) return ''
  return SPEC_ID_RE.test(props.form.id)
    ? ''
    : 'Must be 3-64 chars, start with a lowercase letter, and use only lowercase letters, digits, hyphens, and underscores'
})

const canProceed = computed(() => {
  if (currentLayerStep.value?.id === 'system_runtime_layer') {
    const selected = selectedByLayer.value.system_runtime_layer
    const alreadyAdded = props.form.blocks.includes(selected) || props.form.blocks.some((blockId) => {
      const layers = blockLayers.value[blockId] || []
      return layers.includes('system_runtime_layer')
    })
    return Boolean(selected) || alreadyAdded
  }
  return true
})

const canComplete = computed(() => props.canCreate && !idError.value)

watch(
  () => props.show,
  async (open) => {
    if (!open) return
    step.value = 1
    for (const layer of STACK_LAYERS) selectedByLayer.value[layer.id] = ''
    await nextTick()
    focusFirst()
  },
)

function isStackRequired(field: string): boolean {
  const required = props.createContracts?.stack?.required_fields || []
  return required.includes(field) || required.includes(field.split('.')[0])
}

function onIdInput(event: Event) {
  const input = event.target as HTMLInputElement
  props.form.id = sanitizeSpecIdInput(input.value)
}

function describeBuildStrategy(value: string): string {
  if (value === 'pull') return 'Use pull-first strategy when compatible artifacts are available'
  if (value === 'overlay') return 'Compose overlay changes over a resolved baseline'
  return 'Use resolver defaults for this stack'
}

function addBlockFromLayer(layerId: StackLayerId) {
  const blockId = selectedByLayer.value[layerId]
  if (!blockId) return
  if (!props.form.blocks.includes(blockId)) {
    props.form.blocks.push(blockId)
  }
  selectedByLayer.value[layerId] = ''
}

function removeBlock(index: number) {
  if (index < 0 || index >= props.form.blocks.length) return
  props.form.blocks.splice(index, 1)
}

function moveBlockUp(index: number) {
  if (index <= 0) return
  const x = props.form.blocks[index - 1]
  props.form.blocks[index - 1] = props.form.blocks[index]
  props.form.blocks[index] = x
}

function moveBlockDown(index: number) {
  if (index >= props.form.blocks.length - 1) return
  const x = props.form.blocks[index + 1]
  props.form.blocks[index + 1] = props.form.blocks[index]
  props.form.blocks[index] = x
}

function nextStep() {
  if (currentStep.value === 'hardware' && props.form.blocks.length === 0) {
    for (const layer of layerRows.value) {
      const blockId = selectedByLayer.value[layer.id]
      if (!blockId) continue
      if (!props.form.blocks.includes(blockId)) props.form.blocks.push(blockId)
    }
  }
  if (currentLayerStep.value) {
    const blockId = selectedByLayer.value[currentLayerStep.value.id]
    if (blockId && !props.form.blocks.includes(blockId)) {
      props.form.blocks.push(blockId)
    }
  }
  if (!canProceed.value) return
  step.value = Math.min(totalSteps.value, step.value + 1)
  nextTick(focusFirst)
}

function prevStep() {
  step.value = Math.max(1, step.value - 1)
  nextTick(focusFirst)
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
  const first = root.querySelector<HTMLElement>('input, select, button, textarea')
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
  width: min(980px, 95vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
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

.row {
  display: grid;
  gap: 0.75rem;
}

.row.two {
  grid-template-columns: repeat(2, minmax(180px, 1fr));
}

.row.full {
  grid-template-columns: 1fr;
}

.form-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
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

.wizard-step input,
.wizard-step select,
.wizard-step textarea {
  width: 100%;
}

.wizard-step textarea {
  resize: vertical;
  min-height: 4rem;
}

.help {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.field-error {
  color: var(--error);
  font-size: 0.75rem;
  margin-top: 0.2rem;
}

.dependency-group {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-tertiary);
  padding: 0.65rem 0.75rem 0.75rem;
  margin-top: 0.7rem;
}

.dependency-group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.variant-block {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75rem;
  margin-bottom: 0.5rem;
}

.wizard-footer {
  margin-top: 1rem;
  display: flex;
  justify-content: space-between;
}

.wizard-footer-right {
  display: flex;
  gap: 0.5rem;
}

.wizard-label-inline {
  margin: 0;
}

.stack-warning-bottom {
  margin-bottom: 0.6rem;
}

.help-gap-xs {
  margin-top: 0.2rem;
}

.help-gap-sm {
  margin-top: 0.35rem;
}

.help-gap-md {
  margin-top: 0.5rem;
}

.help-gap-mid {
  margin-top: 0.4rem;
}

.help-gap-compose {
  margin-top: 0.45rem;
}

.stack-layer-select {
  min-width: 280px;
}

.stack-block-row {
  margin-top: 0.35rem;
}

.stack-block-code {
  flex: 1;
}

.stack-warning-top-md {
  margin-top: 0.45rem;
}

.stack-warning-top-lg {
  margin-top: 0.75rem;
}

.stack-warning-top-70 {
  margin-top: 0.7rem;
}

.stack-dependency-top {
  margin-top: 0.7rem;
}
</style>
