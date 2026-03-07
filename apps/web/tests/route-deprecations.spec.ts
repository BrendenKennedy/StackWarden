import { describe, expect, it } from 'vitest'

import {
  BLOCK_ROUTE_REMOVE_AFTER,
  formatBlocksRouteDeprecation,
  isLegacyBlocksRoute,
} from '../src/routerDeprecations'

describe('legacy blocks route deprecation helpers', () => {
  it('detects legacy /blocks route variants', () => {
    expect(isLegacyBlocksRoute('/blocks')).toBe(true)
    expect(isLegacyBlocksRoute('/blocks/new')).toBe(true)
    expect(isLegacyBlocksRoute('/blocks/abc/edit')).toBe(true)
    expect(isLegacyBlocksRoute('/layers')).toBe(false)
    expect(isLegacyBlocksRoute('/catalog')).toBe(false)
    expect(isLegacyBlocksRoute(null)).toBe(false)
  })

  it('formats warning message with explicit removal date', () => {
    const message = formatBlocksRouteDeprecation('/blocks/new')
    expect(message).toContain('/blocks/new')
    expect(message).toContain('/layers')
    expect(message).toContain(BLOCK_ROUTE_REMOVE_AFTER)
  })
})
