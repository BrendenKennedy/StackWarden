import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import LayersView from '../src/views/LayersView.vue'

vi.mock('@/api/endpoints', () => ({
  layers: {
    list: vi.fn().mockResolvedValue([]),
    remove: vi.fn().mockResolvedValue({ deleted: true, id: 'b-old' }),
  },
}))

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('LayersView modal-first creation', () => {
  const globalStubs = {
    RouterLink: true,
    LayerCreateFlowModal: {
      template: '<div v-if="show">MockBlockCreateModal</div>',
      props: ['show'],
    },
    ConfirmDeleteModal: {
      template: '<button v-if="show" class="mock-confirm-delete" @click="$emit(\'confirm\')">ConfirmDelete</button>',
      props: ['show'],
    },
  }

  it('renders create button and keeps modal hidden by default', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/layers', component: LayersView }],
    })
    router.push('/layers')
    await router.isReady()
    const wrapper = mount(LayersView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })

    await flushPromises()
    expect(wrapper.text()).not.toContain('MockBlockCreateModal')
    const createButton = wrapper.findAll('button')
      .find((b) => b.attributes('aria-label') === 'Create New Layer')
    expect(createButton).toBeDefined()
  })

  it('opens modal from query flag', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/layers', component: LayersView }],
    })
    router.push('/layers?create=1')
    await router.isReady()
    const wrapper = mount(LayersView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('MockBlockCreateModal')
  })

  it('deletes a block from the table', async () => {
    const { layers } = await import('@/api/endpoints')
    ;(layers.list as any).mockResolvedValueOnce([
      {
        id: 'b-old',
        display_name: 'Old Layer',
        tags: ['api'],
      },
    ])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/layers', component: LayersView }],
    })
    router.push('/layers')
    await router.isReady()
    const wrapper = mount(LayersView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Old Layer')
    const deleteButton = wrapper.findAll('button').find(b => b.attributes('title') === 'Delete' || b.attributes('aria-label') === 'Delete')
    expect(deleteButton).toBeDefined()
    await deleteButton!.trigger('click')
    await wrapper.get('.mock-confirm-delete').trigger('click')
    await flushPromises()
    expect(layers.remove).toHaveBeenCalledWith('b-old')
    expect(wrapper.text()).not.toContain('Old Layer')
  })
})
