import { SPEC_ID_PATTERN } from '@/api/contracts.generated'

export const SPEC_ID_RE = new RegExp(SPEC_ID_PATTERN)

export function sanitizeSpecIdInput(raw: string): string {
  let value = raw.toLowerCase().replace(/[^a-z0-9_-]/g, '')
  value = value.replace(/^[^a-z]+/, '')
  if (value.length > 64) value = value.slice(0, 64)
  return value
}
