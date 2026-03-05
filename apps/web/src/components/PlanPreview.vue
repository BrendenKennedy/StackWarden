<template>
  <div class="card" v-if="plan">
    <h3 class="card-title">Plan Preview</h3>
    <dl class="detail-grid">
      <dt>Tag</dt>
      <dd>{{ plan.tag }}</dd>
      <dt>Fingerprint</dt>
      <dd>{{ plan.fingerprint }}</dd>
      <dt>Base Image</dt>
      <dd>{{ plan.base_image }}</dd>
      <dt>Builder</dt>
      <dd>{{ plan.builder }}</dd>
    </dl>
    <div v-if="plan.warnings.length" class="plan-section">
      <div v-for="w in plan.warnings" :key="w" class="plan-warning">
        {{ w }}
      </div>
    </div>
    <div v-if="plan.steps.length" class="plan-section">
      <h4 class="plan-subtitle">Steps</h4>
      <div v-for="(s, i) in plan.steps" :key="i" class="plan-step">
        {{ i + 1 }}. {{ s.type }}<span v-if="s.image"> — {{ s.image }}</span>
      </div>
    </div>
    <div v-if="plan.rationale" class="plan-section">
      <details>
        <summary class="plan-summary">Rationale (explain)</summary>
        <pre class="json-viewer plan-code">{{ JSON.stringify(plan.rationale, null, 2) }}</pre>
      </details>
    </div>
    <div v-if="plan.tuple_decision && Object.keys(plan.tuple_decision).length" class="plan-section">
      <details>
        <summary class="plan-summary">Tuple Explanation</summary>
        <pre class="json-viewer plan-code">{{ JSON.stringify(plan.tuple_decision, null, 2) }}</pre>
      </details>
    </div>
    <div
      v-if="plan.build_optimization && Object.keys(plan.build_optimization).length"
      class="plan-section"
    >
      <details>
        <summary class="plan-summary">
          Build Optimization
        </summary>
        <pre class="json-viewer plan-code">{{ JSON.stringify(plan.build_optimization, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PlanResponse } from '@/api/types'

defineProps<{ plan: PlanResponse | null }>()
</script>

<style scoped>
.plan-section {
  margin-top: 0.75rem;
}

.plan-warning {
  color: var(--warning);
  font-size: var(--font-size-sm);
}

.plan-subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.plan-step {
  font-size: var(--font-size-sm);
  font-family: var(--font-mono);
}

.plan-summary {
  cursor: pointer;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.plan-code {
  margin-top: 0.5rem;
}
</style>
