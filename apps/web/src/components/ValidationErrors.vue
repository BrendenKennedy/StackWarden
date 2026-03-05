<template>
  <div v-if="errors.length > 0" class="validation-errors">
    <div class="validation-errors-title">Validation Errors</div>
    <ul>
      <li v-for="(err, i) in errors" :key="i">
        <span class="validation-field">{{ err.field }}</span>
        <span class="validation-msg">{{ err.message }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { ValidationError } from '@/api/types'

defineProps<{
  errors: ValidationError[]
}>()
</script>

<style scoped>
.validation-errors {
  background: #3b1c1c;
  border: 1px solid var(--error);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}

.validation-errors-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--error);
  margin-bottom: 0.5rem;
}

.validation-errors ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.validation-errors li {
  font-size: 0.8125rem;
  padding: 0.2rem 0;
  display: flex;
  gap: 0.5rem;
}

.validation-field {
  color: var(--warning);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  flex-shrink: 0;
}

.validation-field::after {
  content: ':';
}

.validation-msg {
  color: var(--text-primary);
}
</style>
