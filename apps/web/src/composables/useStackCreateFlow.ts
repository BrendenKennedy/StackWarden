import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { layers as layersApi, profiles as profilesApi, stacks as stacksApi, meta as metaApi, settings as settingsApi, system as systemApi } from '@/api/endpoints'
import type {
  LayerSummary,
  ProfileSummary,
  LayerPresetCatalog,
  CreateContractsResponse,
  EnumsMeta,
  StackCreatePayload,
  ValidationError as VError,
} from '@/api/types'
import { resolveCreateSchemaVersion } from '@/api/schemaVersions'
import { useEntityCreateFlow } from '@/composables/useEntityCreateFlow'
import { toUserErrorMessage } from '@/utils/errors'

type Options = {
  onCreated?: (id: string) => void
}

export function useStackCreateFlow(options: Options = {}) {
  const enums = reactive<EnumsMeta>({
    task: [], serve: [], api: [], arch: [], build_strategy: [], container_runtime: [],
  })

  const availableLayers = ref<LayerSummary[]>([])
  const availableProfiles = ref<ProfileSummary[]>([])
  const metadataLoaded = ref(false)
  const authEnabled = ref(true)
  const createContracts = ref<CreateContractsResponse | null>(null)
  const layerCatalog = ref<LayerPresetCatalog | null>(null)

  const form = reactive({
    id: '',
    display_name: '',
    description: '',
    build_strategy: '',
    base_role: '',
    target_profile_id: '',
    layers: [] as string[],
    copy_items: [] as { src: string; dst: string }[],
    variants: {} as Record<string, { type: 'bool' | 'enum'; options: string[]; default: string | boolean }>,
  })

  const composeDebounceTimer = ref<number | null>(null)
  let composeRequestToken = 0

  const composedYamlStr = ref('')
  const composedResolvedSpec = ref<Record<string, any> | null>(null)
  const composing = ref(false)
  const dependencyConflicts = ref<Array<Record<string, string>>>([])
  const tupleConflicts = ref<Array<Record<string, string>>>([])
  const runtimeConflicts = ref<Array<Record<string, string>>>([])

  const canCreate = computed(() =>
    form.id !== '' &&
    form.display_name !== '' &&
    form.target_profile_id !== '' &&
    form.layers.length > 0,
  )

  async function loadMetadata() {
    flow.generalError.value = null
    try {
      const [enumData, sysConfig, layerData, profileData, contracts] = await Promise.all([
        metaApi.enums(),
        systemApi.config(),
        layersApi.list(),
        profilesApi.list(),
        metaApi.createContracts('v3').catch(() => null),
      ])
      Object.assign(enums, enumData)
      authEnabled.value = sysConfig.auth_enabled
      availableLayers.value = layerData
      availableProfiles.value = profileData
      createContracts.value = contracts
      try {
        layerCatalog.value = await settingsApi.layerCatalog()
      } catch {
        layerCatalog.value = null
      }
      metadataLoaded.value = true
    } catch (err: unknown) {
      flow.generalError.value = toUserErrorMessage(err)
      metadataLoaded.value = false
    }
  }

  watch(
    () => [...form.layers],
    async () => {
      if (form.layers.length > 0) {
        if (composeDebounceTimer.value !== null) {
          window.clearTimeout(composeDebounceTimer.value)
        }
        composeDebounceTimer.value = window.setTimeout(() => {
          void previewComposed()
        }, 250)
      }
    },
    { deep: true },
  )

  function buildPayload(): StackCreatePayload {
    const resolvedId = (form.id || '').trim() || 'draft-stack'
    const resolvedDisplayName = (form.display_name || '').trim() || 'Draft Stack'

    return {
      schema_version: resolveCreateSchemaVersion('stack', createContracts.value),
      kind: 'stack_recipe',
      id: resolvedId,
      display_name: resolvedDisplayName,
      target_profile_id: form.target_profile_id,
      description: (form.description || '').trim(),
      layers: [...form.layers],
      build_strategy: form.build_strategy,
      base_role: form.base_role,
      copy_items: form.copy_items.filter(c => c.src),
      variants: form.variants,
      requirements: {
        needs: [],
        optimize_for: [],
        constraints: { target_profile_id: form.target_profile_id },
      },
    }
  }

  const flow = useEntityCreateFlow<StackCreatePayload, { id: string }>({
    entityLabel: 'Stack',
    buildPayload,
    dryRun: (payload) => stacksApi.dryRun(payload),
    create: (payload) => stacksApi.create(payload),
    onCreated: options.onCreated,
  })

  async function previewComposed() {
    const token = ++composeRequestToken
    composing.value = true
    flow.validationErrors.value = []
    flow.generalError.value = null
    try {
      const resp = await stacksApi.composePreview(buildPayload())
      if (token !== composeRequestToken) {
        return
      }
      dependencyConflicts.value = (resp.dependency_conflicts || []) as Array<Record<string, string>>
      tupleConflicts.value = (resp.tuple_conflicts || []) as Array<Record<string, string>>
      runtimeConflicts.value = (resp.runtime_conflicts || []) as Array<Record<string, string>>
      if (resp.valid) {
        composedYamlStr.value = resp.yaml
        composedResolvedSpec.value = (resp.resolved_spec || null) as Record<string, any> | null
      } else {
        flow.validationErrors.value = resp.errors as VError[]
        composedYamlStr.value = ''
        composedResolvedSpec.value = null
      }
    } catch (err: unknown) {
      if (token !== composeRequestToken) {
        return
      }
      flow.generalError.value = toUserErrorMessage(err)
      dependencyConflicts.value = []
      tupleConflicts.value = []
      runtimeConflicts.value = []
      composedResolvedSpec.value = null
    } finally {
      if (token === composeRequestToken) {
        composing.value = false
      }
    }
  }

  const createStack = flow.createEntity
  const previewYaml = flow.previewYaml

  function resetForNewSession() {
    form.id = ''
    form.display_name = ''
    form.description = ''
    form.build_strategy = ''
    form.base_role = ''
    form.target_profile_id = ''
    form.layers = []
    form.copy_items = []
    form.variants = {}
    flow.resetFlowState()
    composedYamlStr.value = ''
    composedResolvedSpec.value = null
    dependencyConflicts.value = []
    tupleConflicts.value = []
    runtimeConflicts.value = []
  }

  function isStackRequired(field: string): boolean {
    const required = createContracts.value?.stack?.required_fields || []
    return required.includes(field) || required.includes(field.split('.')[0])
  }

  onUnmounted(() => {
    if (composeDebounceTimer.value !== null) {
      window.clearTimeout(composeDebounceTimer.value)
      composeDebounceTimer.value = null
    }
  })

  return {
    enums,
    form,
    availableLayers,
    availableProfiles,
    layerCatalog,
    authEnabled,
    createContracts,
    metadataLoaded,
    validationErrors: flow.validationErrors,
    generalError: flow.generalError,
    previewYamlStr: flow.previewYamlStr,
    composedYamlStr,
    composedResolvedSpec,
    previewing: flow.previewing,
    composing,
    creating: flow.creating,
    dependencyConflicts,
    tupleConflicts,
    runtimeConflicts,
    canCreate,
    loadMetadata,
    previewYaml,
    previewComposed,
    createStack,
    resetForNewSession,
    isStackRequired,
  }
}
