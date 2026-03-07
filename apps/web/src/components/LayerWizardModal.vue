<template>
  <BlockWizardModal v-bind="attrs" />
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'
import BlockWizardModal from '@/components/BlockWizardModal.vue'

const attrs = useAttrs()
</script>
