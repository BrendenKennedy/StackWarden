<template>
  <div class="dynamic-list">
    <div v-for="(_, idx) in modelValue" :key="idx" class="dynamic-list-row">
      <slot :index="idx" :item="modelValue[idx]" />
      <button class="btn dynamic-list-remove" @click="removeItem(idx)" title="Remove">&times;</button>
    </div>
    <button class="btn dynamic-list-add" @click="addItem">+ {{ addLabel }}</button>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: any[]
  addLabel: string
  defaultItem: () => any
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any[]]
}>()

function addItem() {
  emit('update:modelValue', [...props.modelValue, props.defaultItem()])
}

function removeItem(idx: number) {
  const copy = [...props.modelValue]
  copy.splice(idx, 1)
  emit('update:modelValue', copy)
}
</script>

<style scoped>
.dynamic-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.dynamic-list-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.dynamic-list-remove {
  padding: 0.2rem 0.5rem;
  font-size: 1rem;
  line-height: 1;
  color: var(--error);
  background: transparent;
  border: 1px solid transparent;
}

.dynamic-list-remove:hover {
  border-color: var(--error);
  background: #3b1c1c;
}

.dynamic-list-add {
  align-self: flex-start;
  font-size: 0.75rem;
  padding: 0.3rem 0.75rem;
  margin-top: 0.25rem;
}
</style>
