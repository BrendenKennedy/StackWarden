<template>
  <div class="app-layout">
    <header class="mobile-header">
      <button
        class="btn btn-ghost mobile-menu-btn"
        type="button"
        aria-label="Toggle navigation menu"
        @click="isSidebarOpen = !isSidebarOpen"
      >
        {{ isSidebarOpen ? 'Close' : 'Menu' }}
      </button>
      <div class="mobile-brand"><span>Stack</span>smith</div>
    </header>
    <div v-if="isSidebarOpen" class="sidebar-overlay" @click="isSidebarOpen = false"></div>
    <aside class="sidebar" :class="{ 'sidebar-open': isSidebarOpen }">
      <div class="sidebar-brand"><span>Stack</span>smith</div>
      <nav class="sidebar-nav">
        <div class="sidebar-nav-top">
          <router-link to="/catalog" @click="isSidebarOpen = false">Catalog</router-link>
          <router-link to="/profiles" @click="isSidebarOpen = false">Profiles</router-link>
          <router-link to="/stacks" @click="isSidebarOpen = false">Stacks</router-link>
          <router-link to="/blocks" @click="isSidebarOpen = false">Blocks</router-link>
        </div>
        <div class="sidebar-nav-bottom">
          <div class="sidebar-divider"></div>
          <router-link to="/settings" @click="isSidebarOpen = false">Settings</router-link>
        </div>
      </nav>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ToastContainer from '@/components/ToastContainer.vue'

const route = useRoute()
const isSidebarOpen = ref(false)

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
