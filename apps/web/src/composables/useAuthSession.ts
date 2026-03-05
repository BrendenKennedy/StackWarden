import { computed, ref } from 'vue'
import { auth } from '@/api/endpoints'
import type { AuthSessionStatus } from '@/api/types'

const status = ref<AuthSessionStatus | null>(null)
const loading = ref(false)
const STATUS_TTL_MS = 10_000
let statusFetchedAt = 0
let inflightStatusRequest: Promise<AuthSessionStatus> | null = null

export function useAuthSession() {
  const isAuthenticated = computed(() => !!status.value?.authenticated)
  const setupRequired = computed(() => !!status.value?.setup_required)
  const username = computed(() => status.value?.username || null)

  async function refreshStatus(options?: { force?: boolean }) {
    const forceRefresh = !!options?.force
    const now = Date.now()
    if (!forceRefresh && status.value && now - statusFetchedAt < STATUS_TTL_MS) {
      return status.value
    }
    if (!forceRefresh && inflightStatusRequest) {
      return inflightStatusRequest
    }

    loading.value = true
    inflightStatusRequest = auth.status()
    try {
      status.value = await inflightStatusRequest
      statusFetchedAt = Date.now()
      return status.value
    } finally {
      inflightStatusRequest = null
      loading.value = false
    }
  }

  async function login(username: string, password: string) {
    status.value = await auth.login({ username, password })
    statusFetchedAt = Date.now()
    return status.value
  }

  async function setup(username: string, password: string) {
    status.value = await auth.setup({ username, password })
    statusFetchedAt = Date.now()
    return status.value
  }

  async function logout() {
    await auth.logout()
    status.value = { setup_required: false, authenticated: false, username: null }
    statusFetchedAt = Date.now()
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    await auth.changePassword({
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  return {
    status,
    loading,
    isAuthenticated,
    setupRequired,
    username,
    refreshStatus,
    login,
    setup,
    logout,
    changePassword,
  }
}
