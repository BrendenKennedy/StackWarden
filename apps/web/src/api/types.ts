export interface CudaInfo {
  major: number
  minor: number
  variant: string
}

export interface GpuInfo {
  vendor: string
  family: string
  compute_capability?: string | null
}

export interface ProfileSummary {
  id: string
  display_name: string
  arch: string
  os: string
  cuda: CudaInfo | null
  gpu: GpuInfo
  derived_capabilities: string[]
  source?: string | null
  source_path?: string | null
  source_repo_url?: string | null
  source_repo_owner?: string | null
}

export interface BaseCandidate {
  name: string
  tags: string[]
  score_bias: number
}

export interface ProfileDetail extends ProfileSummary {
  container_runtime: string
  constraints: {
    disallow: Record<string, string[]>
    require: Record<string, string[]>
  }
  base_candidates: BaseCandidate[]
  defaults: { python: string; user: string; workdir: string }
}

export interface VariantDef {
  type: 'bool' | 'enum'
  options: string[]
  default: string | boolean
}

export type DependencyVersionMode = 'latest' | 'custom'
export type PipDependencyVersionMode = DependencyVersionMode | 'wheel'
export type NpmPackageManager = 'npm' | 'pnpm' | 'yarn'
export type NpmInstallScope = 'prod' | 'dev'
export type PipInstallMode = 'index' | 'wheelhouse_prefer' | 'wheelhouse_only'

export interface PipDependencyPayload {
  name: string
  version: string
  version_mode?: DependencyVersionMode
}

export interface NpmDependencyPayload {
  name: string
  version: string
  version_mode?: DependencyVersionMode
  package_manager?: NpmPackageManager
  install_scope?: NpmInstallScope
}

export interface StackSummary {
  id: string
  display_name: string
  task: string
  serve: string
  api: string
  variants: Record<string, VariantDef>
  source?: string | null
  source_path?: string | null
  source_repo_url?: string | null
  source_repo_owner?: string | null
}

export interface StackDetail extends StackSummary {
  build_strategy: string
  ports: number[]
  env: string[]
}

export interface BlockSummary {
  id: string
  display_name: string
  tags: string[]
  requires_keys?: string[]
  source?: string | null
  source_path?: string | null
  source_repo_url?: string | null
  source_repo_owner?: string | null
}

export interface BlockDetail extends BlockSummary {
  build_strategy: string | null
  ports: number[]
  env: string[]
  pip_count: number
  npm_count: number
  apt_count: number
  requires: Record<string, any>
  conflicts: string[]
  incompatible_with: string[]
  provides: Record<string, any>
}

export interface ArtifactSummary {
  id: string | null
  profile_id: string
  stack_id: string
  tag: string
  fingerprint: string
  status: string
  base_image: string
  build_strategy: string
  created_at: string
  variant_json: string | null
}

export interface ArtifactDetail extends ArtifactSummary {
  image_id: string | null
  digest: string | null
  base_digest: string | null
  template_hash: string | null
  stale_reason: string | null
  error_detail: string | null
}

export interface CatalogItem {
  row_id: string
  source: 'artifact'
  status: string
  profile_id: string
  stack_id: string
  created_at: string
  started_at: string | null
  ended_at: string | null
  job_id: string | null
  artifact_id: string | null
  tag: string | null
  fingerprint: string | null
  base_image: string | null
  build_strategy: string | null
  variant_json: string | null
  error_message: string | null
  stale_reason: string | null
  log_path: string | null
}

export interface PlanStep {
  type: string
  image: string | null
  tags: string[]
}

export interface PlanResponse {
  plan_id: string
  profile_id: string
  stack_id: string
  base_image: string
  base_digest: string | null
  builder: string
  warnings: string[]
  tag: string
  fingerprint: string
  steps: PlanStep[]
  rationale: Record<string, any> | null
  tuple_decision?: Record<string, any>
  build_optimization?: Record<string, any> | null
}

export interface VerifyResponse {
  ok: boolean
  errors: string[]
  warnings: string[]
  facts: Record<string, string>
  recomputed_fingerprint: string | null
  label_fingerprint: string | null
  catalog_fingerprint: string | null
  actions: string[]
}

export interface JobSummary {
  job_id: string
  status: string
  created_at: string
  started_at: string | null
  ended_at: string | null
  profile_id: string
  stack_id: string
}

export interface JobDetail extends JobSummary {
  variants: Record<string, any> | null
  flags: Record<string, boolean>
  build_optimization?: Record<string, any>
  result_artifact_id: string | null
  result_tag: string | null
  error_message: string | null
  log_path: string | null
}

export interface SystemConfig {
  catalog_path: string | null
  log_dir: string | null
  default_profile: string | null
  registry_allow: string[]
  registry_deny: string[]
  remote_catalog_enabled?: boolean
  remote_catalog_repo_url?: string | null
  remote_catalog_branch?: string
  remote_catalog_local_path?: string | null
  remote_catalog_local_overrides_path?: string | null
  remote_catalog_auto_pull?: boolean
  remote_catalog_last_sync_status?: string | null
  remote_catalog_last_sync_detail?: string | null
  remote_catalog_last_sync_commit?: string | null
  auth_enabled: boolean
  blocks_first_enabled: boolean
  tuple_layer_mode?: string
}

export interface SettingsConfigUpdatePayload {
  default_profile?: string | null
  registry_allow?: string[]
  registry_deny?: string[]
  remote_catalog_enabled?: boolean
  remote_catalog_repo_url?: string | null
  remote_catalog_branch?: string
  remote_catalog_local_path?: string | null
  remote_catalog_local_overrides_path?: string | null
  remote_catalog_auto_pull?: boolean
  tuple_layer_mode?: string | null
  sync_now?: boolean
}

export interface AuthSessionStatus {
  setup_required: boolean
  authenticated: boolean
  username?: string | null
}

export interface DetectionProbe {
  name: string
  status: 'ok' | 'warn' | 'error'
  message: string
  duration_ms: number
}

export interface DetectionHints {
  host_scope: string
  arch: string | null
  os: string | null
  os_family?: string | null
  os_version?: string | null
  container_runtime: string | null
  cuda_available: boolean
  cuda: CudaInfo | null
  gpu: GpuInfo | null
  gpu_devices?: Array<{
    index: number
    model?: string | null
    family?: string | null
    compute_capability?: string | null
    memory_gb?: number | null
  }>
  driver_version: string | null
  cpu_model?: string | null
  cpu_cores_logical?: number | null
  cpu_cores_physical?: number | null
  memory_gb_total?: number | null
  disk_gb_total?: number | null
  supported_cuda_min?: string | null
  supported_cuda_max?: string | null
  confidence?: Record<string, 'detected' | 'inferred' | 'unknown'>
  unknown_rate?: number
  resolved_ids?: Record<string, string>
  matched_by?: Record<string, 'exact' | 'alias' | 'inferred'>
  unmatched_suggestions?: Array<{ catalog: string; raw_value: string; suggested_id: string }>
  capabilities_suggested: string[]
  probes: DetectionProbe[]
}

export interface HardwareCatalogItem {
  id: string
  label: string
  aliases: string[]
  parent_id?: string | null
  deprecated?: boolean
}

export interface HardwareCatalog {
  schema_version: number
  revision: number
  arch: HardwareCatalogItem[]
  os_family: HardwareCatalogItem[]
  os_version: HardwareCatalogItem[]
  container_runtime: HardwareCatalogItem[]
  gpu_vendor: HardwareCatalogItem[]
  gpu_family: HardwareCatalogItem[]
  gpu_model: HardwareCatalogItem[]
}

export interface BlockPresetPipDep {
  name: string
  version: string
}

export interface BlockPresetCategory {
  id: string
  label: string
  description: string
}

export interface BlockPreset {
  id: string
  display_name: string
  description: string
  category: string
  tags: string[]
  pip: BlockPresetPipDep[]
  apt: string[]
  env: Record<string, string>
  ports: number[]
  entrypoint_cmd: string[]
  requires: Record<string, any>
  provides: Record<string, any>
  layers?: string[]
}

export interface BlockPresetCatalog {
  schema_version: number
  revision: number
  categories: BlockPresetCategory[]
  presets: BlockPreset[]
}

export interface TupleCatalogSelector {
  arch: string
  os_family_id: string
  os_version_id: string
  container_runtime: string
  gpu_vendor_id: string
  gpu_family_id?: string | null
  cuda_min?: number | null
  cuda_max?: number | null
  driver_min?: number | null
}

export interface TupleCatalogItem {
  id: string
  status: 'supported' | 'experimental' | 'unsupported'
  selector: TupleCatalogSelector
  base_image: string
  wheelhouse_path: string
  notes: string
  tags: string[]
}

export interface TupleCatalog {
  schema_version: number
  revision: number
  tuples: TupleCatalogItem[]
}

// ---------------------------------------------------------------------------
// Create
// ---------------------------------------------------------------------------

export interface StackCreatePayload {
  schema_version?: number
  kind: 'stack_recipe'
  id: string
  display_name: string
  description?: string
  blocks: string[]
  build_strategy?: string | null
  base_role?: string | null
  copy_items: { src: string; dst: string }[]
  variants: Record<string, { type: 'bool' | 'enum'; options: string[]; default: string | boolean }>
  intent?: { outcome?: string | null; summary?: string | null }
  requirements?: { needs: string[]; optimize_for: string[]; constraints: Record<string, any> }
  derived_capabilities?: string[]
  selected_features?: string[]
  rejected_candidates?: Array<{ name: string; reason: string }>
  fix_suggestions?: string[]
  decision_trace?: string[]
}

export interface BlockCreatePayload {
  schema_version?: number
  id: string
  display_name: string
  description?: string
  tags: string[]
  build_strategy?: string | null
  base_role?: string | null
  pip: PipDependencyPayload[]
  pip_install_mode?: PipInstallMode
  pip_wheelhouse_path?: string
  npm?: NpmDependencyPayload[]
  apt: string[]
  apt_constraints?: Record<string, string>
  env: Record<string, string>
  ports: number[]
  entrypoint_cmd?: string[] | null
  copy_items: { src: string; dst: string }[]
  variants: Record<string, { type: 'bool' | 'enum'; options: string[]; default: string | boolean }>
  requires?: Record<string, any>
  conflicts?: string[]
  incompatible_with?: string[]
  provides?: Record<string, any>
}

export interface ProfileCreatePayload {
  schema_version?: number
  id: string
  display_name: string
  arch: string
  os: string
  os_family?: string | null
  os_version?: string | null
  os_family_id?: string | null
  os_version_id?: string | null
  container_runtime: string
  cuda?: { major: number; minor: number; variant: string } | null
  gpu: {
    vendor: string
    family: string
    vendor_id?: string | null
    family_id?: string | null
    model_id?: string | null
    compute_capability?: string | null
  }
  gpu_devices?: Array<{
    index: number
    model?: string | null
    family?: string | null
    compute_capability?: string | null
    memory_gb?: number | null
  }>
  base_candidates?: { name: string; tags: string[]; score_bias: number }[]
  constraints?: {
    disallow: Record<string, string[]>
    require: Record<string, string[]>
  }
  intent?: { outcome?: string | null; summary?: string | null }
  requirements?: { needs: string[]; optimize_for: string[]; constraints: Record<string, any> }
  derived_capabilities?: string[]
  selected_features?: string[]
  rejected_candidates?: Array<{ name: string; reason: string }>
  fix_suggestions?: string[]
  decision_trace?: string[]
  defaults?: { python: string; user: string; workdir: string }
  host_facts?: {
    driver_version?: string | null
    runtime_version?: string | null
    cpu_model?: string | null
    cpu_cores_logical?: number | null
    cpu_cores_physical?: number | null
    memory_gb_total?: number | null
    disk_gb_total?: number | null
    detected_at?: string | null
    confidence?: Record<string, 'detected' | 'inferred' | 'unknown'>
  }
  capability_ranges?: Array<{ name: string; min?: string | null; max?: string | null; values: string[] }>
  labels?: Record<string, string>
  tags?: string[]
  advanced_override?: boolean
}

export interface CreateResponse {
  id: string
  display_name: string
  path: string
}

export interface DryRunResponse {
  yaml: string
  valid: boolean
  errors: { field: string; message: string }[]
}

export interface ComposePreviewResponse {
  valid: boolean
  errors: { field: string; message: string }[]
  yaml: string
  resolved_spec: Record<string, any> | null
  dependency_conflicts?: Array<{
    type: string
    name: string
    severity: 'warning' | 'error'
    existing: string
    incoming: string
    existing_source: string
    incoming_source: string
    message: string
  }>
  tuple_conflicts?: Array<{
    type: string
    name: string
    severity: 'warning' | 'error'
    existing: string
    incoming: string
    existing_source: string
    incoming_source: string
    message: string
  }>
  runtime_conflicts?: Array<{
    type: string
    name: string
    severity: 'warning' | 'error'
    existing: string
    incoming: string
    existing_source: string
    incoming_source: string
    message: string
  }>
}

export interface CompatibilityIssue {
  code: string
  severity: 'error' | 'warning' | 'info'
  message: string
  rule_id?: string | null
  rule_version?: number | null
  source?: string | null
  field?: string | null
  fix_hint?: string | null
  confidence_context?: Record<string, string>
}

export interface CompatibilityPreviewResponse {
  compatible: boolean
  errors: CompatibilityIssue[]
  warnings: CompatibilityIssue[]
  info: CompatibilityIssue[]
  requirements_summary: Record<string, any>
  suggested_fixes: string[]
  decision_trace: string[]
  tuple_decision?: Record<string, any>
}

export interface EnumsMeta {
  task: string[]
  serve: string[]
  api: string[]
  arch: string[]
  build_strategy: string[]
  container_runtime: string[]
}

export interface FieldConstraint {
  pattern?: string | null
  enum_values: string[]
  min_items?: number | null
  max_items?: number | null
  required_if?: Record<string, any> | null
  note?: string | null
}

export interface CreateContract {
  required_fields: string[]
  defaults: Record<string, any>
  fields: Record<string, FieldConstraint>
}

export interface CreateContractsResponse {
  schema_version: number
  profile: CreateContract
  stack: CreateContract
  block: CreateContract
}

export interface ValidationError {
  field: string
  message: string
}

export interface DuplicateRequest {
  new_id: string
  overrides?: Record<string, any>
}
