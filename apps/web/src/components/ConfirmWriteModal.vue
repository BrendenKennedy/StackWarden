<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('cancel')" @keydown="onKeydown">
      <div
        ref="dialogRef"
        class="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-write-modal-title"
      >
        <div class="modal-header">
          <h3 id="confirm-write-modal-title">Confirm Write</h3>
        </div>
        <div class="modal-body">
          <p class="modal-path-label">File will be written to:</p>
          <code class="modal-path">{{ targetPath }}</code>

          <div class="yaml-preview-section" v-if="yaml">
            <p class="modal-preview-label">YAML contents:</p>
            <pre class="modal-yaml">{{ yaml }}</pre>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="$emit('cancel')">Cancel</button>
          <button class="btn btn-primary" @click="$emit('confirm')" :disabled="loading">
            {{ loading ? 'Writing...' : 'Write File' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, toRef } from 'vue'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const props = defineProps<{
  show: boolean
  targetPath: string
  yaml: string
  loading: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
const { onKeydown } = useModalFocusTrap(dialogRef, toRef(props, 'show'), () => emit('cancel'))
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}

.modal-dialog {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  width: 90%;
  max-width: 700px;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}

.modal-header h3 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.modal-body {
  padding: 1.25rem;
}

.modal-path-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.modal-path {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--accent);
  background: var(--bg-tertiary);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  margin-bottom: 1rem;
  word-break: break-all;
}

.modal-preview-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
}

.modal-yaml {
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
  max-height: 350px;
  overflow-y: auto;
}

.modal-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
