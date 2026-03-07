import { del, get, post, put } from './client'
import type {
  LayerSummary,
  ProfileSummary,
  StackSummary,
  CatalogItem,
  ArtifactDetail,
  PlanResponse,
  VerifyResponse,
  JobSummary,
  JobDetail,
  SystemConfig,
  DetectionHints,
  StackCreatePayload,
  ProfileCreatePayload,
  CreateResponse,
  DryRunResponse,
  EnumsMeta,
  CreateContractsResponse,
  LayerCreatePayload,
  ComposePreviewResponse,
  CompatibilityPreviewResponse,
  LayerOptionsClassifyPayload,
  LayerOptionsClassifyResponse,
  HardwareCatalog,
  HardwareCatalogItem,
  LayerPresetCatalog,
  TupleCatalog,
  SettingsConfigUpdatePayload,
  AuthSessionStatus,
} from './types'

export const profiles = {
  list: () => get<ProfileSummary[]>('/profiles'),
  getSpec: (id: string) => get<ProfileCreatePayload>(`/profiles/${id}/spec`),
  create: (payload: ProfileCreatePayload) => post<CreateResponse>('/profiles', payload),
  update: (id: string, payload: ProfileCreatePayload) => put<CreateResponse>(`/profiles/${id}`, payload),
  remove: (id: string) => del<{ deleted: boolean; id: string }>(`/profiles/${id}`),
  dryRun: (payload: ProfileCreatePayload) => post<DryRunResponse>('/profiles/dry-run', payload),
}

export const stacks = {
  list: () => get<StackSummary[]>('/stacks'),
  getSpec: (id: string) => get<StackCreatePayload>(`/stacks/${id}/spec`),
  create: (payload: StackCreatePayload) => post<CreateResponse>('/stacks', payload),
  update: (id: string, payload: StackCreatePayload) => put<CreateResponse>(`/stacks/${id}`, payload),
  remove: (id: string) => del<{ deleted: boolean; id: string }>(`/stacks/${id}`),
  dryRun: (payload: StackCreatePayload) => post<DryRunResponse>('/stacks/dry-run', payload),
  composePreview: (payload: StackCreatePayload) =>
    post<ComposePreviewResponse>('/stacks/compose', payload),
}

export const layers = {
  list: () => get<LayerSummary[]>('/layers'),
  classifyOptions: (payload: LayerOptionsClassifyPayload) =>
    post<LayerOptionsClassifyResponse>('/layers/options/classify', payload),
  getSpec: (id: string) => get<LayerCreatePayload>(`/layers/${id}/spec`),
  create: (payload: LayerCreatePayload) => post<CreateResponse>('/layers', payload),
  update: (id: string, payload: LayerCreatePayload) => put<CreateResponse>(`/layers/${id}`, payload),
  remove: (id: string) => del<{ deleted: boolean; id: string }>(`/layers/${id}`),
  dryRun: (payload: LayerCreatePayload) => post<DryRunResponse>('/layers/dry-run', payload),
}

export const catalog = {
  items: (params?: {
    profile_id?: string
    stack_id?: string
    status?: string
    q?: string
    limit?: string
    offset?: string
  }) => get<CatalogItem[]>('/catalog/items', params),
}

export const artifacts = {
  get: (id: string) => get<ArtifactDetail>(`/artifacts/${id}`),

  getFile: (id: string, name: string) =>
    get<Record<string, any>>(`/artifacts/${id}/files/${name}`),

  markStale: (id: string) => post<{ marked: number }>(`/artifacts/${id}/mark-stale`),
  remove: (id: string) => del<{ deleted: boolean; id: string }>(`/artifacts/${id}`),
}

export const plan = {
  preview: (body: {
    profile_id: string
    stack_id: string
    variants?: Record<string, any>
    flags?: Record<string, boolean>
  }) => post<PlanResponse>('/plan', body),
}

export const compatibility = {
  preview: (body: { profile_id: string; stack_id: string }) =>
    post<CompatibilityPreviewResponse>('/compatibility/preview', body),
}

export const verify = {
  run: (body: {
    tag_or_id: string
    strict?: boolean
    fix?: boolean
  }) => post<VerifyResponse>('/verify', body),
}

export const jobs = {
  list: (limit?: number) =>
    get<JobSummary[]>('/jobs', limit ? { limit: String(limit) } : undefined),

  get: (id: string) => get<JobDetail>(`/jobs/${id}`),

  retry: (id: string) => post<{ job_id: string }>(`/jobs/${id}/retry`),
  cancel: (id: string) =>
    post<{ canceled: boolean; job_id: string; detail: string }>(`/jobs/${id}/cancel`),

  ensure: (body: {
    profile_id: string
    stack_id: string
    variants?: Record<string, any>
    flags?: Record<string, boolean>
  }) => post<{ job_id: string }>('/ensure', body),
}

export const system = {
  health: () => get<{ ok: boolean }>('/health'),
  config: () => get<SystemConfig>('/system/config'),
  detectionHints: (refresh = false) =>
    get<DetectionHints>('/system/detection-hints', refresh ? { refresh: 'true' } : undefined),
}

export const settings = {
  hardwareCatalogs: () => get<HardwareCatalog>('/settings/hardware-catalogs'),
  layerCatalog: () => get<LayerPresetCatalog>('/settings/layer-catalog'),
  tupleCatalog: () => get<TupleCatalog>('/settings/tuple-catalog'),
  updateConfig: (body: SettingsConfigUpdatePayload) => post<SystemConfig>('/settings/config', body),
  recycleServices: () => post<{ started: boolean; pid: number; log_file: string }>('/settings/services/recycle'),
}

export const auth = {
  status: () => get<AuthSessionStatus>('/auth/status'),
  setup: (body: { username: string; password: string }) => post<AuthSessionStatus>('/auth/setup', body),
  login: (body: { username: string; password: string }) => post<AuthSessionStatus>('/auth/login', body),
  logout: () => post<{ ok: boolean }>('/auth/logout'),
  changePassword: (body: { current_password: string; new_password: string }) =>
    post<{ ok: boolean }>('/auth/change-password', body),
}

export const meta = {
  enums: () => get<EnumsMeta>('/meta/enums'),
  createContracts: (schema: 'v1' | 'v2' | 'v3' = 'v3') =>
    get<CreateContractsResponse>('/meta/create-contracts', { schema }),
}
