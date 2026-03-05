<template>
  <div>
    <h1 class="page-title">Edit {{ entity.slice(0, -1) }}: {{ id }}</h1>
    <div class="card edit-actions">
      <router-link class="btn" :to="`/${entity}/${id}`">Cancel</router-link>
      <button class="btn btn-primary" :disabled="saving" @click="save">
        {{ saving ? 'Saving...' : 'Save Changes' }}
      </button>
    </div>
    <div class="card">
      <div v-if="loading" class="empty-state">Loading editable spec...</div>
      <template v-else>
        <textarea v-model="raw" class="spec-editor" />
        <div v-if="error" class="edit-error">{{ error }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { blocks as blocksApi, profiles as profilesApi, stacks as stacksApi } from '@/api/endpoints'
import { ApiError } from '@/api/client'

const props = defineProps<{ entity: 'profiles' | 'stacks' | 'blocks'; id: string }>()
const router = useRouter()
const entity = computed(() => props.entity)
const id = computed(() => props.id)

const loading = ref(true)
const saving = ref(false)
const raw = ref('')
const error = ref('')

async function loadSpec() {
  loading.value = true
  error.value = ''
  try {
    let spec: any
    if (entity.value === 'profiles') spec = await profilesApi.getSpec(id.value)
    else if (entity.value === 'stacks') spec = await stacksApi.getSpec(id.value)
    else spec = await blocksApi.getSpec(id.value)
    raw.value = JSON.stringify(spec, null, 2)
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const payload = JSON.parse(raw.value)
    if (entity.value === 'profiles') await profilesApi.update(id.value, payload)
    else if (entity.value === 'stacks') await stacksApi.update(id.value, payload)
    else await blocksApi.update(id.value, payload)
    router.push(`/${entity.value}/${id.value}`)
  } catch (e: any) {
    if (e instanceof ApiError) error.value = e.detail
    else if (e instanceof SyntaxError) error.value = 'Invalid JSON payload'
    else error.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(loadSpec)
</script>

<style scoped>
.edit-actions {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.spec-editor {
  width: 100%;
  min-height: 500px;
  background: #0a0c10;
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75rem;
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.edit-error {
  margin-top: 0.75rem;
  color: var(--error);
}
</style>
