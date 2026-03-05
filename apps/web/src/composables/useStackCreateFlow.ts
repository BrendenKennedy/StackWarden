import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { blocks as blocksApi, stacks as stacksApi, meta as metaApi, settings as settingsApi, system as systemApi } from '@/api/endpoints'
import type {
  BlockSummary,
  BlockPresetCatalog,
  CreateContractsResponse,
  EnumsMeta,
  StackCreatePayload,
  ValidationError as VError,
} from '@/api/types'
import { useEntityCreateFlow } from '@/composables/useEntityCreateFlow'

type Options = {
  onCreated?: (id: string) => void
}

export function useStackCreateFlow(options: Options = {}) {
  const enums = reactive<EnumsMeta>({
    task: [], serve: [], api: [], arch: [], build_strategy: [], container_runtime: [],
  })

  const availableBlocks = ref<BlockSummary[]>([])
  const metadataLoaded = ref(false)
  const authEnabled = ref(true)
  const createContracts = ref<CreateContractsResponse | null>(null)
  const blockCatalog = ref<BlockPresetCatalog | null>(null)

  const form = reactive({
    id: '',
    display_name: '',
    build_strategy: '',
    base_role: '',
    blocks: [] as string[],
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
    form.blocks.length > 0,
  )

  async function loadMetadata() {
    flow.generalError.value = null
    try {
      const [enumData, sysConfig, blockData, contracts] = await Promise.all([
        metaApi.enums(),
        systemApi.config(),
        blocksApi.list(),
        metaApi.createContracts('v3').catch(() => null),
      ])
      Object.assign(enums, enumData)
      authEnabled.value = sysConfig.auth_enabled
      availableBlocks.value = blockData
      createContracts.value = contracts
      try {
        blockCatalog.value = await settingsApi.blockCatalog()
      } catch {
        blockCatalog.value = null
      }
      metadataLoaded.value = true
    } catch (err: unknown) {
      flow.generalError.value = err instanceof Error ? err.message : String(err)
      metadataLoaded.value = false
    }
  }

  watch(
    () => [...form.blocks],
    async () => {
      if (form.blocks.length > 0) {
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
      schema_version: 3,
      kind: 'stack_recipe',
      id: resolvedId,
      display_name: resolvedDisplayName,
      blocks: [...form.blocks],
      build_strategy: form.build_strategy,
      base_role: form.base_role,
      copy_items: form.copy_items.filter(c => c.src),
      variants: form.variants,
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
      flow.generalError.value = err instanceof Error ? err.message : String(err)
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
    form.build_strategy = ''
    form.base_role = ''
    form.blocks = []
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
    availableBlocks,
    blockCatalog,
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
