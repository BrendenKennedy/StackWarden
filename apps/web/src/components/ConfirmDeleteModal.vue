<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('cancel')" @keydown="onKeydown">
      <div
        ref="dialogRef"
        class="modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-delete-modal-title"
      >
        <div class="modal-header">
          <h3 id="confirm-delete-modal-title">Confirm Delete</h3>
        </div>
        <div class="modal-body">
          <p>
            Delete {{ entityLabel }} <code>{{ targetId }}</code>?
          </p>
          <p class="warning-text">This action cannot be undone.</p>
        </div>
        <div class="modal-footer">
          <button class="btn" @click="$emit('cancel')" :disabled="loading">Cancel</button>
          <button class="btn btn-danger" @click="$emit('confirm')" :disabled="loading">
            {{ loading ? 'Deleting...' : `Delete ${entityLabelTitle}` }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const props = withDefaults(defineProps<{
  show: boolean
  targetId: string
  loading: boolean
  entityLabel?: string
}>(), {
  entityLabel: 'profile',
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
const { onKeydown } = useModalFocusTrap(dialogRef, toRef(props, 'show'), () => emit('cancel'))

const entityLabelTitle = computed(() =>
  props.entityLabel.charAt(0).toUpperCase() + props.entityLabel.slice(1),
)
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
  border-radius: var(--radius-md);
  width: 90%;
  max-width: 520px;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}

.modal-header h3 {
  margin: 0;
  font-size: 1rem;
}

.modal-body {
  padding: 1rem 1.25rem;
}

.warning-text {
  color: var(--error);
  margin-bottom: 0;
}

.modal-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

</style>

