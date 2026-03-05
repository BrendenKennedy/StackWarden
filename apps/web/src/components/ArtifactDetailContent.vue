<template>
  <slot v-if="$slots.header" name="header" :artifact="artifact" />
  <div v-if="loading" class="empty-state">Loading...</div>
  <div v-else-if="loadError" class="auth-warning">{{ loadError }}</div>
  <div v-else-if="!artifact" class="empty-state">Artifact not found.</div>
  <template v-else>
    <div class="card">
      <dl class="detail-grid">
        <dt>Tag</dt>
        <dd>
          {{ artifact.tag }}
          <button class="btn copy-btn" @click="copy(artifact.tag)">Copy</button>
        </dd>
        <dt>Fingerprint</dt>
        <dd>
          {{ artifact.fingerprint }}
          <button class="btn copy-btn" @click="copy(artifact.fingerprint)">Copy</button>
        </dd>
        <dt>Status</dt>
        <dd><JobBadge :status="artifact.status" /></dd>
        <dt>Profile</dt>
        <dd>{{ artifact.profile_id }}</dd>
        <dt>Stack</dt>
        <dd>{{ artifact.stack_id }}</dd>
        <dt>Base Image</dt>
        <dd>{{ artifact.base_image }}</dd>
        <dt>Strategy</dt>
        <dd>{{ artifact.build_strategy }}</dd>
        <dt>Created</dt>
        <dd>{{ new Date(artifact.created_at).toLocaleString() }}</dd>
        <template v-if="artifact.image_id">
          <dt>Image ID</dt>
          <dd>{{ artifact.image_id }}</dd>
        </template>
        <template v-if="artifact.digest">
          <dt>Digest</dt>
          <dd>{{ artifact.digest }}</dd>
        </template>
        <template v-if="artifact.stale_reason">
          <dt>Stale Reason</dt>
          <dd class="text-warning">{{ artifact.stale_reason }}</dd>
        </template>
        <template v-if="artifact.error_detail">
          <dt>Error</dt>
          <dd class="text-error">{{ artifact.error_detail }}</dd>
        </template>
        <template v-if="tupleSummary">
          <dt>Tuple</dt>
          <dd>{{ tupleSummary }}</dd>
        </template>
      </dl>
    </div>

    <div class="artifact-actions">
      <button class="btn" @click="runVerify" :disabled="verifying">
        {{ verifying ? 'Verifying...' : 'Verify' }}
      </button>
      <button class="btn" @click="markStale">Mark Stale</button>
      <button class="btn btn-danger" @click="deleteArtifact" :disabled="deleting">
        {{ deleting ? 'Deleting...' : 'Delete' }}
      </button>
    </div>

    <div v-if="verifyResult" class="card verify-card">
      <h3 class="verify-title">
        Verify: <span :class="verifyResult.ok ? 'text-success' : 'text-error'">
          {{ verifyResult.ok ? 'PASS' : 'FAIL' }}
        </span>
      </h3>
      <div v-if="verifyResult.errors.length">
        <div v-for="e in verifyResult.errors" :key="e" class="verify-error">{{ e }}</div>
      </div>
      <div v-if="verifyResult.warnings.length" class="verify-warnings">
        <div v-for="w in verifyResult.warnings" :key="w" class="verify-warning">{{ w }}</div>
      </div>
    </div>

    <div class="tabs" role="tablist">
      <button
        v-for="t in tabs"
        :key="t.key"
        :class="['tab', { active: activeTab === t.key }]"
        role="tab"
        type="button"
        :tabindex="activeTab === t.key ? 0 : -1"
        :aria-selected="activeTab === t.key"
        @click="loadTab(t.key)"
        @keydown.enter="loadTab(t.key)"
        @keydown.space.prevent="loadTab(t.key)"
      >
        {{ t.label }}
      </button>
    </div>
    <JsonViewer :data="tabData" :loading="tabLoading" :error="tabError" />
  </template>
</template>

<script setup lang="ts">
import { toRef } from 'vue'
import JobBadge from '@/components/JobBadge.vue'
import JsonViewer from '@/components/JsonViewer.vue'
import { useArtifactDetail } from '@/composables/useArtifactDetail'

const props = defineProps<{
  artifactId: string | null
  onDeleted?: () => void
}>()

const artifactIdRef = toRef(props, 'artifactId')

const {
  tabs,
  artifact,
  loading,
  loadError,
  verifying,
  deleting,
  verifyResult,
  activeTab,
  tabData,
  tabLoading,
  tabError,
  tupleSummary,
  loadTab,
  runVerify,
  markStale,
  deleteArtifact,
  copy,
} = useArtifactDetail(artifactIdRef, { onDeleted: props.onDeleted })

defineExpose({ artifact })
</script>

<style scoped>
.copy-btn {
  margin-left: var(--space-2);
  padding: 0.2rem 0.5rem;
  font-size: var(--font-size-xs);
}

.text-warning {
  color: var(--warning);
}

.text-error {
  color: var(--error);
}

.text-success {
  color: var(--success);
}

.artifact-actions {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.verify-card {
  margin-bottom: var(--space-4);
}

.verify-title {
  margin-bottom: var(--space-2);
}

.verify-error,
.verify-warning {
  font-size: var(--font-size-sm);
}

.verify-error {
  color: var(--error);
}

.verify-warnings {
  margin-top: var(--space-1);
}

.verify-warning {
  color: var(--warning);
}
</style>
