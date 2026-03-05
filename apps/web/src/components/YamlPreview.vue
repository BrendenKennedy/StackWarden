<template>
  <div class="yaml-preview" v-if="yaml">
    <div class="yaml-preview-header">
      <span>YAML Preview</span>
      <button class="btn yaml-preview-copy" @click="copyYaml">
        {{ copied ? 'Copied' : 'Copy' }}
      </button>
    </div>
    <pre class="yaml-preview-content">{{ yaml }}</pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  yaml: string
}>()

const copied = ref(false)

async function copyYaml() {
  try {
    await navigator.clipboard.writeText(props.yaml)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // fallback: ignore clipboard errors
  }
}
</script>

<style scoped>
.yaml-preview {
  margin-top: 1rem;
}

.yaml-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.yaml-preview-content {
  background: #0a0c10;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  color: var(--text-secondary);
  max-height: 500px;
  overflow-y: auto;
}

.yaml-preview-copy {
  padding: 0.25rem 0.5rem;
  font-size: var(--font-size-xs);
}
</style>
