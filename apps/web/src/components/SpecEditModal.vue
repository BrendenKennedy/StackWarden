<template>
  <Teleport to="body">
  <div
    v-if="show"
    class="spec-edit-modal-overlay"
    @click.self="cancel"
    @keydown="onKeydown"
  >
    <div ref="modalRef" class="spec-edit-modal card" role="dialog" aria-modal="true" :aria-labelledby="`spec-edit-modal-title-${entity}`">
      <div class="spec-edit-modal-header">
        <h2 :id="`spec-edit-modal-title-${entity}`" class="spec-edit-modal-title">Edit {{ entity.slice(0, -1) }}: {{ id }}</h2>
        <button class="btn" @click="cancel">Cancel</button>
      </div>
      <div v-if="loading" class="empty-state">Loading editable spec...</div>
      <template v-else>
        <textarea v-model="raw" class="spec-editor" />
        <div v-if="error" class="edit-error">{{ error }}</div>
        <div class="spec-edit-modal-actions">
          <button class="btn" @click="cancel">Cancel</button>
          <button class="btn btn-primary" :disabled="saving" @click="save">
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
        </div>
      </template>
    </div>
  </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { layers as layersApi, profiles as profilesApi, stacks as stacksApi } from '@/api/endpoints'
import { toUserErrorMessage } from '@/utils/errors'
import { ApiError } from '@/api/client'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const props = defineProps<{
  show: boolean
  entity: 'profiles' | 'stacks' | 'layers'
  id: string | null
}>()

const emit = defineEmits<{
  close: []
  saved: []
}>()

const modalRef = ref<HTMLElement | null>(null)
const { onKeydown } = useModalFocusTrap(modalRef, () => props.show, () => emit('close'))

const loading = ref(false)
const saving = ref(false)
const raw = ref('')
const error = ref('')

async function loadSpec() {
  if (!props.id) return
  loading.value = true
  error.value = ''
  try {
    let spec: any
    if (props.entity === 'profiles') spec = await profilesApi.getSpec(props.id)
    else if (props.entity === 'stacks') spec = await stacksApi.getSpec(props.id)
    else spec = await layersApi.getSpec(props.id)
    raw.value = JSON.stringify(spec, null, 2)
  } catch (e: unknown) {
    error.value = toUserErrorMessage(e)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!props.id) return
  saving.value = true
  error.value = ''
  try {
    const payload = JSON.parse(raw.value)
    if (props.entity === 'profiles') await profilesApi.update(props.id, payload)
    else if (props.entity === 'stacks') await stacksApi.update(props.id, payload)
    else await layersApi.update(props.id, payload)
    emit('saved')
    emit('close')
  } catch (e: unknown) {
    if (e instanceof ApiError) error.value = e.detail
    else if (e instanceof SyntaxError) error.value = 'Invalid JSON payload'
    else error.value = toUserErrorMessage(e)
  } finally {
    saving.value = false
  }
}

function cancel() {
  emit('close')
}

watch(() => [props.show, props.entity, props.id] as const, ([show, , id]) => {
  if (show && id) {
    loadSpec()
  } else {
    raw.value = ''
    error.value = ''
  }
}, { immediate: true })
</script>

<style scoped>
.spec-edit-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
}

.spec-edit-modal {
  width: min(760px, 95vw);
  max-height: 90vh;
  overflow-y: auto;
}

.spec-edit-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.spec-edit-modal-title {
  font-size: var(--font-size-lg);
  margin: 0;
}

.spec-editor {
  width: 100%;
  min-height: 400px;
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

.spec-edit-modal-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  flex-wrap: wrap;
}
</style>
