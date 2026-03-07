<template>
  <div v-if="showAppShell" class="app-layout">
    <header class="mobile-header">
      <button
        class="btn btn-ghost mobile-menu-btn"
        type="button"
        aria-label="Toggle navigation menu"
        @click="isSidebarOpen = !isSidebarOpen"
      >
        {{ isSidebarOpen ? 'Close' : 'Menu' }}
      </button>
      <div class="mobile-brand"><span>Stack</span>Warden</div>
    </header>
    <div v-if="isSidebarOpen" class="sidebar-overlay" @click="isSidebarOpen = false"></div>
    <aside
      class="sidebar"
      :class="{ 'sidebar-open': isSidebarOpen, 'sidebar-collapsed': isSidebarCollapsed }"
      @click="handleSidebarClick"
    >
      <div
        class="sidebar-brand sidebar-brand-row"
      >
        <div class="sidebar-brand-text">
          <span class="sidebar-brand-full">
            <span class="sidebar-brand-stack">Stack</span><span class="sidebar-brand-warden">Warden</span>
          </span>
          <span class="sidebar-brand-compact">
            <span class="sidebar-brand-compact-stack">S</span><span class="sidebar-brand-compact-warden">W</span>
          </span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <div class="sidebar-nav-top">
          <router-link to="/dashboard" aria-label="Dashboard" title="Dashboard" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <rect x="3" y="3" width="8" height="8" rx="1.5" />
              <rect x="13" y="3" width="8" height="5" rx="1.5" />
              <rect x="13" y="10" width="8" height="11" rx="1.5" />
              <rect x="3" y="13" width="8" height="8" rx="1.5" />
            </svg>
            <span class="sidebar-nav-label">Dashboard</span>
          </router-link>
          <router-link to="/catalog" aria-label="Catalog" title="Catalog" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <path d="M4 6H20" />
              <path d="M4 12H20" />
              <path d="M4 18H20" />
            </svg>
            <span class="sidebar-nav-label">Catalog</span>
          </router-link>
          <router-link to="/stacks" aria-label="Stacks" title="Stacks" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <path d="M12 3L3 8L12 13L21 8L12 3Z" />
              <path d="M3 12L12 17L21 12" />
              <path d="M3 16L12 21L21 16" />
            </svg>
            <span class="sidebar-nav-label">Stacks</span>
          </router-link>
          <router-link to="/layers" aria-label="Layers" title="Layers" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <path d="M12 6L4 10L12 14L20 10L12 6Z" />
            </svg>
            <span class="sidebar-nav-label">Layers</span>
          </router-link>
          <router-link to="/profiles" aria-label="Profiles" title="Profiles" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <path d="M16 21V19C16 17.34 14.66 16 13 16H7C5.34 16 4 17.34 4 19V21" />
              <circle cx="10" cy="10" r="3" />
              <path d="M20 8V14" />
              <path d="M23 11H17" />
            </svg>
            <span class="sidebar-nav-label">Profiles</span>
          </router-link>
        </div>
        <div class="sidebar-nav-bottom">
          <div class="sidebar-divider"></div>
          <router-link to="/settings" aria-label="Settings" title="Settings" @click="isSidebarOpen = false">
            <svg viewBox="0 0 24 24" class="sidebar-nav-icon" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15A1.66 1.66 0 0 0 19.73 16.82L19.79 16.88A2 2 0 1 1 16.96 19.71L16.9 19.65A1.66 1.66 0 0 0 15.08 19.32A1.66 1.66 0 0 0 14 20.85V21A2 2 0 1 1 10 21V20.91A1.66 1.66 0 0 0 8.92 19.38A1.66 1.66 0 0 0 7.1 19.71L7.04 19.77A2 2 0 1 1 4.21 16.94L4.27 16.88A1.66 1.66 0 0 0 4.6 15.06A1.66 1.66 0 0 0 3.07 14H3A2 2 0 1 1 3 10H3.09A1.66 1.66 0 0 0 4.62 8.92A1.66 1.66 0 0 0 4.29 7.1L4.23 7.04A2 2 0 1 1 7.06 4.21L7.12 4.27A1.66 1.66 0 0 0 8.94 4.6H9A1.66 1.66 0 0 0 10 3.09V3A2 2 0 1 1 14 3V3.09A1.66 1.66 0 0 0 15.08 4.62A1.66 1.66 0 0 0 16.9 4.29L16.96 4.23A2 2 0 1 1 19.79 7.06L19.73 7.12A1.66 1.66 0 0 0 19.4 8.94V9A1.66 1.66 0 0 0 20.93 10H21A2 2 0 1 1 21 14H20.91A1.66 1.66 0 0 0 19.38 15Z" />
            </svg>
            <span class="sidebar-nav-label">Settings</span>
          </router-link>
        </div>
      </nav>
    </aside>
    <main class="main-content" :class="{ 'main-content-sidebar-collapsed': isSidebarCollapsed }">
      <router-view />
    </main>
    <ToastContainer />
  </div>
  <div v-else class="auth-layout">
    <router-view />
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ToastContainer from '@/components/ToastContainer.vue'

const route = useRoute()
const isSidebarOpen = ref(false)
const isSidebarCollapsed = ref(false)
const showAppShell = computed(
  () => route.name !== 'login' && route.name !== 'setup-admin',
)

const toggleSidebarCollapsed = () => {
  if (window.matchMedia('(max-width: 768px)').matches) {
    return
  }
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const handleSidebarClick = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null
  if (target?.closest('a, button, input, select, textarea, label')) {
    return
  }
  toggleSidebarCollapsed()
}

watch(() => route.fullPath, () => {
  isSidebarOpen.value = false
})
</script>

<style scoped>
.mobile-header {
  display: none;
}

.mobile-brand {
  font-size: 1rem;
  font-weight: 700;
}

.mobile-brand span {
  color: var(--accent);
}

.mobile-menu-btn {
  min-width: 4.5rem;
}

.sidebar-overlay {
  display: none;
}

@media (max-width: 768px) {
  .mobile-header {
    position: sticky;
    top: 0;
    z-index: 45;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg-secondary) 85%, transparent);
    backdrop-filter: blur(8px);
  }

  .sidebar {
    transform: translateX(-100%);
    width: min(82vw, 290px);
    box-shadow: var(--shadow-lg);
  }

  .sidebar-open {
    transform: translateX(0);
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 35;
    background: var(--bg-overlay);
  }
}
</style>
