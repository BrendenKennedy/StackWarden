export type ImportedPipDep = {
  name: string
  version: string
  version_mode: 'latest' | 'custom'
}

export type ImportedNpmDep = {
  name: string
  version: string
  version_mode: 'latest' | 'custom'
  package_manager: 'npm'
  install_scope: 'prod' | 'dev'
}

export function parseRequirementsText(text: string): ImportedPipDep[] {
  const out: ImportedPipDep[] = []
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.split('#', 1)[0].trim()
    if (!line) continue
    if (line.startsWith('-')) continue
    if (line.startsWith('git+') || line.startsWith('http://') || line.startsWith('https://')) continue
    const markerParts = line.split(';', 1)
    const dep = markerParts[0]?.trim() || ''
    if (!dep) continue
    const m = dep.match(/^([A-Za-z0-9._-]+(?:\[[\w,\-]+\])?)(.*)$/)
    if (!m) continue
    const name = (m[1] || '').trim()
    const version = (m[2] || '').trim()
    if (!name) continue
    out.push({
      name,
      version: version || '',
      version_mode: version ? 'custom' : 'latest',
    })
  }
  return out
}

export function parseAptListText(
  text: string,
): { apt: string[]; constraints: Record<string, string> } {
  const apt: string[] = []
  const constraints: Record<string, string> = {}
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.split('#', 1)[0].trim()
    if (!line) continue
    const m = line.match(/^([a-z0-9][a-z0-9.+-]*)(.*)$/)
    if (!m) continue
    const name = m[1]
    const rest = (m[2] || '').trim()
    apt.push(name)
    if (rest) constraints[name] = rest
  }
  return { apt, constraints }
}

export function parsePackageJsonText(text: string): ImportedNpmDep[] {
  const data = JSON.parse(text) as {
    dependencies?: Record<string, string>
    devDependencies?: Record<string, string>
  }
  const out: ImportedNpmDep[] = []
  const pushEntries = (entries: Record<string, string> | undefined, scope: 'prod' | 'dev') => {
    for (const [name, version] of Object.entries(entries || {})) {
      const trimmed = (version || '').trim()
      out.push({
        name: name.trim(),
        version: trimmed,
        version_mode: trimmed ? 'custom' : 'latest',
        package_manager: 'npm',
        install_scope: scope,
      })
    }
  }
  pushEntries(data.dependencies, 'prod')
  pushEntries(data.devDependencies, 'dev')
  return out
}
