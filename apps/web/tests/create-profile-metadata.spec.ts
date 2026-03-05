import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import { ApiError } from '../src/api/client'
import ProfilesView from '../src/views/ProfilesView.vue'

vi.mock('@/api/endpoints', () => ({
  profiles: {
    list: vi.fn().mockResolvedValue([]),
    remove: vi.fn().mockResolvedValue({ deleted: true, id: 'p-old' }),
  },
}))

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('ProfilesView modal-first creation', () => {
  const globalStubs = {
    RouterLink: true,
    ProfileCreateFlowModal: {
      template: '<div v-if="show">MockCreateModal</div>',
      props: ['show'],
    },
    ConfirmDeleteModal: {
      template: '<button v-if="show" class="mock-confirm-delete" @click="$emit(\'confirm\')">ConfirmDelete</button>',
      props: ['show'],
    },
  }

  it('opens create modal from Profiles page button', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profiles', component: ProfilesView }],
    })
    router.push('/profiles')
    await router.isReady()
    const wrapper = mount(ProfilesView, {
      global: { plugins: [router], stubs: globalStubs },
    })

    await flushPromises()
    await flushPromises()

    expect(wrapper.get('button.btn.btn-primary').attributes('aria-label')).toBe('Create New Profile')
    expect(wrapper.text()).not.toContain('MockCreateModal')
    await wrapper.get('button.btn.btn-primary').trigger('click')
    await router.replace({ path: '/profiles', query: { create: '1' } })
    await flushPromises()
    await flushPromises()
    expect(wrapper.text()).toContain('MockCreateModal')
  })

  it('shows API detail when profiles list fails', async () => {
    const { profiles } = await import('@/api/endpoints')
    ;(profiles.list as any).mockRejectedValueOnce(new ApiError(500, 'profiles failure'))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profiles', component: ProfilesView }],
    })
    router.push('/profiles')
    await router.isReady()
    const wrapper = mount(ProfilesView, {
      global: { plugins: [router], stubs: globalStubs },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('profiles failure')
  })

  it('deletes a profile from the table', async () => {
    const { profiles } = await import('@/api/endpoints')
    ;(profiles.list as any).mockResolvedValueOnce([
      {
        id: 'p-old',
        display_name: 'Old Profile',
        arch: 'amd64',
        os: 'linux',
        cuda: null,
        gpu: { vendor: 'nvidia', family: 'ampere' },
      },
    ])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profiles', component: ProfilesView }],
    })
    router.push('/profiles')
    await router.isReady()
    const wrapper = mount(ProfilesView, {
      global: { plugins: [router], stubs: globalStubs },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Old Profile')
    const deleteButton = wrapper.findAll('button').find(b => b.attributes('title') === 'Delete' || b.attributes('aria-label') === 'Delete')
    expect(deleteButton).toBeDefined()
    await deleteButton!.trigger('click')
    await wrapper.get('.mock-confirm-delete').trigger('click')
    await flushPromises()
    expect(profiles.remove).toHaveBeenCalledWith('p-old')
    expect(wrapper.text()).not.toContain('Old Profile')
  })
})

