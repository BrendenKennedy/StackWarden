export const BLOCK_ROUTE_REMOVE_AFTER = '2026-12-31'

export function isLegacyBlocksRoute(path: string | null | undefined): boolean {
  if (!path) return false
  return path === '/blocks' || path.startsWith('/blocks/')
}

export function formatBlocksRouteDeprecation(path: string): string {
  return (
    `[deprecation] route "${path}" is deprecated; use "/layers" routes instead. ` +
    `Compatibility redirects are scheduled for removal after ${BLOCK_ROUTE_REMOVE_AFTER}.`
  )
}
