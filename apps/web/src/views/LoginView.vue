<template>
  <AuthCard
    title="Sign in"
    subtitle="Use the admin account credentials to access StackWarden."
    :username="username"
    :password="password"
    username-id="signin-username"
    password-id="signin-password"
    username-autocomplete="username"
    password-autocomplete="current-password"
    submit-label="Sign in"
    submitting-label="Signing in..."
    :submitting="submitting"
    :error="error"
    @update:username="username = $event"
    @update:password="password = $event"
    @submit="submit"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthCard from '@/components/AuthCard.vue'
import { useAuthSession } from '@/composables/useAuthSession'
import { toUserErrorMessage } from '@/utils/errors'

const router = useRouter()
const { login } = useAuthSession()
const username = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref('')

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await login(username.value.trim(), password.value)
    await router.replace('/dashboard')
  } catch (err) {
    error.value = toUserErrorMessage(err)
  } finally {
    submitting.value = false
  }
}

</script>
