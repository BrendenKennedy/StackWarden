<template>
  <LayerCreateFlowModal v-bind="attrs" />
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'
import LayerCreateFlowModal from '@/components/LayerCreateFlowModal.vue'

const attrs = useAttrs()
</script>
