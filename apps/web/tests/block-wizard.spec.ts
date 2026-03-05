import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import BlockWizardModal from '../src/components/BlockWizardModal.vue'

describe('BlockWizardModal', () => {
  it('renders modal and no longer requires apply preset click', async () => {
    const wrapper = mount(BlockWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: '',
          display_name: '',
          tags: [],
          pip: [],
          pip_install_mode: 'index',
          pip_wheelhouse_path: '',
          npm: [],
          apt: [],
          apt_constraints: {},
          ports: [],
        },
        envEntries: [],
        contracts: {
          schema_version: 3,
          profile: { required_fields: [], defaults: {}, fields: {} },
          stack: { required_fields: [], defaults: {}, fields: {} },
          block: { required_fields: ['id', 'display_name'], defaults: {}, fields: {} },
        },
        blockCatalog: {
          schema_version: 1,
          revision: 1,
          categories: [{ id: 'llm_serving', label: 'LLM Serving', description: '' }],
          presets: [
            {
              id: 'vllm',
              display_name: 'vLLM Runtime',
              description: '',
              category: 'llm_serving',
              tags: ['llm'],
              pip: [{ name: 'vllm', version: '>=0.6,<0.8' }],
              apt: [],
              env: {},
              ports: [],
              entrypoint_cmd: [],
              requires: {},
              provides: {},
            },
          ],
        },
        selectedCategory: '',
        searchTerm: '',
        selectedPresetId: 'vllm',
        selectedProfile: 'base',
      },
    })
    await nextTick()

    const applyButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Apply Preset'))
    expect(applyButton).toBeFalsy()
    expect(document.body.textContent || '').toContain('Featured Presets')
    wrapper.unmount()
  })

  it('moves from runtime directly to review', async () => {
    const wrapper = mount(BlockWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: 'test_block',
          display_name: 'Test Block',
          tags: [],
          pip: [],
          pip_install_mode: 'index',
          pip_wheelhouse_path: '',
          npm: [],
          apt: [],
          apt_constraints: {},
          ports: [],
        },
        envEntries: [],
        contracts: null,
        blockCatalog: null,
        selectedCategory: '',
        searchTerm: '',
        selectedPresetId: '',
        selectedProfile: 'base',
      },
    })
    await nextTick()

    const nextButton = () => Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Next'))
    nextButton()?.click()
    await nextTick()
    nextButton()?.click()
    await nextTick()
    expect(document.body.textContent || '').toContain('Step 3 of 3')
    expect(document.body.textContent || '').toContain('Review')
    wrapper.unmount()
  })

  it('shows dependency guidance and npm section in runtime step', async () => {
    const wrapper = mount(BlockWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: 'deps_block',
          display_name: 'Deps Block',
          tags: [],
          pip: [{ name: 'fastapi', version: '', version_mode: 'latest' }],
          pip_install_mode: 'index',
          pip_wheelhouse_path: '',
          npm: [],
          apt: [],
          apt_constraints: {},
          ports: [],
        },
        envEntries: [],
        contracts: null,
        blockCatalog: null,
        selectedCategory: '',
        searchTerm: '',
        selectedPresetId: '',
        selectedProfile: 'base',
      },
    })
    await nextTick()
    const nextButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Next'))
    nextButton?.click()
    await nextTick()
    const text = document.body.textContent || ''
    expect(text).toContain('Dependency defaults use latest compatible installs')
    expect(text).toContain('Node Dependencies (npm/pnpm/yarn)')
    expect(text).toContain('Import requirements.txt')
    expect(text).toContain('Import package.json')
    expect(text).toContain('Import apt list')
    wrapper.unmount()
  })

  it('shows wheel location only when a pip dependency selects wheel source', async () => {
    const wrapper = mount(BlockWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: 'deps_block',
          display_name: 'Deps Block',
          tags: [],
          pip: [{ name: 'fastapi', version: '', version_mode: 'latest', wheel_file_path: '' }],
          pip_install_mode: 'index',
          pip_wheelhouse_path: '',
          npm: [],
          apt: [],
          apt_constraints: {},
          ports: [],
        },
        envEntries: [],
        contracts: null,
        blockCatalog: null,
        selectedCategory: '',
        searchTerm: '',
        selectedPresetId: '',
        selectedProfile: 'base',
      },
    })
    await nextTick()
    const nextButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Next'))
    nextButton?.click()
    await nextTick()

    expect(document.body.textContent || '').not.toContain('Wheel File')

    const sourceSelect = Array.from(document.body.querySelectorAll<HTMLSelectElement>('select'))
      .find((select) => Array.from(select.options).some((option) => option.value === 'wheel'))
    expect(sourceSelect).toBeTruthy()
    sourceSelect!.value = 'wheel'
    sourceSelect!.dispatchEvent(new Event('change'))
    await nextTick()

    expect(document.body.textContent || '').toContain('Wheel File')
    const wheelInput = Array.from(document.body.querySelectorAll<HTMLInputElement>('input'))
      .find((input) => input.placeholder.includes('flash_attn'))
    expect(wheelInput).toBeTruthy()
    wheelInput!.value = 'wheels/flash_attn-2.7.4-cp310-cp310-linux_x86_64.whl'
    wheelInput!.dispatchEvent(new Event('input'))
    await nextTick()
    expect((wrapper.props('form') as any).pip[0].version).toBe('==2.7.4')
    wrapper.unmount()
  })
})
