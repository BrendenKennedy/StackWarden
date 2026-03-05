import { createRouter, createWebHistory } from 'vue-router'
import CatalogView from './views/CatalogView.vue'
import ArtifactDetailView from './views/ArtifactDetailView.vue'
import JobsView from './views/JobsView.vue'
import SettingsView from './views/SettingsView.vue'
import ProfilesView from './views/ProfilesView.vue'
import StacksView from './views/StacksView.vue'
import BlocksView from './views/BlocksView.vue'

const routes = [
  { path: '/', redirect: '/catalog' },
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
  { path: '/blocks', name: 'blocks', component: BlocksView },
  { path: '/blocks/new', redirect: '/blocks?create=1' },
  { path: '/blocks/:id', redirect: '/blocks' },
  { path: '/blocks/:id/edit', redirect: '/blocks' },
  { path: '/create/profile', redirect: '/profiles?create=1' },
  { path: '/create/stack', redirect: '/stacks?create=1' },
  { path: '/create/block', redirect: '/blocks?create=1' },
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

export default createRouter({
  history: createWebHistory(),
  routes,
})
