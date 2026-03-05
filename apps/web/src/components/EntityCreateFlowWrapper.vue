<template>
  <slot
    name="wizard"
    :show="show && !showConfirm"
    :on-complete="onWizardComplete"
  />

  <ConfirmWriteModal
    :show="showConfirm"
    :target-path="`specs/${specFolder}/${entityId}.yaml`"
    :yaml="previewYamlStr"
    :loading="creating"
    @confirm="doCreate"
    @cancel="showConfirm = false"
  />

  <div v-if="show && generalError" class="flow-error">
    {{ generalError }}
  </div>
  <div v-if="show && validationErrors.length > 0" class="flow-error">
    {{ validationErrors[0]?.field || 'validation' }}: {{ validationErrors[0]?.message }}
  </div>
</template>

<script setup lang="ts">
import { ref, watch, type Ref } from 'vue'
import ConfirmWriteModal from '@/components/ConfirmWriteModal.vue'

export interface FlowHandle {
  generalError: Ref<string | null>
  validationErrors: Ref<Array<{ field?: string; message?: string }>>
  previewYamlStr: Ref<string>
  creating: Ref<boolean>
  metadataLoaded: Ref<boolean>
  loadMetadata: () => Promise<void>
  resetForNewSession: () => void
  previewYaml: () => Promise<void>
  createEntity: () => Promise<{ id: string } | null>
}

const props = defineProps<{
  show: boolean
  specFolder: string
  entityId: string
  flow: FlowHandle
}>()

const emit = defineEmits<{
  cancel: []
  created: [id: string]
}>()

const showConfirm = ref(false)

const generalError = props.flow.generalError
const validationErrors = props.flow.validationErrors
const previewYamlStr = props.flow.previewYamlStr
const creating = props.flow.creating

watch(
  () => props.show,
  async (open) => {
    if (!open) {
      showConfirm.value = false
      props.flow.resetForNewSession()
      return
    }
    if (!props.flow.metadataLoaded.value) {
      await props.flow.loadMetadata()
    }
  },
)

async function onWizardComplete() {
  await props.flow.previewYaml()
  if (props.flow.validationErrors.value.length === 0 && props.flow.previewYamlStr.value) {
    showConfirm.value = true
  }
}

async function doCreate() {
  const result = await props.flow.createEntity()
  if (!result) {
    showConfirm.value = false
    return
  }
  props.flow.resetForNewSession()
  showConfirm.value = false
  emit('created', result.id)
}
</script>

<style scoped>
.flow-error {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 1rem;
  z-index: 9400;
  background: #3b1117;
  border: 1px solid var(--error);
  color: var(--error);
  border-radius: var(--radius);
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}
</style>
