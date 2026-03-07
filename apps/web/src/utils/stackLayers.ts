export type StackLayerId =
  | 'hardware_layer'
  | 'system_runtime_layer'
  | 'driver_accelerator_layer'
  | 'core_compute_layer'
  | 'inference_engine_layer'
  | 'optimization_compilation_layer'
  | 'serving_layer'
  | 'application_orchestration_layer'
  | 'observability_operations_layer'

export const STACK_LAYERS: Array<{
  id: StackLayerId
  label: string
  hint: string
  purpose: string
  whenUsed: string
  profileManaged?: boolean
}> = [
  {
    id: 'hardware_layer',
    label: 'Hardware Layer',
    hint: 'Managed by selected profile (host and device assumptions).',
    purpose: 'Defines host architecture and accelerator constraints.',
    whenUsed: 'Always selected via profile for planning/compatibility.',
    profileManaged: true,
  },
  {
    id: 'inference_engine_layer',
    label: 'Inference Engine Layer',
    hint: 'Model execution runtimes.',
    purpose: 'Defines the model-serving runtime engine.',
    whenUsed: 'Use for specific runtime choices (vLLM, llama.cpp, etc.).',
  },
  {
    id: 'optimization_compilation_layer',
    label: 'Optimization/Compilation Layer',
    hint: 'Quantization/export/compile tools.',
    purpose: 'Adds optimization passes, export, and compile toolchains.',
    whenUsed: 'Use when latency/throughput optimization is needed.',
  },
  {
    id: 'core_compute_layer',
    label: 'Core Compute Libraries',
    hint: 'Torch/ONNX and core compute libs.',
    purpose: 'Supplies primary numeric/compute frameworks.',
    whenUsed: 'Use when model runtime depends on these foundations.',
  },
  {
    id: 'driver_accelerator_layer',
    label: 'Driver/Accelerator Layer',
    hint: 'GPU/accelerator wiring and kernels.',
    purpose: 'Adds accelerator-specific runtime support.',
    whenUsed: 'Use for GPU or other hardware-accelerated inference.',
  },
  {
    id: 'system_runtime_layer',
    label: 'System/Runtime Layer',
    hint: 'Base runtime and system glue.',
    purpose: 'Provides foundational system packages and runtime prerequisites.',
    whenUsed: 'Use when workloads need common OS/runtime tooling.',
  },
  {
    id: 'application_orchestration_layer',
    label: 'Application/Orchestration Layer',
    hint: 'API/workers/agent orchestration.',
    purpose: 'Coordinates app logic, APIs, and worker execution.',
    whenUsed: 'Use for API wrappers, workers, agents, and orchestration.',
  },
  {
    id: 'observability_operations_layer',
    label: 'Observability/Operations Layer',
    hint: 'Metrics/tracing/ops readiness.',
    purpose: 'Provides telemetry and operational visibility.',
    whenUsed: 'Use for production monitoring, tracing, and diagnostics.',
  },
  {
    id: 'serving_layer',
    label: 'Serving Layer',
    hint: 'Inference serving interfaces.',
    purpose: 'Exposes model runtime through serving protocols and gateways.',
    whenUsed: 'Use when stack needs network-facing inference serving.',
  },
]

const TAG_LAYER_MAP: Array<{ token: string; layer: StackLayerId }> = [
  { token: 'observability', layer: 'observability_operations_layer' },
  { token: 'monitoring', layer: 'observability_operations_layer' },
  { token: 'metrics', layer: 'observability_operations_layer' },
  { token: 'tracing', layer: 'observability_operations_layer' },
  { token: 'serving', layer: 'serving_layer' },
  { token: 'gateway', layer: 'serving_layer' },
  { token: 'api', layer: 'application_orchestration_layer' },
  { token: 'worker', layer: 'application_orchestration_layer' },
  { token: 'agent', layer: 'application_orchestration_layer' },
  { token: 'orchestration', layer: 'application_orchestration_layer' },
  { token: 'optimization', layer: 'optimization_compilation_layer' },
  { token: 'quantization', layer: 'optimization_compilation_layer' },
  { token: 'compile', layer: 'optimization_compilation_layer' },
  { token: 'cuda', layer: 'driver_accelerator_layer' },
  { token: 'accelerator', layer: 'driver_accelerator_layer' },
  { token: 'llm', layer: 'inference_engine_layer' },
  { token: 'diffusion', layer: 'inference_engine_layer' },
  { token: 'vision', layer: 'inference_engine_layer' },
  { token: 'asr', layer: 'inference_engine_layer' },
  { token: 'tts', layer: 'inference_engine_layer' },
  { token: 'torch', layer: 'core_compute_layer' },
  { token: 'onnx', layer: 'core_compute_layer' },
  { token: 'ubuntu', layer: 'system_runtime_layer' },
  { token: 'debian', layer: 'system_runtime_layer' },
  { token: 'bookworm', layer: 'system_runtime_layer' },
  { token: 'os', layer: 'system_runtime_layer' },
  { token: 'infra', layer: 'system_runtime_layer' },
  { token: 'system', layer: 'system_runtime_layer' },
  { token: 'hardware', layer: 'hardware_layer' },
]

export function inferLayersFromTags(tags: string[]): StackLayerId[] {
  const joined = tags.join(' ').toLowerCase()
  const out = new Set<StackLayerId>()
  for (const row of TAG_LAYER_MAP) {
    if (joined.includes(row.token)) out.add(row.layer)
  }
  if (!out.size) out.add('application_orchestration_layer')
  return Array.from(out)
}
