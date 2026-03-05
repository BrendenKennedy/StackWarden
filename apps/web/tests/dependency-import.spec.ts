import { describe, expect, it } from 'vitest'

import {
  parseAptListText,
  parsePackageJsonText,
  parseRequirementsText,
} from '../src/utils/dependencyImport'

describe('dependency import parsers', () => {
  it('parses requirements.txt style lines', () => {
    const deps = parseRequirementsText(`
      # comment
      fastapi==0.115.2
      uvicorn[standard]>=0.30
      numpy
      -f https://example.com/simple
    `)
    expect(deps).toEqual([
      { name: 'fastapi', version: '==0.115.2', version_mode: 'custom' },
      { name: 'uvicorn[standard]', version: '>=0.30', version_mode: 'custom' },
      { name: 'numpy', version: '', version_mode: 'latest' },
    ])
  })

  it('parses apt list with optional constraints', () => {
    const parsed = parseAptListText(`
      curl =8.5.0-1ubuntu1
      git
      # ignored
    `)
    expect(parsed.apt).toEqual(['curl', 'git'])
    expect(parsed.constraints).toEqual({ curl: '=8.5.0-1ubuntu1' })
  })

  it('parses package.json deps and devDeps', () => {
    const deps = parsePackageJsonText(JSON.stringify({
      dependencies: { next: '^15.0.0' },
      devDependencies: { typescript: '^5.8.0' },
    }))
    expect(deps).toEqual([
      {
        name: 'next',
        version: '^15.0.0',
        version_mode: 'custom',
        package_manager: 'npm',
        install_scope: 'prod',
      },
      {
        name: 'typescript',
        version: '^5.8.0',
        version_mode: 'custom',
        package_manager: 'npm',
        install_scope: 'dev',
      },
    ])
  })
})
