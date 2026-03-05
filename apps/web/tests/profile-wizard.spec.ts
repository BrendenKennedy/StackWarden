import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import ProfileWizardModal from '../src/components/ProfileWizardModal.vue'

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('ProfileWizardModal', () => {
  it('starts on hardware and enforces required fields before review', async () => {
    const wrapper = mount(ProfileWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: '',
          display_name: '',
          arch: '',
          os: 'linux',
          os_family_id: '',
          os_version_id: '',
          container_runtime: 'nvidia',
          gpu: { vendor: 'nvidia', family: 'ampere', vendor_id: 'nvidia', family_id: 'ampere', model_id: '' },
          defaults: { python: '3.10', user: 'root', workdir: '/workspace' },
          advanced_override: false,
        },
        enums: {
          task: [],
          serve: [],
          api: [],
          arch: ['amd64', 'arm64'],
          build_strategy: [],
          container_runtime: ['nvidia', 'runc'],
        },
        hints: null,
        detectingHints: false,
        catalogs: {
          schema_version: 1,
          revision: 1,
          arch: [{ id: 'amd64', label: 'AMD64', aliases: [] }],
          os_family: [{ id: 'linux', label: 'Linux', aliases: [] }],
          os_version: [],
          container_runtime: [{ id: 'nvidia', label: 'NVIDIA Runtime', aliases: [] }],
          gpu_vendor: [{ id: 'nvidia', label: 'NVIDIA', aliases: [] }],
          gpu_family: [{ id: 'ampere', label: 'Ampere', aliases: [], parent_id: 'nvidia' }],
          gpu_model: [],
        },
        contracts: {
          schema_version: 2,
          profile: {
            required_fields: ['id', 'display_name', 'arch', 'container_runtime'],
            defaults: {},
            fields: {},
          },
          stack: { required_fields: [], defaults: {}, fields: {} },
          block: { required_fields: [], defaults: {}, fields: {} },
        },
      },
    })

    await nextTick()
    const nextButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Next'))
    expect(nextButton).toBeTruthy()
    nextButton!.click()
    await nextTick()
    expect(document.body.textContent || '').toContain('Step 1 of 2')
    const archSelect = Array.from(document.body.querySelectorAll<HTMLSelectElement>('select'))
      .find(sel => Array.from(sel.options).some(opt => opt.text === 'amd64'))
    expect(archSelect).toBeTruthy()
    archSelect!.value = 'amd64'
    archSelect!.dispatchEvent(new Event('change'))
    await nextTick()

    const nextAgain = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Next'))
    expect(nextAgain).toBeTruthy()
    nextAgain!.click()
    await nextTick()
    expect(document.body.textContent || '').toContain('Step 2 of 2')

    wrapper.unmount()
  })

  it('starts directly on hardware step', async () => {
    const wrapper = mount(ProfileWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: {
          id: '',
          display_name: '',
          arch: '',
          os: 'linux',
          os_family_id: '',
          os_version_id: '',
          container_runtime: 'nvidia',
          gpu: { vendor: 'nvidia', family: 'ampere', vendor_id: 'nvidia', family_id: 'ampere', model_id: '' },
          defaults: { python: '3.10', user: 'root', workdir: '/workspace' },
          advanced_override: false,
        },
        enums: {
          task: [],
          serve: [],
          api: [],
          arch: ['amd64', 'arm64'],
          build_strategy: [],
          container_runtime: ['nvidia', 'runc'],
        },
        hints: null,
        detectingHints: false,
        catalogs: null,
        contracts: null,
      },
    })
    await nextTick()
    expect(document.body.textContent || '').toContain('Step 1 of 2')
    expect(document.body.textContent || '').toContain('Hardware')
    wrapper.unmount()
  })

  it('opens coming soon modal and resets value on custom sentinel selection', async () => {
    const formData = {
      id: 'profile_custom',
      display_name: 'Profile Custom',
      arch: 'amd64',
      os: 'linux',
      os_family_id: '',
      os_version_id: '',
      container_runtime: 'nvidia',
      gpu: { vendor: 'nvidia', family: 'ampere', vendor_id: 'nvidia', family_id: 'ampere', model_id: '' },
      defaults: { python: '3.10', user: 'root', workdir: '/workspace' },
      advanced_override: false,
    }
    const wrapper = mount(ProfileWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: formData,
        enums: {
          task: [],
          serve: [],
          api: [],
          arch: ['amd64', 'arm64'],
          build_strategy: [],
          container_runtime: ['nvidia', 'runc'],
        },
        hints: null,
        detectingHints: false,
        catalogs: {
          schema_version: 1,
          revision: 1,
          arch: [{ id: 'amd64', label: 'AMD64', aliases: [] }],
          os_family: [{ id: 'ubuntu', label: 'Ubuntu', aliases: [] }],
          os_version: [{ id: 'ubuntu_24_04', label: 'Ubuntu 24.04', aliases: [], parent_id: 'ubuntu' }],
          container_runtime: [{ id: 'nvidia', label: 'NVIDIA Runtime', aliases: [] }],
          gpu_vendor: [{ id: 'nvidia', label: 'NVIDIA', aliases: [] }],
          gpu_family: [{ id: 'ampere', label: 'Ampere', aliases: [], parent_id: 'nvidia' }],
          gpu_model: [{ id: 'nvidia_a100', label: 'NVIDIA A100', aliases: [], parent_id: 'ampere' }],
        },
        contracts: null,
      },
    })
    await nextTick()
    const osFamilySelect = Array.from(document.body.querySelectorAll<HTMLSelectElement>('select'))
      .find(sel => Array.from(sel.options).some(opt => opt.text.includes('Add your own OS family')))
    expect(osFamilySelect).toBeTruthy()
    osFamilySelect!.value = '__add_custom__'
    osFamilySelect!.dispatchEvent(new Event('change'))
    await nextTick()

    expect(document.body.textContent || '').toContain('Add custom option — coming soon')
    expect(formData.os_family_id).toBe('')

    const gotItButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Got it'))
    expect(gotItButton).toBeTruthy()
    gotItButton!.click()
    await nextTick()
    expect(document.body.textContent || '').not.toContain('Add custom option — coming soon')

    wrapper.unmount()
  })

  it('detect and autofill button applies detected hardware hints', async () => {
    const detectHardware = vi.fn().mockResolvedValue(undefined)
    const formData = {
      id: 'profile_detect',
      display_name: 'Profile Detect',
      arch: '',
      os: 'linux',
      os_family_id: '',
      os_version_id: '',
      container_runtime: '',
      gpu: { vendor: 'nvidia', family: 'ampere', vendor_id: '', family_id: '', model_id: '' },
      defaults: { python: '3.10', user: 'root', workdir: '/workspace' },
      advanced_override: false,
    }
    const wrapper = mount(ProfileWizardModal, {
      attachTo: document.body,
      props: {
        show: true,
        form: formData,
        enums: {
          task: [],
          serve: [],
          api: [],
          arch: ['amd64', 'arm64'],
          build_strategy: [],
          container_runtime: ['nvidia', 'runc'],
        },
        hints: {
          host_scope: 'server',
          arch: 'amd64',
          os: 'linux',
          os_family: 'ubuntu',
          os_version: '24.04',
          container_runtime: 'nvidia',
          cuda_available: false,
          cuda: null,
          gpu: { vendor: 'nvidia', family: 'hopper' },
          driver_version: null,
          capabilities_suggested: [],
          resolved_ids: {
            os_family_id: 'ubuntu',
            os_version_id: 'ubuntu_24_04',
            gpu_vendor_id: 'nvidia',
            gpu_family_id: 'hopper',
          },
          probes: [],
        },
        detectingHints: false,
        detectHardware,
        catalogs: {
          schema_version: 1,
          revision: 1,
          arch: [{ id: 'amd64', label: 'AMD64', aliases: [] }],
          os_family: [{ id: 'ubuntu', label: 'Ubuntu', aliases: [] }],
          os_version: [{ id: 'ubuntu_24_04', label: 'Ubuntu 24.04', aliases: [], parent_id: 'ubuntu' }],
          container_runtime: [{ id: 'nvidia', label: 'NVIDIA Runtime', aliases: [] }],
          gpu_vendor: [{ id: 'nvidia', label: 'NVIDIA', aliases: [] }],
          gpu_family: [{ id: 'hopper', label: 'Hopper', aliases: [], parent_id: 'nvidia' }],
          gpu_model: [],
        },
        contracts: null,
      },
    })
    await nextTick()
    const detectButton = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(el => el.textContent?.includes('Detect & Autofill Hardware'))
    expect(detectButton).toBeTruthy()
    detectButton!.click()
    await nextTick()
    await flushPromises()

    expect(detectHardware).toHaveBeenCalledTimes(1)
    expect(formData.arch).toBe('amd64')
    expect(formData.container_runtime).toBe('nvidia')
    expect(formData.os_family_id).toBe('ubuntu')
    expect(formData.os_version_id).toBe('ubuntu_24_04')
    expect(formData.gpu.vendor_id).toBe('nvidia')
    expect(formData.gpu.family_id).toBe('hopper')

    wrapper.unmount()
  })
})
