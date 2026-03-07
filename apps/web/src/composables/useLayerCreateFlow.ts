import { useBlockCreateFlow } from '@/composables/useBlockCreateFlow'

export function useLayerCreateFlow(options: Parameters<typeof useBlockCreateFlow>[0] = {}) {
  return useBlockCreateFlow(options)
}
