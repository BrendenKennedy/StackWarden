<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('cancel')">
      <div
        class="wizard-dialog modal-wizard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="block-wizard-title"
        ref="dialogRef"
        @keydown="onKeydown"
      >
        <div class="wizard-header">
          <h3 id="block-wizard-title">Guided Block Setup</h3>
          <button class="btn" @click="$emit('cancel')">Close</button>
        </div>
        <div class="wizard-scroll">
        <p class="wizard-subtitle" aria-live="polite">
          Step {{ step }} of {{ totalSteps }} - {{ stepLabel }}
        </p>

        <div v-if="currentStep === 'preset'" class="wizard-step">
          <h4>Preset Selection</h4>
          <div class="wizard-detail">
            <p>Presets auto-apply a coherent baseline. You can edit any field afterwards. Preset mode applies mode-specific env/requirements on top of the selected preset.</p>
          </div>
          <div class="featured-preset-wrap">
            <label>Featured Presets</label>
            <div class="featured-preset-list">
              <button
                v-for="preset in featuredPresets"
                :key="preset.id"
                type="button"
                class="btn featured-preset-btn"
                @click="selectFeaturedPreset(preset.id)"
              >
                {{ preset.display_name }}
              </button>
              <span v-if="!featuredPresets.length" class="help">No featured presets available for this filter.</span>
            </div>
          </div>
          <div class="row two">
            <div>
              <label>Category</label>
              <select v-model="selectedCategory">
                <option value="">All categories</option>
                <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ categoryLabel(cat.id, cat.label) }}</option>
              </select>
            </div>
            <div>
              <label>Filter Presets</label>
              <input v-model="searchTerm" type="text" placeholder="Filter by id, name, tags" />
            </div>
          </div>
          <div class="row two">
            <div>
              <label>Preset</label>
              <select v-model="selectedPresetId">
                <option value="">None (manual entry)</option>
                <option v-for="preset in availablePresets" :key="preset.id" :value="preset.id">
                  {{ preset.display_name }} ({{ preset.id }})
                </option>
              </select>
              <p class="help block-help-gap-sm">Showing {{ filteredPresetCount }} of {{ totalPresetCount }} presets.</p>
              <p v-if="filteredPresetCount === 0" class="field-error">
                No presets match your filter. Clear the filter or switch category.
              </p>
            </div>
            <div>
              <label>Preset Mode</label>
              <select v-model="selectedProfile">
                <option value="base">Base</option>
                <option value="cpu">CPU Optimized</option>
                <option value="gpu">GPU Optimized</option>
                <option value="dev">Developer</option>
                <option value="prod">Production</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="currentStep === 'runtime'" class="wizard-step">
          <h4>Dependencies and Runtime</h4>
          <div class="wizard-detail">
            <p>Defaults use latest compatible installs. Custom constraints are advanced; StackWarden validates syntax but does not guarantee cross-environment compatibility.</p>
          </div>
          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Tags</label>
            </div>
            <DynamicListEditor v-model="form.tags" add-label="Add tag" :default-item="() => ''">
              <template #default="{ index }">
                <input type="text" v-model="form.tags[index]" placeholder="tag" class="block-flex-input" />
              </template>
            </DynamicListEditor>
          </div>

          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Pip Dependencies</label>
              <button class="btn" type="button" @click="openPipImport">Import requirements.txt</button>
            </div>
            <input
              ref="pipImportInput"
              type="file"
              accept=".txt,.in,.pip,requirements*"
              class="wizard-hidden-input"
              @change="onPipImportSelected"
            />
            <DynamicListEditor
              v-model="form.pip"
              add-label="Add pip dependency"
              :default-item="() => ({ name: '', version: '', version_mode: 'latest', wheel_file_path: '' })"
            >
              <template #default="{ index }">
                <div class="block-grid-row">
                  <div class="block-inline-row">
                    <input type="text" v-model="form.pip[index].name" placeholder="Package name" class="block-flex-input" />
                    <select v-model="form.pip[index].version_mode" class="block-select-sm">
                      <option v-for="mode in pipVersionModes" :key="mode.value" :value="mode.value">{{ mode.label }}</option>
                    </select>
                    <input
                      type="text"
                      v-model="form.pip[index].version"
                      :disabled="(form.pip[index].version_mode || 'latest') !== 'custom'"
                      :placeholder="(form.pip[index].version_mode || 'latest') === 'custom' ? 'Version constraint' : ((form.pip[index].version_mode || 'latest') === 'wheel' ? 'Auto from wheel file' : 'Auto (latest)')"
                      class="block-select-lg"
                    />
                  </div>
                  <div v-if="(form.pip[index].version_mode || 'latest') === 'wheel'" class="block-inline-row">
                    <span class="help block-nowrap">Wheel File</span>
                    <input
                      type="text"
                      :value="form.pip[index].wheel_file_path || ''"
                      @input="setPipWheelFilePath(index, (($event.target as HTMLInputElement | null)?.value ?? ''))"
                      placeholder="wheels/flash_attn-2.7.4-cp310-cp310-linux_x86_64.whl"
                      class="block-flex-input"
                    />
                  </div>
                </div>
              </template>
            </DynamicListEditor>
          </div>

          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Node Dependencies (npm/pnpm/yarn)</label>
              <button class="btn" type="button" @click="openNpmImport">Import package.json</button>
            </div>
            <input
              ref="npmImportInput"
              type="file"
              accept=".json,package.json"
              class="wizard-hidden-input"
              @change="onNpmImportSelected"
            />
            <DynamicListEditor
              v-model="form.npm"
              add-label="Add node dependency"
              :default-item="() => ({ name: '', version: '', version_mode: 'latest', package_manager: 'npm', install_scope: 'prod' })"
            >
              <template #default="{ index }">
                <input type="text" v-model="form.npm[index].name" placeholder="Package name" class="block-flex-input" />
                <select v-model="form.npm[index].version_mode" class="block-select-sm">
                  <option v-for="mode in versionModes" :key="mode.value" :value="mode.value">{{ mode.label }}</option>
                </select>
                <input
                  type="text"
                  v-model="form.npm[index].version"
                  :disabled="(form.npm[index].version_mode || 'latest') !== 'custom'"
                  :placeholder="(form.npm[index].version_mode || 'latest') === 'custom' ? 'Version constraint' : 'Auto (latest)'"
                  class="block-select-lg"
                />
                <select v-model="form.npm[index].package_manager" class="block-select-xs">
                  <option v-for="pm in npmPackageManagers" :key="pm.value" :value="pm.value">{{ pm.label }}</option>
                </select>
                <select v-model="form.npm[index].install_scope" class="block-select-xs">
                  <option v-for="scope in npmInstallScopes" :key="scope.value" :value="scope.value">{{ scope.label }}</option>
                </select>
              </template>
            </DynamicListEditor>
          </div>
          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Apt Packages</label>
              <button class="btn" type="button" @click="openAptImport">Import apt list</button>
            </div>
            <input
              ref="aptImportInput"
              type="file"
              accept=".txt,.list,.cfg,.conf"
              class="wizard-hidden-input"
              @change="onAptImportSelected"
            />
            <DynamicListEditor v-model="form.apt" add-label="Add apt package" :default-item="() => ''">
              <template #default="{ index }">
                <input type="text" v-model="form.apt[index]" placeholder="package" class="block-flex-input" />
                <select
                  :value="aptVersionMode(form.apt[index])"
                  @change="setAptVersionMode(form.apt[index], ($event.target as HTMLSelectElement).value as DependencyVersionMode)"
                  class="block-select-sm"
                >
                  <option v-for="mode in versionModes" :key="mode.value" :value="mode.value">{{ mode.label }}</option>
                </select>
                <input
                  :value="getAptConstraint(form.apt[index])"
                  @input="setAptConstraint(form.apt[index], (($event.target as HTMLInputElement | null)?.value ?? ''))"
                  :disabled="aptVersionMode(form.apt[index]) !== 'custom'"
                  :placeholder="aptVersionMode(form.apt[index]) === 'custom' ? 'Version constraint' : 'Auto (latest)'"
                  class="block-select-lg"
                />
              </template>
            </DynamicListEditor>
          </div>
          <p v-if="importFeedback" class="help">{{ importFeedback }}</p>

          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Environment Variables</label>
            </div>
            <DynamicListEditor v-model="envEntries" add-label="Add env variable" :default-item="() => ({ key: '', value: '' })">
              <template #default="{ index }">
                <input type="text" v-model="envEntries[index].key" placeholder="KEY" class="block-select-md" />
                <span class="block-env-separator">=</span>
                <input type="text" v-model="envEntries[index].value" placeholder="value" class="block-flex-input" />
              </template>
            </DynamicListEditor>
          </div>

          <div class="dependency-group">
            <div class="dependency-group-header">
              <label class="wizard-label-inline">Ports</label>
            </div>
            <DynamicListEditor v-model="form.ports" add-label="Add port" :default-item="() => 8080">
              <template #default="{ index }">
                <input type="number" v-model.number="form.ports[index]" min="1" max="65535" class="block-port-input" />
              </template>
            </DynamicListEditor>
          </div>
        </div>

        <div v-if="currentStep === 'review'" class="wizard-step">
          <h4>Review</h4>
          <div class="wizard-detail">
            <p>Confirm identity and review the summary before writing the block spec.</p>
          </div>
          <label :class="{ required: requiresField('display_name') }">Display Name</label>
          <input
            v-model="form.display_name"
            name="display_name"
            type="text"
            placeholder="My Block"
            @input="onDisplayNameInput"
          />

          <label :class="{ required: requiresField('id') }">ID</label>
          <input
            v-model="form.id"
            name="id"
            @input="onIdInput"
            type="text"
            placeholder="my-block"
            maxlength="64"
            autocapitalize="off"
            spellcheck="false"
          />
          <p v-if="idError" class="field-error">{{ idError }}</p>

          <label>Description</label>
          <textarea
            v-model="form.description"
            name="description"
            placeholder="What this block does and why it exists (human-readable)"
            rows="3"
          />

          <div class="wizard-info block-summary-warning">
            <strong>Summary</strong>
            <ul class="compact-list">
              <li>{{ form.tags.length }} tag(s)</li>
              <li>{{ form.pip.length }} pip dependency(ies), {{ form.apt.length }} apt package(s)</li>
              <li>{{ form.npm.length }} node dependency(ies)</li>
              <li>{{ envEntries.length }} env variable(s), {{ form.ports.length }} port(s)</li>
              <li>{{ customConstraintCount }} custom dependency constraint(s)</li>
              <li>{{ pipWheelCount }} pip dependency(ies) using wheel mode</li>
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
            <button v-else class="btn btn-primary" @click="onComplete" :disabled="!canProceed">
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
import type {
  BlockPresetCatalog,
  CreateContractsResponse,
  DependencyVersionMode,
  NpmInstallScope,
  NpmPackageManager,
  PipDependencyVersionMode,
} from '@/api/types'
import DynamicListEditor from '@/components/DynamicListEditor.vue'
import { toUserErrorMessage } from '@/utils/errors'
import { SPEC_ID_RE, sanitizeSpecIdInput } from '@/utils/specId'
import {
  parseAptListText,
  parsePackageJsonText,
  parseRequirementsText,
} from '@/utils/dependencyImport'

const props = defineProps<{
  show: boolean
  form: {
    id: string
    display_name: string
    description: string
    tags: string[]
    pip: Array<{
      name: string
      version: string
      version_mode?: PipDependencyVersionMode
      wheel_file_path?: string
    }>
    pip_install_mode?: 'index' | 'wheelhouse_prefer' | 'wheelhouse_only'
    pip_wheelhouse_path?: string
    npm: Array<{
      name: string
      version: string
      version_mode?: DependencyVersionMode
      package_manager?: NpmPackageManager
      install_scope?: NpmInstallScope
    }>
    apt: string[]
    apt_constraints?: Record<string, string>
    ports: number[]
  }
  envEntries: Array<{ key: string; value: string }>
  contracts: CreateContractsResponse | null
  blockCatalog: BlockPresetCatalog | null
  selectedCategory: string
  searchTerm: string
  selectedPresetId: string
  selectedProfile: 'base' | 'cpu' | 'gpu' | 'dev' | 'prod'
}>()

const emit = defineEmits<{
  cancel: []
  complete: []
  'update:envEntries': [value: Array<{ key: string; value: string }>]
  'update:selectedCategory': [value: string]
  'update:searchTerm': [value: string]
  'update:selectedPresetId': [value: string]
  'update:selectedProfile': [value: 'base' | 'cpu' | 'gpu' | 'dev' | 'prod']
}>()

const dialogRef = ref<HTMLElement | null>(null)
const step = ref(1)
const steps = ['preset', 'runtime', 'review']
const totalSteps = computed(() => steps.length)
const currentStep = computed(() => steps[step.value - 1] || 'review')
const stepLabel = computed(() => {
  const map: Record<string, string> = {
    preset: 'Preset',
    runtime: 'Runtime',
    review: 'Review',
  }
  return map[currentStep.value] || 'Review'
})

const categories = computed(() => props.blockCatalog?.categories || [])
const categoryCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const preset of props.blockCatalog?.presets || []) {
    counts.set(preset.category, (counts.get(preset.category) || 0) + 1)
  }
  return counts
})
function categoryLabel(id: string, label: string): string {
  return `${label} (${categoryCounts.value.get(id) || 0})`
}
const VARIANT_SUFFIX_RE = /_(base|cpu|gpu|dev|prod)$/
function variantRank(id: string): number {
  if (id.endsWith('_base')) return 0
  if (id.endsWith('_cpu')) return 1
  if (id.endsWith('_gpu')) return 2
  if (id.endsWith('_dev')) return 3
  if (id.endsWith('_prod')) return 4
  return 5
}
const availablePresets = computed(() => {
  const rows = props.blockCatalog?.presets || []
  const deduped = new Map<string, typeof rows[number]>()
  for (const preset of rows) {
    const key = preset.id.replace(VARIANT_SUFFIX_RE, '')
    const existing = deduped.get(key)
    if (!existing || variantRank(preset.id) < variantRank(existing.id)) {
      deduped.set(key, preset)
    }
  }
  const canonicalRows = Array.from(deduped.values())
  const query = props.searchTerm.trim().toLowerCase()
  return canonicalRows.filter((preset) => {
    if (props.selectedCategory && preset.category !== props.selectedCategory) return false
    if (!query) return true
    return (
      preset.id.toLowerCase().includes(query) ||
      preset.display_name.toLowerCase().includes(query) ||
      preset.tags.join(' ').toLowerCase().includes(query)
    )
  })
})
const totalPresetCount = computed(() => {
  const rows = props.blockCatalog?.presets || []
  const dedupedKeys = new Set(rows.map(p => p.id.replace(VARIANT_SUFFIX_RE, '')))
  return dedupedKeys.size
})
const filteredPresetCount = computed(() => availablePresets.value.length)
const featuredPresetIds = [
  'vllm',
  'diffusers_runtime',
  'ultralytics_yolo',
  'faster_whisper_asr',
  'langgraph_runtime',
  'onnx_export_tools',
]
const featuredPresets = computed(() =>
  availablePresets.value.filter(p => featuredPresetIds.includes(p.id)).slice(0, 7),
)
const versionModes: Array<{ value: DependencyVersionMode; label: string }> = [
  { value: 'latest', label: 'Latest' },
  { value: 'custom', label: 'Custom' },
]
const pipVersionModes: Array<{ value: PipDependencyVersionMode; label: string }> = [
  { value: 'latest', label: 'Latest' },
  { value: 'custom', label: 'Custom' },
  { value: 'wheel', label: 'Wheel' },
]
const npmPackageManagers: Array<{ value: NpmPackageManager; label: string }> = [
  { value: 'npm', label: 'npm' },
  { value: 'pnpm', label: 'pnpm' },
  { value: 'yarn', label: 'yarn' },
]
const npmInstallScopes: Array<{ value: NpmInstallScope; label: string }> = [
  { value: 'prod', label: 'prod' },
  { value: 'dev', label: 'dev' },
]
const customConstraintCount = computed(() =>
  props.form.pip.filter(dep => (dep.version_mode || 'latest') === 'custom').length
  + props.form.npm.filter(dep => (dep.version_mode || 'latest') === 'custom').length
  + Object.keys(props.form.apt_constraints || {}).length,
)
const pipWheelCount = computed(() =>
  props.form.pip.filter(dep => (dep.version_mode || 'latest') === 'wheel').length,
)
const aptModeByName = ref<Record<string, DependencyVersionMode>>({})
const importFeedback = ref('')
const pipImportInput = ref<HTMLInputElement | null>(null)
const npmImportInput = ref<HTMLInputElement | null>(null)
const aptImportInput = ref<HTMLInputElement | null>(null)

function getAptConstraint(name: string): string {
  return props.form.apt_constraints?.[name] || ''
}

function setAptConstraint(name: string, value: string): void {
  if (!props.form.apt_constraints) props.form.apt_constraints = {}
  if (!value.trim()) {
    delete props.form.apt_constraints[name]
    return
  }
  props.form.apt_constraints[name] = value
}

function aptVersionMode(name: string): DependencyVersionMode {
  if (!name) return 'latest'
  return aptModeByName.value[name] || (getAptConstraint(name) ? 'custom' : 'latest')
}

function setAptVersionMode(name: string, mode: DependencyVersionMode): void {
  if (!name) return
  aptModeByName.value[name] = mode
  if (mode === 'latest') {
    setAptConstraint(name, '')
  }
}

function selectFeaturedPreset(presetId: string): void {
  selectedPresetId.value = presetId
}

function parseWheelVersionFromPath(path: string): string | null {
  const fileName = path.trim().split('/').pop() || ''
  if (!fileName.endsWith('.whl')) return null
  const stem = fileName.slice(0, -4)
  const parts = stem.split('-')
  if (parts.length < 2) return null
  return parts[1] || null
}

function setPipWheelFilePath(index: number, path: string): void {
  const dep = props.form.pip[index]
  if (!dep) return
  dep.wheel_file_path = path
  const parsedVersion = parseWheelVersionFromPath(path)
  if (parsedVersion) dep.version = `==${parsedVersion}`
}

function openPipImport(): void {
  pipImportInput.value?.click()
}

function openNpmImport(): void {
  npmImportInput.value?.click()
}

function openAptImport(): void {
  aptImportInput.value?.click()
}

async function onPipImportSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const imported = parseRequirementsText(text)
    const existing = new Set(props.form.pip.map(dep => dep.name.trim().toLowerCase()).filter(Boolean))
    let added = 0
    let skipped = 0
    for (const dep of imported) {
      const key = dep.name.trim().toLowerCase()
      if (!key || existing.has(key)) {
        skipped += 1
        continue
      }
      props.form.pip.push({
        name: dep.name,
        version: dep.version,
        version_mode: dep.version_mode,
        wheel_file_path: '',
      })
      existing.add(key)
      added += 1
    }
    importFeedback.value = `Pip import: added ${added}, skipped ${skipped}.`
  } catch (err) {
    importFeedback.value = `Pip import failed: ${toUserErrorMessage(err)}`
  } finally {
    input.value = ''
  }
}

async function onNpmImportSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const imported = parsePackageJsonText(text)
    const existing = new Set(
      props.form.npm.map(dep => `${dep.name.trim().toLowerCase()}::${dep.install_scope || 'prod'}`),
    )
    let added = 0
    let skipped = 0
    for (const dep of imported) {
      const key = `${dep.name.trim().toLowerCase()}::${dep.install_scope}`
      if (!dep.name.trim() || existing.has(key)) {
        skipped += 1
        continue
      }
      props.form.npm.push({
        name: dep.name,
        version: dep.version,
        version_mode: dep.version_mode,
        package_manager: dep.package_manager,
        install_scope: dep.install_scope,
      })
      existing.add(key)
      added += 1
    }
    importFeedback.value = `Node import: added ${added}, skipped ${skipped}.`
  } catch (err) {
    importFeedback.value = `Node import failed: ${toUserErrorMessage(err)}`
  } finally {
    input.value = ''
  }
}

async function onAptImportSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    const parsed = parseAptListText(text)
    const existing = new Set(props.form.apt.map(pkg => pkg.trim()).filter(Boolean))
    let added = 0
    let skipped = 0
    for (const pkg of parsed.apt) {
      if (!pkg || existing.has(pkg)) {
        skipped += 1
        continue
      }
      props.form.apt.push(pkg)
      existing.add(pkg)
      added += 1
    }
    if (!props.form.apt_constraints) props.form.apt_constraints = {}
    for (const [name, constraint] of Object.entries(parsed.constraints)) {
      if (name && constraint) {
        props.form.apt_constraints[name] = constraint
      }
    }
    importFeedback.value = `Apt import: added ${added}, skipped ${skipped}.`
  } catch (err) {
    importFeedback.value = `Apt import failed: ${toUserErrorMessage(err)}`
  } finally {
    input.value = ''
  }
}


watch(
  () => [...props.form.apt],
  (packages) => {
    const active = new Set(packages.filter(Boolean))
    for (const pkg of Object.keys(aptModeByName.value)) {
      if (!active.has(pkg)) {
        delete aptModeByName.value[pkg]
      }
    }
    for (const pkg of active) {
      if (!aptModeByName.value[pkg]) {
        aptModeByName.value[pkg] = getAptConstraint(pkg) ? 'custom' : 'latest'
      }
    }
  },
  { immediate: true },
)

const selectedCategory = computed({
  get: () => props.selectedCategory,
  set: (value: string) => emit('update:selectedCategory', value),
})
const searchTerm = computed({
  get: () => props.searchTerm,
  set: (value: string) => emit('update:searchTerm', value),
})
const selectedPresetId = computed({
  get: () => props.selectedPresetId,
  set: (value: string) => emit('update:selectedPresetId', value),
})
const selectedProfile = computed({
  get: () => props.selectedProfile,
  set: (value: 'base' | 'cpu' | 'gpu' | 'dev' | 'prod') => emit('update:selectedProfile', value),
})
const envEntries = computed({
  get: () => props.envEntries,
  set: (value: Array<{ key: string; value: string }>) => emit('update:envEntries', value),
})

watch(
  () => props.show,
  async (open) => {
    if (!open) return
    step.value = 1
    await nextTick()
    focusFirst()
  },
)

watch(
  [availablePresets, selectedPresetId],
  ([rows, selected]) => {
    if (!selected) return
    if (!rows.some(p => p.id === selected)) {
      selectedPresetId.value = ''
    }
  },
)

function requiresField(field: string): boolean {
  const required = new Set(props.contracts?.block?.required_fields || [])
  return required.has(field)
}

const idError = computed(() => {
  if (!props.form.id) return ''
  return SPEC_ID_RE.test(props.form.id)
    ? ''
    : 'Must be 3-64 chars, start with a lowercase letter, and use only lowercase letters, digits, hyphens, and underscores'
})

const canProceed = computed(() => {
  if (currentStep.value === 'review') {
    if (requiresField('id') && !props.form.id) return false
    if (requiresField('display_name') && !props.form.display_name) return false
    if (idError.value) return false
  }
  return true
})

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
  const candidate = compact && /^[a-z]/.test(compact) ? compact : `b_${compact || 'block'}`
  return sanitizeSpecIdInput(candidate)
}

function onDisplayNameInput(event: Event) {
  const input = event.target as HTMLInputElement
  props.form.display_name = input.value
  if (!props.form.id.trim()) {
    props.form.id = suggestedIdFromDisplayName(props.form.display_name)
  }
}

function nextStep() {
  if (!canProceed.value) return
  step.value = Math.min(totalSteps.value, step.value + 1)
  nextTick(focusFirst)
}

function prevStep() {
  step.value = Math.max(1, step.value - 1)
  nextTick(focusFirst)
}

function onComplete() {
  emit('complete')
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

.row {
  display: grid;
  gap: 0.75rem;
}

.row.two {
  grid-template-columns: repeat(2, minmax(180px, 1fr));
}

.field-error {
  color: var(--error);
  font-size: 0.75rem;
  margin-top: 0.2rem;
}

.help {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.featured-preset-wrap {
  margin-bottom: 0.75rem;
}

.featured-preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.featured-preset-btn {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
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

.import-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.15rem;
  margin-bottom: 0.35rem;
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

.wizard-hidden-input {
  display: none;
}

.block-help-gap-sm {
  margin-top: 0.35rem;
}

.block-grid-row {
  display: grid;
  gap: 0.45rem;
  width: 100%;
}

.block-inline-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
  width: 100%;
}

.block-flex-input {
  flex: 1;
}

.block-select-xs {
  width: 95px;
}

.block-select-sm {
  width: 130px;
}

.block-select-md {
  width: 160px;
}

.block-select-lg {
  width: 220px;
}

.block-port-input {
  width: 120px;
}

.block-env-separator {
  color: var(--text-muted);
}

.block-nowrap {
  white-space: nowrap;
}

.block-summary-warning {
  margin-top: 0.75rem;
}
</style>
