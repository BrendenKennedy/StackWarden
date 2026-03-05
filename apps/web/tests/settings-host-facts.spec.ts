import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SettingsView from '../src/views/SettingsView.vue'

const mocks = vi.hoisted(() => ({
  detectionHintsMock: vi.fn(),
  configMock: vi.fn().mockResolvedValue({
    auth_enabled: true,
    catalog_path: null,
    log_dir: null,
    default_profile: null,
    registry_allow: [],
    registry_deny: [],
    blocks_first_enabled: true,
  }),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ showToast: vi.fn() }),
}))

vi.mock('@/api/endpoints', () => ({
  system: {
    config: mocks.configMock,
    detectionHints: mocks.detectionHintsMock,
  },
  settings: {
    tupleCatalog: vi.fn().mockResolvedValue(null),
  },
}))

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('Settings host facts panel', () => {
  it('renders host facts and refreshes detection', async () => {
    mocks.detectionHintsMock.mockResolvedValueOnce({
      host_scope: 'server',
      arch: 'arm64',
      os: 'linux',
      os_family: 'ubuntu',
      os_version: '24.04',
      container_runtime: 'nvidia',
      cuda_available: false,
      cuda: null,
      gpu: { vendor: 'nvidia', family: 'gpu', compute_capability: '12.1' },
      driver_version: '580.126.09',
      capabilities_suggested: ['cuda'],
      probes: [],
      confidence: { arch: 'detected' },
      resolved_ids: { arch_id: 'arm64' },
      gpu_devices: [],
    })
    mocks.detectionHintsMock.mockResolvedValueOnce({
      host_scope: 'server',
      arch: 'arm64',
      os: 'linux',
      os_family: 'ubuntu',
      os_version: '24.04',
      container_runtime: 'nvidia',
      cuda_available: false,
      cuda: null,
      gpu: { vendor: 'nvidia', family: 'gpu', compute_capability: '12.1' },
      driver_version: '580.126.09',
      capabilities_suggested: ['cuda'],
      probes: [],
      confidence: { arch: 'detected' },
      resolved_ids: { arch_id: 'arm64' },
      gpu_devices: [],
    })

    const wrapper = mount(SettingsView)
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('Discovered Host Facts')
    expect(wrapper.text()).toContain('arm64')
    expect(mocks.detectionHintsMock).toHaveBeenCalledTimes(1)

    const refreshButton = wrapper.findAll('button').find(b => b.text().includes('Refresh Detection'))
    expect(refreshButton).toBeTruthy()
    await refreshButton!.trigger('click')
    await flushPromises()

    expect(mocks.detectionHintsMock).toHaveBeenCalledTimes(2)
    expect(mocks.detectionHintsMock).toHaveBeenLastCalledWith(true)
  })
})

