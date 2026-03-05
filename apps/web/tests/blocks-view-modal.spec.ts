import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import BlocksView from '../src/views/BlocksView.vue'

vi.mock('@/api/endpoints', () => ({
  blocks: {
    list: vi.fn().mockResolvedValue([]),
    remove: vi.fn().mockResolvedValue({ deleted: true, id: 'b-old' }),
  },
}))

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('BlocksView modal-first creation', () => {
  const globalStubs = {
    RouterLink: true,
    BlockCreateFlowModal: {
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
      routes: [{ path: '/blocks', component: BlocksView }],
    })
    router.push('/blocks')
    await router.isReady()
    const wrapper = mount(BlocksView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })

    await flushPromises()
    expect(wrapper.text()).not.toContain('MockBlockCreateModal')
    expect(wrapper.get('button.btn.btn-primary').attributes('aria-label')).toBe('Create New Block')
  })

  it('opens modal from query flag', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/blocks', component: BlocksView }],
    })
    router.push('/blocks?create=1')
    await router.isReady()
    const wrapper = mount(BlocksView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('MockBlockCreateModal')
  })

  it('deletes a block from the table', async () => {
    const { blocks } = await import('@/api/endpoints')
    ;(blocks.list as any).mockResolvedValueOnce([
      {
        id: 'b-old',
        display_name: 'Old Block',
        tags: ['api'],
      },
    ])
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/blocks', component: BlocksView }],
    })
    router.push('/blocks')
    await router.isReady()
    const wrapper = mount(BlocksView, {
      global: {
        plugins: [router],
        stubs: globalStubs,
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Old Block')
    const deleteButton = wrapper.findAll('button').find(b => b.text() === 'Delete')
    expect(deleteButton).toBeDefined()
    await deleteButton!.trigger('click')
    await wrapper.get('.mock-confirm-delete').trigger('click')
    await flushPromises()
    expect(blocks.remove).toHaveBeenCalledWith('b-old')
    expect(wrapper.text()).not.toContain('Old Block')
  })
})
