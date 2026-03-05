import type { DetectionHints } from '@/api/types'

export type ProbeIssue = {
  key: string
  label: string
  reason: string
  docs: string
}

export function formatProbeIssues(hints: DetectionHints | null): ProbeIssue[] {
  if (!hints) return []
  const probes = hints.probes || []
  const getProbe = (name: string) => probes.find((p) => p.name === name)
  const issues: ProbeIssue[] = []

  const nvidiaProbe = getProbe('nvidia_smi')
  if (nvidiaProbe?.status === 'warn') {
    const skipped = nvidiaProbe.message.includes('Skipped by capability/OS gate')
    issues.push({
      key: 'nvidia_smi',
      label: 'nvidia-smi',
      reason: skipped
        ? 'Tool is not available on the server host PATH, so GPU/driver/CUDA facts cannot be read.'
        : `Probe warning: ${nvidiaProbe.message || 'nvidia-smi could not run on this host.'}`,
      docs: 'https://docs.nvidia.com/deploy/nvidia-smi/',
    })
  }

  const dockerProbe = getProbe('docker')
  if (dockerProbe?.status === 'warn') {
    const skipped = dockerProbe.message.includes('Skipped by capability/OS gate')
    issues.push({
      key: 'docker',
      label: 'Docker Engine',
      reason: skipped
        ? 'Docker CLI/socket was not detected, so runtime facts may be incomplete.'
        : `Probe warning: ${dockerProbe.message || 'Docker daemon could not be queried.'}`,
      docs: 'https://docs.docker.com/engine/install/ubuntu/',
    })
  }

  if (hints.container_runtime === 'nvidia' && !hints.gpu) {
    issues.push({
      key: 'nvidia_toolkit',
      label: 'NVIDIA Container Toolkit',
      reason:
        'Runtime is set to nvidia, but no GPU facts were detected. Verify toolkit/driver wiring and device visibility.',
      docs: 'https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html',
    })
  }

  return issues
}
