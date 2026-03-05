import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, get } from '../src/api/client'

describe('api client error handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('maps network/proxy failures to actionable ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    let caught: unknown
    try {
      await get('/meta/enums')
    } catch (err) {
      caught = err
    }

    expect(caught).toBeInstanceOf(ApiError)
    const apiErr = caught as ApiError
    expect(apiErr.status).toBe(0)
    expect(apiErr.detail.toLowerCase()).toContain('backend unreachable')
  })

  it('normalizes FastAPI validation errors from loc/msg format', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        detail: [{ loc: ['body', 'payload', 'id'], msg: 'Field required', type: 'missing' }],
      }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      }),
    ))

    let caught: unknown
    try {
      await get('/profiles')
    } catch (err) {
      caught = err
    }

    expect(caught).toBeInstanceOf(ApiError)
    const apiErr = caught as ApiError
    expect(apiErr.status).toBe(422)
    expect(apiErr.validationErrors).toEqual([{ field: 'payload.id', message: 'Field required' }])
  })
})

