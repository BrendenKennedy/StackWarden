import { describe, expect, it } from 'vitest'

import { CREATE_SCHEMA_VERSIONS, resolveCreateSchemaVersion } from '../src/api/schemaVersions'

describe('schema version resolution', () => {
  it('falls back to local defaults when contracts are missing', () => {
    expect(resolveCreateSchemaVersion('profile', null)).toBe(CREATE_SCHEMA_VERSIONS.profile)
    expect(resolveCreateSchemaVersion('stack', null)).toBe(CREATE_SCHEMA_VERSIONS.stack)
    expect(resolveCreateSchemaVersion('layer', null)).toBe(CREATE_SCHEMA_VERSIONS.layer)
  })

  it('uses contract defaults when valid schema_version is present', () => {
    const contracts = {
      profile: { defaults: { schema_version: 7 } },
      stack: { defaults: { schema_version: '5' } },
      layer: { defaults: { schema_version: 2 } },
    }
    expect(resolveCreateSchemaVersion('profile', contracts)).toBe(7)
    expect(resolveCreateSchemaVersion('stack', contracts)).toBe(5)
    expect(resolveCreateSchemaVersion('layer', contracts)).toBe(2)
  })

  it('ignores invalid schema_version values from contracts', () => {
    const contracts = {
      profile: { defaults: { schema_version: 0 } },
      stack: { defaults: { schema_version: 'abc' } },
      layer: { defaults: { schema_version: -2 } },
    }
    expect(resolveCreateSchemaVersion('profile', contracts)).toBe(CREATE_SCHEMA_VERSIONS.profile)
    expect(resolveCreateSchemaVersion('stack', contracts)).toBe(CREATE_SCHEMA_VERSIONS.stack)
    expect(resolveCreateSchemaVersion('layer', contracts)).toBe(CREATE_SCHEMA_VERSIONS.layer)
  })
})
