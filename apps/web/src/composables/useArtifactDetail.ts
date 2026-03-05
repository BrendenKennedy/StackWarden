import { computed, ref, type Ref, watch } from 'vue'
import type { ArtifactDetail, VerifyResponse } from '@/api/types'
import { artifacts as artifactsApi, verify as verifyApi } from '@/api/endpoints'
import { toUserErrorMessage } from '@/utils/errors'

const TABS = [
  { key: 'manifest', label: 'Manifest' },
  { key: 'plan', label: 'Plan' },
  { key: 'profile', label: 'Profile' },
  { key: 'stack', label: 'Stack' },
  { key: 'sbom', label: 'SBOM' },
] as const

export type ArtifactDetailTabKey = (typeof TABS)[number]['key']

export function useArtifactDetail(
  artifactId: Ref<string | null>,
  options?: { onDeleted?: () => void },
) {
  const artifact = ref<ArtifactDetail | null>(null)
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const verifying = ref(false)
  const deleting = ref(false)
  const verifyResult = ref<VerifyResponse | null>(null)

  const activeTab = ref<ArtifactDetailTabKey>('manifest')
  const tabData = ref<unknown>(null)
  const tabLoading = ref(false)
  const tabError = ref<string | null>(null)
  let tabRequestId = 0

  const tupleSummary = computed(() => {
    const d = tabData.value as Record<string, unknown> | null
    if (!d || activeTab.value !== 'manifest') return ''
    const tupleId = (d.tuple_id as string) || ''
    if (!tupleId) return ''
    return `${tupleId} (${(d.tuple_status as string) || 'unknown'}, mode=${(d.tuple_mode as string) || 'unknown'})`
  })

  async function loadTab(key: string) {
    const id = artifactId.value
    if (!id) return
    activeTab.value = key as ArtifactDetailTabKey
    tabLoading.value = true
    tabError.value = null
    tabData.value = null
    const reqId = ++tabRequestId
    try {
      const data = await artifactsApi.getFile(id, key)
      if (reqId !== tabRequestId) return
      tabData.value = data
    } catch (err: unknown) {
      if (reqId !== tabRequestId) return
      const msg = toUserErrorMessage(err)
      if (msg.includes('404') || msg.includes('Not Found')) {
        tabError.value =
          key === 'sbom'
            ? 'SBOM not generated. Run `stackwarden sbom <tag>` to export.'
            : `${key}.json not found`
      } else {
        tabError.value = msg
      }
    } finally {
      if (reqId === tabRequestId) tabLoading.value = false
    }
  }

  async function loadArtifact() {
    const id = artifactId.value
    if (!id) return
    loading.value = true
    loadError.value = null
    artifact.value = null
    try {
      artifact.value = await artifactsApi.get(id)
      await loadTab('manifest')
    } catch (err: unknown) {
      loadError.value = toUserErrorMessage(err)
    } finally {
      loading.value = false
    }
  }

  async function runVerify() {
    if (!artifact.value) return
    verifying.value = true
    try {
      const tagOrId = artifact.value.id || artifact.value.tag
      verifyResult.value = await verifyApi.run({ tag_or_id: tagOrId })
    } catch (err: unknown) {
      verifyResult.value = {
        ok: false,
        errors: [toUserErrorMessage(err)],
        warnings: [],
        facts: {},
        recomputed_fingerprint: null,
        label_fingerprint: null,
        catalog_fingerprint: null,
        actions: [],
      }
    } finally {
      verifying.value = false
    }
  }

  async function markStale() {
    const id = artifactId.value
    if (!artifact.value || !id) return
    try {
      await artifactsApi.markStale(id)
      artifact.value = await artifactsApi.get(id)
    } catch (e) {
      console.error('Failed to mark stale:', e)
    }
  }

  async function deleteArtifact() {
    const id = artifactId.value
    if (!artifact.value || !id) return
    deleting.value = true
    try {
      await artifactsApi.remove(id)
      options?.onDeleted?.()
    } catch (err: unknown) {
      console.error('Failed to delete artifact:', err)
      loadError.value = toUserErrorMessage(err)
    } finally {
      deleting.value = false
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  function reset() {
    artifact.value = null
    verifyResult.value = null
    activeTab.value = 'manifest'
    tabData.value = null
  }

  watch(
    () => artifactId.value,
    (id) => {
      if (id) {
        loadArtifact()
      } else {
        reset()
      }
    },
    { immediate: true },
  )

  return {
    tabs: TABS,
    artifact,
    loading,
    loadError,
    verifying,
    deleting,
    verifyResult,
    activeTab,
    tabData,
    tabLoading,
    tabError,
    tupleSummary,
    loadTab,
    runVerify,
    markStale,
    deleteArtifact,
    copy,
  }
}
