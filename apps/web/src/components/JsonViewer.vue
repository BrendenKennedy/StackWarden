<template>
  <div v-if="loading" class="empty-state">Loading...</div>
  <div v-else-if="error" class="message-error">{{ error }}</div>
  <pre v-else class="json-viewer">{{ formatted }}</pre>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  data: unknown
  loading?: boolean
  error?: string | null
}>()

const formatted = computed(() => {
  if (props.data === null || props.data === undefined) return ''
  return JSON.stringify(props.data, null, 2)
})
</script>
