<template>
  <div class="log-stream-wrapper">
    <div class="log-header">
      <JobBadge :status="status" />
      <label class="checkbox-group log-autoscroll">
        <input type="checkbox" v-model="autoScroll" /> Auto-scroll
      </label>
    </div>
    <div ref="logEl" class="log-panel">
      <div v-for="(line, i) in lines" :key="i" class="log-line">{{ line.line }}</div>
      <div v-if="error" class="log-line log-error">ERROR: {{ error }}</div>
      <div v-if="result" class="log-line log-success">
        Build complete: {{ result.tag }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, toRef } from 'vue'
import { useJobStream } from '@/composables/useJobStream'
import JobBadge from './JobBadge.vue'

const props = defineProps<{ jobId: string }>()

const { lines, status, result, error } = useJobStream(toRef(props, 'jobId'))
const autoScroll = ref(true)
const logEl = ref<HTMLElement | null>(null)

watch(lines, async () => {
  if (autoScroll.value && logEl.value) {
    await nextTick()
    logEl.value.scrollTop = logEl.value.scrollHeight
  }
}, { deep: true })
</script>

<style scoped>
.log-stream-wrapper {
  margin-top: 1rem;
}
.log-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.log-autoscroll {
  margin-left: auto;
}

.log-error {
  color: var(--error);
}

.log-success {
  color: var(--success);
}
</style>
