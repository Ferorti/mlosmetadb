import { ref } from 'vue'
import { getProtein } from '@/api/proteins.js'

export function useProtein() {
  const protein = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchProtein(uniprotId, ppiPage = null) {
    loading.value = true
    error.value = null
    try {
      const res = await getProtein(uniprotId, ppiPage)
      protein.value = res.data
    } catch (e) {
      error.value = e?.response?.status === 404 ? 'not_found' : 'error'
    } finally {
      loading.value = false
    }
  }

  return { protein, loading, error, fetchProtein }
}
