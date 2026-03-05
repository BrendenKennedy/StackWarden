<template>
  <div class="toast-container" aria-live="polite" aria-atomic="true">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast-item"
      :class="`toast-${toast.type}`"
    >
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts } = useToast()
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}

.toast-item {
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  font-weight: 600;
  pointer-events: auto;
  animation: toast-in 0.25s ease-out;
  max-width: 400px;
  box-shadow: var(--shadow-md);
}

.toast-success {
  background: #16432a;
  color: var(--success);
  border: 1px solid var(--success);
}

.toast-error {
  background: #3b1c1c;
  color: var(--error);
  border: 1px solid var(--error);
}

.toast-warning {
  background: #3b2e10;
  color: var(--warning);
  border: 1px solid var(--warning);
}

.toast-info {
  background: #2a3141;
  color: var(--info);
  border: 1px solid var(--info);
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(1rem);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
