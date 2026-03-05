import type { ValidationError } from './types'

const BASE_URL = '/api'
const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  status: number
  validationErrors: ValidationError[]
  detail: string

  constructor(status: number, detail: string, validationErrors: ValidationError[] = []) {
    super(`${status}: ${detail}`)
    this.status = status
    this.detail = detail
    this.validationErrors = validationErrors
  }
}

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = localStorage.getItem('stacksmith_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

function withTimeout(ms: number = DEFAULT_TIMEOUT_MS): AbortSignal {
  return AbortSignal.timeout(ms)
}

function normalizeValidationErrors(raw: unknown): ValidationError[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((entry): ValidationError | null => {
      if (!entry || typeof entry !== 'object') return null
      const item = entry as Record<string, unknown>
      if (typeof item.field === 'string' && typeof item.message === 'string') {
        return { field: item.field, message: item.message }
      }
      const loc = Array.isArray(item.loc) ? item.loc : []
      const fieldParts = loc
        .map((part) => String(part))
        .filter((part) => !['body', 'query', 'path'].includes(part))
      const field = fieldParts.length > 0 ? fieldParts.join('.') : 'request'
      const message = typeof item.msg === 'string'
        ? item.msg
        : (typeof item.message === 'string' ? item.message : 'Invalid value')
      return { field, message }
    })
    .filter((item): item is ValidationError => item !== null)
}

async function handleError(res: Response): Promise<never> {
  const text = await res.text()
  let detail = text
  let validationErrors: ValidationError[] = []

  try {
    const json = JSON.parse(text)
    if (Array.isArray(json.detail)) {
      validationErrors = normalizeValidationErrors(json.detail)
      detail = validationErrors.length > 0
        ? validationErrors.map((e) => `${e.field}: ${e.message}`).join('; ')
        : 'Validation failed'
    } else if (typeof json.detail === 'string') {
      detail = json.detail
    }
  } catch {
    // not JSON, keep raw text
  }

  throw new ApiError(res.status, detail, validationErrors)
}

function networkDetail(path: string, reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason)
  if (message.toLowerCase().includes('timeout')) {
    return `Request timed out while calling ${path}. Backend may be unavailable.`
  }
  return `Backend unreachable while calling ${path}. Ensure stacksmith-web is running on 127.0.0.1:8765.`
}

async function safeFetch(input: string, init: RequestInit, path: string): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (error) {
    throw new ApiError(0, networkDetail(path, error))
  }
}

async function parseJsonResponse<T>(res: Response, path: string): Promise<T> {
  const text = await res.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    const preview = text.slice(0, 120).replace(/\s+/g, ' ').trim()
    throw new ApiError(
      res.status || 500,
      `Expected JSON from ${path}, got non-JSON response (${preview || 'empty body'}).`,
    )
  }
}

export async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, v)
      }
    })
  }
  const res = await safeFetch(url.toString(), {
    headers: getHeaders(),
    signal: withTimeout(),
  }, path)
  if (!res.ok) {
    await handleError(res)
  }
  return parseJsonResponse<T>(res, path)
}

export async function post<T>(
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const res = await safeFetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { ...getHeaders(), ...(extraHeaders || {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: withTimeout(),
  }, path)
  if (!res.ok) {
    await handleError(res)
  }
  return parseJsonResponse<T>(res, path)
}

export async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await safeFetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: getHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: withTimeout(),
  }, path)
  if (!res.ok) {
    await handleError(res)
  }
  return parseJsonResponse<T>(res, path)
}

export async function del<T>(path: string): Promise<T> {
  const res = await safeFetch(`${BASE_URL}${path}`, {
    method: 'DELETE',
    headers: getHeaders(),
    signal: withTimeout(),
  }, path)
  if (!res.ok) {
    await handleError(res)
  }
  return parseJsonResponse<T>(res, path)
}
