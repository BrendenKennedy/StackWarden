<template>
  <div class="auth-page">
    <div class="card auth-card">
      <h1 class="auth-title">{{ title }}</h1>
      <p class="auth-subtitle">{{ subtitle }}</p>
      <form class="auth-form" @submit.prevent="$emit('submit')">
        <div class="auth-field">
          <label :for="usernameId" class="auth-label">{{ usernameLabel }}</label>
          <input
            :id="usernameId"
            :value="username"
            class="auth-input"
            type="text"
            :autocomplete="usernameAutocomplete"
            :minlength="usernameMinlength"
            required
            @input="$emit('update:username', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <div class="auth-field auth-field-spaced">
          <label :for="passwordId" class="auth-label">{{ passwordLabel }}</label>
          <input
            :id="passwordId"
            :value="password"
            class="auth-input"
            type="password"
            :autocomplete="passwordAutocomplete"
            :minlength="passwordMinlength"
            required
            @input="$emit('update:password', ($event.target as HTMLInputElement).value)"
          />
        </div>
        <slot name="extra-fields" />
        <button class="btn auth-submit" type="submit" :disabled="submitting">
          {{ submitting ? submittingLabel : submitLabel }}
        </button>
      </form>
      <p v-if="error" class="auth-error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
  username: string
  password: string
  usernameId: string
  passwordId: string
  usernameAutocomplete: string
  passwordAutocomplete: string
  submitLabel: string
  submittingLabel: string
  submitting: boolean
  error: string
  usernameLabel?: string
  passwordLabel?: string
  usernameMinlength?: number
  passwordMinlength?: number
}>()

defineEmits<{
  (event: 'update:username', value: string): void
  (event: 'update:password', value: string): void
  (event: 'submit'): void
}>()
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1.25rem;
}

.auth-card {
  width: min(30rem, 100%);
  padding: 1.5rem;
}

.auth-title {
  margin-bottom: 0.35rem;
  text-align: center;
}

.auth-subtitle {
  color: var(--text-muted);
  margin-bottom: 1.25rem;
  text-align: center;
}

.auth-form {
  width: min(23rem, 100%);
  margin: 0 auto;
}

.auth-field {
  display: grid;
  gap: 0.4rem;
}

.auth-field-spaced {
  margin-top: 1.1rem;
}

.auth-label {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.auth-input {
  width: 100%;
}

.auth-submit {
  width: 100%;
  margin-top: 1.1rem;
}

.auth-error {
  color: #fca5a5;
  margin-top: 0.85rem;
  text-align: center;
}
</style>
