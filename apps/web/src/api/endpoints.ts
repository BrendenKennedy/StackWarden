import { del, get, post, put } from './client'
import type {
  BlockSummary,
  ProfileSummary,
  StackSummary,
  CatalogItem,
  ArtifactDetail,
  PlanResponse,
  VerifyResponse,
  JobSummary,
  JobDetail,
  CompatibilityFix,
  RetryWithFixResponse,
  SystemConfig,
  DetectionHints,
  StackCreatePayload,
  ProfileCreatePayload,
  CreateResponse,
  DryRunResponse,
  EnumsMeta,
  CreateContractsResponse,
  BlockCreatePayload,
  ComposePreviewResponse,
  CompatibilityPreviewResponse,
  HardwareCatalog,
  HardwareCatalogItem,
  BlockPresetCatalog,
  TupleCatalog,
  SettingsConfigUpdatePayload,
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

export const blocks = {
  list: () => get<BlockSummary[]>('/blocks'),
  getSpec: (id: string) => get<BlockCreatePayload>(`/blocks/${id}/spec`),
  create: (payload: BlockCreatePayload) => post<CreateResponse>('/blocks', payload),
  update: (id: string, payload: BlockCreatePayload) => put<CreateResponse>(`/blocks/${id}`, payload),
  remove: (id: string) => del<{ deleted: boolean; id: string }>(`/blocks/${id}`),
  dryRun: (payload: BlockCreatePayload) => post<DryRunResponse>('/blocks/dry-run', payload),
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

  getCompatibilityFix: (id: string) =>
    get<CompatibilityFix>(`/jobs/${id}/compatibility-fix`),

  retry: (id: string) => post<{ job_id: string }>(`/jobs/${id}/retry`),

  retryWithFix: (id: string) =>
    post<RetryWithFixResponse>(`/jobs/${id}/retry-with-fix`),

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
  blockCatalog: () => get<BlockPresetCatalog>('/settings/block-catalog'),
  tupleCatalog: () => get<TupleCatalog>('/settings/tuple-catalog'),
  updateConfig: (
    body: SettingsConfigUpdatePayload,
    adminToken?: string,
  ) =>
    post<SystemConfig>(
      '/settings/config',
      body,
      adminToken ? { 'X-StackWarden-Admin-Token': adminToken } : undefined,
    ),
}

export const meta = {
  enums: () => get<EnumsMeta>('/meta/enums'),
  createContracts: (schema: 'v1' | 'v2' | 'v3' = 'v3') =>
    get<CreateContractsResponse>('/meta/create-contracts', { schema }),
}
