<template>
  <EntityCreateFlowWrapper
    :show="show"
    spec-folder="stacks"
    :entity-id="form.id"
    :flow="flowHandle"
    @cancel="$emit('cancel')"
    @created="$emit('created', $event)"
  >
    <template #wizard="{ show: wizardShow, onComplete }">
      <StackWizardModal
        :show="wizardShow"
        :form="form"
        :available-blocks="availableBlocks"
        :block-catalog="blockCatalog"
        :create-contracts="createContracts"
        :auth-enabled="authEnabled"
        :can-create="canCreate"
        :composing="composing"
        :dependency-conflicts="dependencyConflicts"
        :tuple-conflicts="tupleConflicts"
        :runtime-conflicts="runtimeConflicts"
        :resolved-spec="composedResolvedSpec"
        @cancel="$emit('cancel')"
        @complete="onComplete"
      />
    </template>
  </EntityCreateFlowWrapper>
</template>

<script setup lang="ts">
import EntityCreateFlowWrapper from '@/components/EntityCreateFlowWrapper.vue'
import StackWizardModal from '@/components/StackWizardModal.vue'
import { useStackCreateFlow } from '@/composables/useStackCreateFlow'

defineProps<{ show: boolean }>()
defineEmits<{
  cancel: []
  created: [id: string]
}>()

const flow = useStackCreateFlow()

const form = flow.form
const availableBlocks = flow.availableBlocks
const blockCatalog = flow.blockCatalog
const createContracts = flow.createContracts
const authEnabled = flow.authEnabled
const canCreate = flow.canCreate
const composing = flow.composing
const dependencyConflicts = flow.dependencyConflicts
const tupleConflicts = flow.tupleConflicts
const runtimeConflicts = flow.runtimeConflicts
const composedResolvedSpec = flow.composedResolvedSpec

const flowHandle = {
  generalError: flow.generalError,
  validationErrors: flow.validationErrors,
  previewYamlStr: flow.previewYamlStr,
  creating: flow.creating,
  metadataLoaded: flow.metadataLoaded,
  loadMetadata: flow.loadMetadata,
  resetForNewSession: flow.resetForNewSession,
  previewYaml: flow.previewYaml,
  createEntity: flow.createStack,
}
</script>
