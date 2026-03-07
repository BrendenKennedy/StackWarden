import { reactive, ref } from 'vue'
import type {
  CreateContractsResponse,
  DetectionHints,
  EnumsMeta,
  HardwareCatalog,
  HardwareCatalogItem,
  ProfileCreatePayload,
} from '@/api/types'
import { profiles as profilesApi, meta as metaApi, settings as settingsApi, system as systemApi } from '@/api/endpoints'
import { ApiError } from '@/api/client'
import { toUserErrorMessage } from '@/utils/errors'
import { SPEC_ID_PATTERN } from '@/api/contracts.generated'
import { resolveCreateSchemaVersion } from '@/api/schemaVersions'
import { useToast } from '@/composables/useToast'
import { useEntityCreateFlow } from '@/composables/useEntityCreateFlow'

type Options = {
  onCreated?: (id: string) => void
}

export function useProfileCreateFlow(options: Options = {}) {
  const { showToast } = useToast()
  const ID_RE = new RegExp(SPEC_ID_PATTERN)
  const ADD_CUSTOM_VALUE = '__add_custom__'

  const enums = reactive<EnumsMeta>({
    task: [], serve: [], api: [], arch: [], build_strategy: [], container_runtime: [],
  })

  const form = reactive({
    id: '',
    display_name: '',
    arch: '',
    os: 'linux',
    os_family_id: '',
    os_version_id: '',
    container_runtime: 'nvidia',
    gpu: { vendor: 'nvidia', family: 'ampere', vendor_id: 'nvidia', family_id: 'ampere', model_id: '' },
    advanced_override: false,
  })

  const authEnabled = ref(true)
  const detectionHints = ref<DetectionHints | null>(null)
  const createContracts = ref<CreateContractsResponse | null>(null)
  const hardwareCatalog = ref<HardwareCatalog | null>(null)
  const metadataWarnings = ref<string[]>([])
  const backendDisconnected = ref(false)
  const detectingHints = ref(false)
  const metadataLoaded = ref(false)

  function resetForm() {
    form.id = ''
    form.display_name = ''
    form.arch = ''
    form.os = 'linux'
    form.os_family_id = ''
    form.os_version_id = ''
    form.container_runtime = 'nvidia'
    form.gpu.vendor = 'nvidia'
    form.gpu.family = 'ampere'
    form.gpu.vendor_id = 'nvidia'
    form.gpu.family_id = 'ampere'
    form.gpu.model_id = ''
    form.advanced_override = false
  }

  function resetForNewSession() {
    resetForm()
    flow.resetFlowState()
  }

  function syncResolvedIdsFromHints(hints: DetectionHints | null) {
    if (!hints?.resolved_ids) return
    form.os_family_id = hints.resolved_ids.os_family_id || form.os_family_id
    form.os_version_id = hints.resolved_ids.os_version_id || form.os_version_id
    form.gpu.vendor_id = hints.resolved_ids.gpu_vendor_id || form.gpu.vendor_id
    form.gpu.family_id = hints.resolved_ids.gpu_family_id || form.gpu.family_id
  }

  async function loadMetadata() {
    flow.generalError.value = null
    metadataWarnings.value = []
    backendDisconnected.value = false
    try {
      const [enumData, sysConfig] = await Promise.all([
        metaApi.enums(),
        systemApi.config(),
      ])
      Object.assign(enums, enumData)
      authEnabled.value = sysConfig.auth_enabled
    } catch (e: unknown) {
      const message = toUserErrorMessage(e)
      backendDisconnected.value = e instanceof ApiError && e.status === 0
      flow.generalError.value = `Failed to load required metadata: ${message}`
      metadataLoaded.value = false
      return
    }

    const optionalResults = await Promise.allSettled([
      systemApi.detectionHints(),
      metaApi.createContracts('v3'),
      settingsApi.hardwareCatalogs(),
    ])
    if (optionalResults[0].status === 'fulfilled') {
      detectionHints.value = optionalResults[0].value
    } else {
      metadataWarnings.value.push(`detection-hints: ${toUserErrorMessage(optionalResults[0].reason)}`)
    }
    if (optionalResults[1].status === 'fulfilled') {
      createContracts.value = optionalResults[1].value
    } else {
      metadataWarnings.value.push(`create-contracts: ${toUserErrorMessage(optionalResults[1].reason)}`)
    }
    if (optionalResults[2].status === 'fulfilled') {
      hardwareCatalog.value = optionalResults[2].value
    } else {
      metadataWarnings.value.push(`hardware-catalogs: ${toUserErrorMessage(optionalResults[2].reason)}`)
    }
    syncResolvedIdsFromHints(detectionHints.value)

    if (metadataWarnings.value.length > 0) {
      try {
        await systemApi.health()
      } catch {
        backendDisconnected.value = true
      }
    }
    metadataLoaded.value = true
  }

  async function refreshDetectionHints(): Promise<DetectionHints | null> {
    detectingHints.value = true
    try {
      const hints = await systemApi.detectionHints(true)
      detectionHints.value = hints
      syncResolvedIdsFromHints(hints)
      showToast('Host detection refreshed', 'success')
      return hints
    } catch (err: unknown) {
      const msg = toUserErrorMessage(err)
      metadataWarnings.value = metadataWarnings.value.filter(w => !w.startsWith('detection-hints:'))
      metadataWarnings.value.push(`detection-hints: ${msg}`)
      showToast(`Detection refresh failed: ${msg}`, 'error')
      return null
    } finally {
      detectingHints.value = false
    }
  }

  function labelOrId(catalog: keyof HardwareCatalog, id: string | undefined): string | null {
    if (!id || id === ADD_CUSTOM_VALUE || !hardwareCatalog.value) return null
    const items = (hardwareCatalog.value[catalog] as HardwareCatalogItem[]) || []
    const match = items.find(i => i.id === id)
    return match?.label || id
  }

  function normalizeSelection(value: string | null | undefined): string {
    if (!value || value === ADD_CUSTOM_VALUE) return ''
    return value
  }

  function buildPayload(): ProfileCreatePayload {
    const arch = normalizeSelection(form.arch)
    const containerRuntime = normalizeSelection(form.container_runtime)
    const osFamilyId = normalizeSelection(form.os_family_id)
    const osVersionId = normalizeSelection(form.os_version_id)
    const gpuVendorId = normalizeSelection(form.gpu.vendor_id)
    const gpuFamilyId = normalizeSelection(form.gpu.family_id)
    const gpuModelId = normalizeSelection(form.gpu.model_id)
    const vendor = labelOrId('gpu_vendor', gpuVendorId)
    const family = labelOrId('gpu_family', gpuFamilyId)
    return {
      schema_version: resolveCreateSchemaVersion('profile', createContracts.value),
      id: form.id,
      display_name: form.display_name,
      arch,
      os: form.os,
      os_family: labelOrId('os_family', osFamilyId) || detectionHints.value?.os_family || form.os || null,
      os_version: labelOrId('os_version', osVersionId) || detectionHints.value?.os_version || null,
      os_family_id: osFamilyId || null,
      os_version_id: osVersionId || null,
      container_runtime: containerRuntime,
      cuda: detectionHints.value?.cuda
        ? {
            major: detectionHints.value.cuda.major,
            minor: detectionHints.value.cuda.minor,
            variant: detectionHints.value.cuda.variant,
          }
        : null,
      gpu: {
        vendor: vendor || 'nvidia',
        family: family || 'gpu',
        vendor_id: gpuVendorId || null,
        family_id: gpuFamilyId || null,
        model_id: gpuModelId || null,
        compute_capability: detectionHints.value?.gpu?.compute_capability || null,
      },
      gpu_devices: detectionHints.value?.gpu_devices || [],
      constraints: { disallow: {}, require: {} },
      host_facts: {
        driver_version: detectionHints.value?.driver_version || null,
        runtime_version: null,
        cpu_model: detectionHints.value?.cpu_model || null,
        cpu_cores_logical: detectionHints.value?.cpu_cores_logical || null,
        cpu_cores_physical: detectionHints.value?.cpu_cores_physical || null,
        memory_gb_total: detectionHints.value?.memory_gb_total || null,
        disk_gb_total: detectionHints.value?.disk_gb_total || null,
        detected_at: new Date().toISOString(),
        confidence: detectionHints.value?.confidence || {},
      },
      capability_ranges: detectionHints.value?.supported_cuda_min || detectionHints.value?.supported_cuda_max
        ? [{
            name: 'cuda_runtime',
            min: detectionHints.value?.supported_cuda_min || null,
            max: detectionHints.value?.supported_cuda_max || null,
            values: [],
          }]
        : [],
      advanced_override: form.advanced_override,
    }
  }

  const flow = useEntityCreateFlow<ProfileCreatePayload, { id: string }>({
    entityLabel: 'Profile',
    buildPayload,
    dryRun: (payload) => profilesApi.dryRun(payload),
    create: (payload) => profilesApi.create(payload),
    onCreated: options.onCreated,
  })

  return {
    ID_RE,
    enums,
    form,
    validationErrors: flow.validationErrors,
    generalError: flow.generalError,
    previewYamlStr: flow.previewYamlStr,
    previewing: flow.previewing,
    creating: flow.creating,
    authEnabled,
    detectionHints,
    createContracts,
    hardwareCatalog,
    metadataWarnings,
    backendDisconnected,
    detectingHints,
    metadataLoaded,
    loadMetadata,
    refreshDetectionHints,
    previewYaml: flow.previewYaml,
    createProfile: flow.createEntity,
    resetForNewSession,
  }
}

