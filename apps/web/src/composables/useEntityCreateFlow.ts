import { ref } from 'vue'
import { ApiError } from '@/api/client'
import { toUserErrorMessage } from '@/utils/errors'
import type { ValidationError as VError } from '@/api/types'
import { useToast } from '@/composables/useToast'

type DryRunResponse = { valid: boolean; yaml: string; errors: VError[] }
type CreateResponse = { id: string }

type FlowOptions<Payload, Result extends CreateResponse> = {
  entityLabel: string
  buildPayload: () => Payload
  dryRun: (payload: Payload) => Promise<DryRunResponse>
  create: (payload: Payload) => Promise<Result>
  onCreated?: (id: string) => void
}

export function useEntityCreateFlow<Payload, Result extends CreateResponse>(
  options: FlowOptions<Payload, Result>,
) {
  const { showToast } = useToast()
  const validationErrors = ref<VError[]>([])
  const generalError = ref<string | null>(null)
  const previewYamlStr = ref('')
  const previewing = ref(false)
  const creating = ref(false)

  async function previewYaml() {
    previewing.value = true
    validationErrors.value = []
    generalError.value = null
    try {
      const resp = await options.dryRun(options.buildPayload())
      if (resp.valid) {
        previewYamlStr.value = resp.yaml
      } else {
        validationErrors.value = resp.errors
        previewYamlStr.value = ''
        showToast(`${options.entityLabel} validation failed. Review fields and try again.`, 'error')
      }
    } catch (err: unknown) {
      generalError.value = toUserErrorMessage(err)
      showToast(`Preview failed: ${generalError.value}`, 'error')
    } finally {
      previewing.value = false
    }
  }

  async function createEntity() {
    creating.value = true
    validationErrors.value = []
    generalError.value = null
    try {
      const resp = await options.create(options.buildPayload())
      showToast(`${options.entityLabel} "${resp.id}" created successfully`, 'success')
      options.onCreated?.(resp.id)
      return resp
    } catch (err: unknown) {
      if (err instanceof ApiError && err.validationErrors.length > 0) {
        validationErrors.value = err.validationErrors
        showToast('Create failed validation. Please review required fields.', 'error')
      } else if (err instanceof ApiError) {
        generalError.value = err.detail
        showToast(`Create failed: ${err.detail}`, 'error')
      } else {
        generalError.value = toUserErrorMessage(err)
        showToast(`Create failed: ${generalError.value}`, 'error')
      }
      return null
    } finally {
      creating.value = false
    }
  }

  function resetFlowState() {
    validationErrors.value = []
    generalError.value = null
    previewYamlStr.value = ''
  }

  return {
    validationErrors,
    generalError,
    previewYamlStr,
    previewing,
    creating,
    previewYaml,
    createEntity,
    resetFlowState,
  }
}
