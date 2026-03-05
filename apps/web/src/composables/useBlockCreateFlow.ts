import { computed, reactive, ref, watch } from 'vue'
import { blocks as blocksApi, meta as metaApi, settings as settingsApi } from '@/api/endpoints'
import type {
  BlockCreatePayload,
  BlockPreset,
  BlockPresetCatalog,
  CreateContractsResponse,
  DependencyVersionMode,
  EnumsMeta,
  NpmInstallScope,
  NpmPackageManager,
  PipDependencyVersionMode,
  PipInstallMode,
} from '@/api/types'
import { useEntityCreateFlow } from '@/composables/useEntityCreateFlow'

type Options = {
  onCreated?: (id: string) => void
}

type PresetProfile = 'base' | 'cpu' | 'gpu' | 'dev' | 'prod'

function profileOverlay(profile: PresetProfile): { env: Record<string, string> } {
  if (profile === 'cpu') {
    return { env: { OMP_NUM_THREADS: '8', MKL_NUM_THREADS: '8' } }
  }
  if (profile === 'gpu') {
    return { env: { NVIDIA_VISIBLE_DEVICES: 'all', CUDA_MODULE_LOADING: 'LAZY' } }
  }
  if (profile === 'dev') {
    return { env: { PYTHONUNBUFFERED: '1', LOG_LEVEL: 'debug' } }
  }
  if (profile === 'prod') {
    return { env: { PYTHONUNBUFFERED: '1', LOG_LEVEL: 'info', UVICORN_WORKERS: '2' } }
  }
  return { env: { STACKSMITH_PROFILE: 'balanced' } }
}

export function useBlockCreateFlow(options: Options = {}) {
  const enums = reactive<EnumsMeta>({
    task: [], serve: [], api: [], arch: [], build_strategy: [], container_runtime: [],
  })
  const createContracts = ref<CreateContractsResponse | null>(null)
  const blockCatalog = ref<BlockPresetCatalog | null>(null)
  const metadataLoaded = ref(false)
  const metadataWarnings = ref<string[]>([])

  const selectedCategory = ref('')
  const searchTerm = ref('')
  const selectedPresetId = ref('')
  const selectedProfile = ref<PresetProfile>('base')

  const VARIANT_SUFFIX_RE = /_(base|cpu|gpu|dev|prod)$/
  function variantRank(id: string): number {
    if (id.endsWith('_base')) return 0
    if (id.endsWith('_cpu')) return 1
    if (id.endsWith('_gpu')) return 2
    if (id.endsWith('_dev')) return 3
    if (id.endsWith('_prod')) return 4
    return 5
  }

  const form = reactive({
    id: '',
    display_name: '',
    tags: [] as string[],
    build_strategy: '',
    base_role: '',
    pip: [] as Array<{
      name: string
      version: string
      version_mode?: PipDependencyVersionMode
      wheel_file_path?: string
    }>,
    pip_install_mode: 'index' as PipInstallMode,
    pip_wheelhouse_path: '',
    npm: [] as Array<{
      name: string
      version: string
      version_mode?: DependencyVersionMode
      package_manager?: NpmPackageManager
      install_scope?: NpmInstallScope
    }>,
    apt: [] as string[],
    apt_constraints: {} as Record<string, string>,
    ports: [] as number[],
    entrypoint_cmd: [] as string[],
    copy_items: [] as { src: string; dst: string }[],
    variants: {} as Record<string, { type: 'bool' | 'enum'; options: string[]; default: string | boolean }>,
    requires: {} as Record<string, any>,
    conflicts: [] as string[],
    incompatible_with: [] as string[],
    provides: {} as Record<string, any>,
  })

  const envEntries = ref<{ key: string; value: string }[]>([])

  const categories = computed(() => blockCatalog.value?.categories || [])
  const availablePresets = computed(() => {
    const rows = blockCatalog.value?.presets || []
    const deduped = new Map<string, typeof rows[number]>()
    for (const preset of rows) {
      const key = preset.id.replace(VARIANT_SUFFIX_RE, '')
      const existing = deduped.get(key)
      if (!existing || variantRank(preset.id) < variantRank(existing.id)) {
        deduped.set(key, preset)
      }
    }
    const canonicalRows = Array.from(deduped.values())
    const q = searchTerm.value.trim().toLowerCase()
    return canonicalRows.filter((preset) => {
      if (selectedCategory.value && preset.category !== selectedCategory.value) return false
      if (!q) return true
      return (
        preset.id.toLowerCase().includes(q) ||
        preset.display_name.toLowerCase().includes(q) ||
        preset.tags.join(' ').toLowerCase().includes(q)
      )
    })
  })

  function setEnvFromObject(env: Record<string, string>) {
    envEntries.value = Object.entries(env).map(([key, value]) => ({ key, value }))
  }

  function envObject(): Record<string, string> {
    const env: Record<string, string> = {}
    for (const entry of envEntries.value) {
      if (entry.key.trim()) env[entry.key.trim()] = entry.value
    }
    return env
  }

  function resetForNewSession() {
    form.id = ''
    form.display_name = ''
    form.tags = []
    form.build_strategy = ''
    form.base_role = ''
    form.pip = []
    form.pip_install_mode = 'index'
    form.pip_wheelhouse_path = ''
    form.npm = []
    form.apt = []
    form.apt_constraints = {}
    form.ports = []
    form.entrypoint_cmd = []
    form.copy_items = []
    form.variants = {}
    form.requires = {}
    form.conflicts = []
    form.incompatible_with = []
    form.provides = {}
    envEntries.value = []
    flow.resetFlowState()
    selectedPresetId.value = ''
    selectedProfile.value = 'base'
    searchTerm.value = ''
    selectedCategory.value = ''
  }

  async function loadMetadata() {
    flow.generalError.value = null
    metadataWarnings.value = []
    try {
      const [enumData, contracts] = await Promise.all([
        metaApi.enums(),
        metaApi.createContracts('v3'),
      ])
      Object.assign(enums, enumData)
      createContracts.value = contracts
      try {
        blockCatalog.value = await settingsApi.blockCatalog()
      } catch (catalogErr: unknown) {
        metadataWarnings.value.push(
          `block-catalog: ${catalogErr instanceof Error ? catalogErr.message : String(catalogErr)}`,
        )
        // Keep wizard usable even when preset API is unavailable.
        blockCatalog.value = {
          schema_version: 1,
          revision: 0,
          categories: [],
          presets: [],
        }
      }
      metadataLoaded.value = true
    } catch (err: unknown) {
      flow.generalError.value = err instanceof Error ? err.message : String(err)
      metadataLoaded.value = false
    }
  }

  function selectedPreset(): BlockPreset | null {
    const id = selectedPresetId.value
    if (!id) return null
    return (blockCatalog.value?.presets || []).find(p => p.id === id) || null
  }

  watch([selectedPresetId, selectedProfile], () => {
    if (!selectedPresetId.value) return
    applyPreset()
  })

  function applyPreset() {
    const preset = selectedPreset()
    if (!preset) return
    const presetEnv = { ...preset.env }

    if (!form.id) form.id = preset.id
    if (!form.display_name) form.display_name = preset.display_name
    form.tags = [...preset.tags]
    form.pip = preset.pip.map(p => ({
      name: p.name,
      version: p.version || '',
      version_mode: p.version ? 'custom' : 'latest',
      wheel_file_path: '',
    }))
    form.pip_install_mode = 'index'
    form.pip_wheelhouse_path = ''
    form.npm = []
    form.apt = [...preset.apt]
    form.apt_constraints = {}
    form.ports = [...preset.ports]
    form.entrypoint_cmd = [...preset.entrypoint_cmd]
    form.requires = { ...(preset.requires || {}) }
    form.provides = { ...(preset.provides || {}) }
    form.incompatible_with = []
    form.conflicts = []

    const overlay = profileOverlay(selectedProfile.value)
    setEnvFromObject({ ...presetEnv, ...overlay.env })
  }

  function buildPayload(): BlockCreatePayload {
    const parseWheelVersion = (wheelPath: string): string | null => {
      const fileName = wheelPath.trim().split('/').pop() || ''
      if (!fileName.endsWith('.whl')) return null
      const stem = fileName.slice(0, -4)
      const parts = stem.split('-')
      if (parts.length < 2) return null
      return parts[1] || null
    }
    const wheelDirFromPath = (wheelPath: string): string | null => {
      const p = wheelPath.trim()
      const idx = p.lastIndexOf('/')
      if (idx <= 0) return null
      return p.slice(0, idx).trim() || null
    }
    const normalizedPip = form.pip
      .map(dep => {
        const name = dep.name.trim()
        if (!name) return null
        const mode = dep.version_mode === 'wheel' ? 'wheel' : (dep.version_mode === 'custom' ? 'custom' : 'latest')
        const wheelFilePath = (dep.wheel_file_path || '').trim()
        const wheelVersion = mode === 'wheel' ? parseWheelVersion(wheelFilePath) : null
        return {
          name,
          version_mode: mode === 'latest' ? 'latest' : 'custom' as DependencyVersionMode,
          version: mode === 'wheel'
            ? (wheelVersion ? `==${wheelVersion}` : dep.version.trim())
            : (mode === 'custom' ? dep.version.trim() : ''),
          wheel_file_path: mode === 'wheel' ? wheelFilePath : '',
        }
      })
      .filter((dep): dep is NonNullable<typeof dep> => dep !== null)
    const wheelDeps = normalizedPip.filter(dep => dep.wheel_file_path)
    const wheelDirs = Array.from(new Set(wheelDeps.map(dep => wheelDirFromPath(dep.wheel_file_path)).filter(Boolean)))
    if (wheelDeps.length > 0 && wheelDirs.length === 0) {
      throw new Error('Wheel mode selected but no valid wheel file path was provided.')
    }
    if (wheelDirs.length > 1) {
      throw new Error('Multiple wheel locations detected across pip dependencies. Use a single wheel location for this block.')
    }
    const apt = form.apt.map(pkg => pkg.trim()).filter(Boolean)
    const aptConstraints = Object.fromEntries(
      Object.entries(form.apt_constraints || {})
        .map(([name, constraint]) => [name.trim(), constraint.trim()] as const)
        .filter(([name, constraint]) => apt.includes(name) && !!constraint),
    )
    const normalizedNpm = form.npm
      .map(dep => {
        const name = dep.name.trim()
        if (!name) return null
        const mode: DependencyVersionMode = dep.version_mode === 'custom' ? 'custom' : 'latest'
        return {
          name,
          package_manager: dep.package_manager || 'npm',
          install_scope: dep.install_scope || 'prod',
          version_mode: mode,
          version: mode === 'custom' ? dep.version.trim() : '',
        }
      })
      .filter((dep): dep is NonNullable<typeof dep> => dep !== null)

    return {
      schema_version: 2,
      id: form.id,
      display_name: form.display_name,
      tags: form.tags.filter(Boolean),
      build_strategy: form.build_strategy || undefined,
      base_role: form.base_role || undefined,
      pip: normalizedPip.map(({ wheel_file_path, ...dep }) => dep),
      pip_install_mode: wheelDeps.length > 0 ? 'wheelhouse_prefer' : 'index',
      pip_wheelhouse_path: wheelDeps.length > 0 ? wheelDirs[0]! : undefined,
      npm: normalizedNpm,
      apt,
      apt_constraints: Object.keys(aptConstraints).length ? aptConstraints : undefined,
      env: envObject(),
      ports: form.ports,
      entrypoint_cmd: form.entrypoint_cmd.filter(Boolean),
      copy_items: form.copy_items.filter(c => c.src),
      variants: form.variants,
      requires: form.requires,
      conflicts: form.conflicts,
      incompatible_with: form.incompatible_with,
      provides: form.provides,
    }
  }

  const flow = useEntityCreateFlow<BlockCreatePayload, { id: string }>({
    entityLabel: 'Block',
    buildPayload,
    dryRun: (payload) => blocksApi.dryRun(payload),
    create: (payload) => blocksApi.create(payload),
    onCreated: options.onCreated,
  })

  return {
    enums,
    createContracts,
    blockCatalog,
    metadataLoaded,
    metadataWarnings,
    selectedCategory,
    searchTerm,
    selectedPresetId,
    selectedProfile,
    categories,
    availablePresets,
    form,
    envEntries,
    validationErrors: flow.validationErrors,
    generalError: flow.generalError,
    previewYamlStr: flow.previewYamlStr,
    previewing: flow.previewing,
    creating: flow.creating,
    loadMetadata,
    previewYaml: flow.previewYaml,
    createBlock: flow.createEntity,
    resetForNewSession,
  }
}
