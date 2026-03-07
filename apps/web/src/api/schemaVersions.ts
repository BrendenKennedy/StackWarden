export const CREATE_SCHEMA_VERSIONS = {
  profile: 3,
  stack: 3,
  layer: 2,
} as const

type CreateEntity = keyof typeof CREATE_SCHEMA_VERSIONS

type CreateContractsLike = {
  profile?: { defaults?: Record<string, unknown> }
  stack?: { defaults?: Record<string, unknown> }
  layer?: { defaults?: Record<string, unknown> }
} | null

function parsePositiveInt(value: unknown): number | null {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) return null
  return parsed
}

export function resolveCreateSchemaVersion(
  entity: CreateEntity,
  contracts: CreateContractsLike,
): number {
  const fromContract = parsePositiveInt(contracts?.[entity]?.defaults?.schema_version)
  return fromContract ?? CREATE_SCHEMA_VERSIONS[entity]
}
