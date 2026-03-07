import { createRouter, createWebHistory } from 'vue-router'
import CatalogView from './views/CatalogView.vue'
import ArtifactDetailView from './views/ArtifactDetailView.vue'
import JobsView from './views/JobsView.vue'
import SettingsView from './views/SettingsView.vue'
import ProfilesView from './views/ProfilesView.vue'
import StacksView from './views/StacksView.vue'
import LayersView from './views/LayersView.vue'
import DashboardView from './views/DashboardView.vue'
import LoginView from './views/LoginView.vue'
import SetupAdminView from './views/SetupAdminView.vue'
import { useAuthSession } from './composables/useAuthSession'
import { formatBlocksRouteDeprecation, isLegacyBlocksRoute } from './routerDeprecations'

const routes = [
  { path: '/', redirect: '/catalog' },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/setup', name: 'setup-admin', component: SetupAdminView },
  { path: '/dashboard', name: 'dashboard', component: DashboardView },
  { path: '/catalog', name: 'catalog', component: CatalogView },
  { path: '/artifacts/:id', name: 'artifact-detail', component: ArtifactDetailView, props: true },
  { path: '/build', redirect: '/catalog' },
  { path: '/profiles', name: 'profiles', component: ProfilesView },
  { path: '/profiles/new', redirect: '/profiles?create=1' },
  { path: '/profiles/:id', redirect: '/profiles' },
  { path: '/profiles/:id/edit', redirect: '/profiles' },
  { path: '/stacks', name: 'stacks', component: StacksView },
  { path: '/stacks/new', name: 'create-stack', redirect: '/stacks?create=1' },
  { path: '/stacks/:id', redirect: '/stacks' },
  { path: '/stacks/:id/edit', redirect: '/stacks' },
  { path: '/layers', name: 'layers', component: LayersView },
  { path: '/layers/new', redirect: '/layers?create=1' },
  { path: '/layers/:id', redirect: '/layers' },
  { path: '/layers/:id/edit', redirect: '/layers' },
  { path: '/blocks', redirect: '/layers' },
  { path: '/blocks/new', redirect: '/layers?create=1' },
  { path: '/blocks/:id', redirect: '/layers' },
  { path: '/blocks/:id/edit', redirect: '/layers' },
  { path: '/create/profile', redirect: '/profiles?create=1' },
  { path: '/create/stack', redirect: '/stacks?create=1' },
  { path: '/create/block', redirect: '/layers?create=1' },
  { path: '/jobs', name: 'jobs', component: JobsView },
  { path: '/jobs/:id', name: 'job-detail', component: JobsView, props: true },
  { path: '/settings', name: 'settings', component: SettingsView },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: {
      template: `<div class="empty-state"><h2>404 - Page Not Found</h2><p><router-link to="/">Go to Catalog</router-link></p></div>`,
    },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

let warnedLegacyBlocksRoute = false

router.beforeEach(async (to) => {
  const redirectedFromPath = to.redirectedFrom?.path
  if (!warnedLegacyBlocksRoute && isLegacyBlocksRoute(redirectedFromPath)) {
    warnedLegacyBlocksRoute = true
    console.warn(formatBlocksRouteDeprecation(redirectedFromPath))
  }

  if (to.name === 'not-found') return true
  const { refreshStatus, status } = useAuthSession()
  let session = status.value
  try {
    session = await refreshStatus()
  } catch (error) {
    if (to.name === 'login' || to.name === 'setup-admin') {
      return true
    }
    if (!session) {
      return { name: 'login' }
    }
  }
  if (!session) {
    return to.name === 'login' || to.name === 'setup-admin' ? true : { name: 'login' }
  }

  if (session.setup_required) {
    if (to.name !== 'setup-admin') {
      return { name: 'setup-admin' }
    }
    return true
  }

  if (!session.authenticated) {
    if (to.name !== 'login') {
      return { name: 'login' }
    }
    return true
  }

  if (to.name === 'login' || to.name === 'setup-admin') {
    return { name: 'dashboard' }
  }
  return true
})

export default router
