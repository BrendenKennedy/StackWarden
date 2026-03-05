import { ApiError } from '@/api/client'

export function toUserErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return String(err)
}
