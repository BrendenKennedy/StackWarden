<template>
  <div v-if="Object.keys(variants).length === 0" class="empty-state variant-empty">
    No configurable variants for this stack.
  </div>
  <div v-else>
    <div v-for="(def, key) in variants" :key="key" class="form-group">
      <label>{{ key }}</label>
      <template v-if="def.type === 'bool'">
        <label class="checkbox-group variant-toggle">
          <input type="checkbox" :checked="modelValue[key] ?? def.default" @change="toggle(key, ($event.target as HTMLInputElement).checked)" />
          {{ modelValue[key] ?? def.default ? 'Enabled' : 'Disabled' }}
        </label>
      </template>
      <template v-else-if="def.type === 'enum'">
        <select :value="modelValue[key] ?? def.default" @change="update(key, ($event.target as HTMLSelectElement).value)">
          <option v-for="opt in def.options" :key="opt" :value="opt">{{ opt }}</option>
        </select>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { VariantDef } from '@/api/types'

const props = defineProps<{
  variants: Record<string, VariantDef>
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{ 'update:modelValue': [val: Record<string, any>] }>()

function toggle(key: string, val: boolean) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

function update(key: string, val: string) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}
</script>

<style scoped>
.variant-empty {
  padding: var(--space-2);
}

.variant-toggle {
  margin-top: var(--space-1);
}
</style>
