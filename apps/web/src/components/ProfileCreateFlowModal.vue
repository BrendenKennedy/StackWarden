<template>
  <EntityCreateFlowWrapper
    :show="show"
    spec-folder="profiles"
    :entity-id="form.id"
    :flow="flowHandle"
    @cancel="$emit('cancel')"
    @created="$emit('created', $event)"
  >
    <template #wizard="{ show: wizardShow, onComplete }">
      <ProfileWizardModal
        :show="wizardShow"
        :form="form"
        :enums="enums"
        :hints="detectionHints"
        :detecting-hints="flow.detectingHints.value"
        :detect-hardware="flow.refreshDetectionHints"
        :contracts="createContracts"
        :catalogs="hardwareCatalog"
        @cancel="$emit('cancel')"
        @complete="onComplete"
      />
    </template>
  </EntityCreateFlowWrapper>
</template>

<script setup lang="ts">
import EntityCreateFlowWrapper from '@/components/EntityCreateFlowWrapper.vue'
import ProfileWizardModal from '@/components/ProfileWizardModal.vue'
import { useProfileCreateFlow } from '@/composables/useProfileCreateFlow'

defineProps<{ show: boolean }>()
defineEmits<{
  cancel: []
  created: [id: string]
}>()

const flow = useProfileCreateFlow()

const form = flow.form
const enums = flow.enums
const detectionHints = flow.detectionHints
const createContracts = flow.createContracts
const hardwareCatalog = flow.hardwareCatalog

const flowHandle = {
  generalError: flow.generalError,
  validationErrors: flow.validationErrors,
  previewYamlStr: flow.previewYamlStr,
  creating: flow.creating,
  metadataLoaded: flow.metadataLoaded,
  loadMetadata: flow.loadMetadata,
  resetForNewSession: flow.resetForNewSession,
  previewYaml: flow.previewYaml,
  createEntity: flow.createProfile,
}
</script>
