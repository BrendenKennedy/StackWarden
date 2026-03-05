<template>
  <AuthCard
    title="Create admin account"
    subtitle="First-time setup: create your StackWarden admin credentials."
    :username="username"
    :password="password"
    username-id="setup-username"
    password-id="setup-password"
    username-autocomplete="username"
    password-autocomplete="new-password"
    submit-label="Create admin account"
    submitting-label="Creating account..."
    :submitting="submitting"
    :error="error"
    :username-minlength="3"
    :password-minlength="10"
    @update:username="username = $event"
    @update:password="password = $event"
    @submit="submit"
  >
    <template #extra-fields>
      <div class="auth-field auth-field-spaced">
        <label for="setup-confirm-password" class="auth-label">Confirm Password</label>
        <input
          id="setup-confirm-password"
          v-model="confirmPassword"
          class="auth-input"
          type="password"
          autocomplete="new-password"
          required
          minlength="10"
        />
      </div>
    </template>
  </AuthCard>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthCard from '@/components/AuthCard.vue'
import { useAuthSession } from '@/composables/useAuthSession'
import { toUserErrorMessage } from '@/utils/errors'

const router = useRouter()
const { setup } = useAuthSession()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return
  }

  submitting.value = true
  error.value = ''
  try {
    await setup(username.value.trim(), password.value)
    await router.replace('/dashboard')
  } catch (err) {
    error.value = toUserErrorMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
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
</style>
