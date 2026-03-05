<template>
  <div>
    <ArtifactDetailContent :artifact-id="props.id" :on-deleted="onDeleted">
      <template #header="{ artifact }">
        <h1 class="page-title">
          Artifact Detail
          <span v-if="artifact" class="artifact-tag">{{ artifact.tag }}</span>
        </h1>
      </template>
    </ArtifactDetailContent>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import ArtifactDetailContent from '@/components/ArtifactDetailContent.vue'

const props = defineProps<{ id: string }>()
const router = useRouter()

function onDeleted() {
  router.push({ name: 'catalog' })
}
</script>

<style scoped>
.artifact-tag {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-left: var(--space-2);
}
</style>
