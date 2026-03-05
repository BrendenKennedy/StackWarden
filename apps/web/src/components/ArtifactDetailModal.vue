<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="artifact-modal-overlay"
      @click.self="close"
      @keydown="onKeydown"
    >
      <div ref="modalRef" class="artifact-modal card" role="dialog" aria-modal="true" aria-labelledby="artifact-modal-title">
        <div class="artifact-modal-header">
          <h2 id="artifact-modal-title" class="artifact-modal-title">
            Artifact Detail
            <span v-if="artifactFromContent" class="artifact-tag">{{ artifactFromContent.tag }}</span>
          </h2>
          <button class="btn" @click="close">Close</button>
        </div>

        <ArtifactDetailContent
          ref="contentRef"
          :artifact-id="artifactId"
          :on-deleted="onDeleted"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, type Ref } from 'vue'
import type { ArtifactDetail } from '@/api/types'
import ArtifactDetailContent from '@/components/ArtifactDetailContent.vue'
import { useModalFocusTrap } from '@/composables/useModalFocusTrap'

const props = defineProps<{
  show: boolean
  artifactId: string | null
}>()

const emit = defineEmits<{
  close: []
  deleted: []
}>()

const modalRef = ref<HTMLElement | null>(null)
const contentRef = ref<InstanceType<typeof ArtifactDetailContent> | null>(null)
const { onKeydown } = useModalFocusTrap(modalRef, () => props.show, () => emit('close'))

const artifactFromContent = computed(() => {
  const comp = contentRef.value as { artifact?: Ref<ArtifactDetail | null> } | null
  return comp?.artifact?.value ?? null
})

function close() {
  emit('close')
}

function onDeleted() {
  emit('deleted')
  emit('close')
}
</script>

<style scoped>
.artifact-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
}

.artifact-modal {
  width: min(800px, 95vw);
  max-height: 90vh;
  overflow-y: auto;
}

.artifact-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.artifact-modal-title {
  font-size: var(--font-size-lg);
  margin: 0;
}

.artifact-tag {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-left: var(--space-2);
}
</style>
