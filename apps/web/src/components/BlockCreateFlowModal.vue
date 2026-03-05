<template>
  <EntityCreateFlowWrapper
    :show="show"
    spec-folder="blocks"
    :entity-id="form.id"
    :flow="flowHandle"
    @cancel="$emit('cancel')"
    @created="$emit('created', $event)"
  >
    <template #wizard="{ show: wizardShow, onComplete }">
      <BlockWizardModal
        :show="wizardShow"
        :form="form"
        :env-entries="envEntries"
        :contracts="createContracts"
        :block-catalog="blockCatalog"
        :selected-category="selectedCategory"
        :search-term="searchTerm"
        :selected-preset-id="selectedPresetId"
        :selected-profile="selectedProfile"
        @update:env-entries="envEntries = $event"
        @update:selected-category="selectedCategory = $event"
        @update:search-term="searchTerm = $event"
        @update:selected-preset-id="selectedPresetId = $event"
        @update:selected-profile="selectedProfile = $event"
        @cancel="$emit('cancel')"
        @complete="onComplete"
      />
    </template>
  </EntityCreateFlowWrapper>
</template>

<script setup lang="ts">
import EntityCreateFlowWrapper from '@/components/EntityCreateFlowWrapper.vue'
import BlockWizardModal from '@/components/BlockWizardModal.vue'
import { useBlockCreateFlow } from '@/composables/useBlockCreateFlow'

defineProps<{ show: boolean }>()
defineEmits<{
  cancel: []
  created: [id: string]
}>()

const flow = useBlockCreateFlow()

const form = flow.form
const envEntries = flow.envEntries
const createContracts = flow.createContracts
const blockCatalog = flow.blockCatalog
const selectedCategory = flow.selectedCategory
const searchTerm = flow.searchTerm
const selectedPresetId = flow.selectedPresetId
const selectedProfile = flow.selectedProfile

const flowHandle = {
  generalError: flow.generalError,
  validationErrors: flow.validationErrors,
  previewYamlStr: flow.previewYamlStr,
  creating: flow.creating,
  metadataLoaded: flow.metadataLoaded,
  loadMetadata: flow.loadMetadata,
  resetForNewSession: flow.resetForNewSession,
  previewYaml: flow.previewYaml,
  createEntity: flow.createBlock,
}
</script>
