import client from './client'

export function getProteins(params = {}) {
  return client.get('/proteins', { params })
}

export function getProtein(uniprotId, ppiPage = null) {
  const params = ppiPage ? { ppi_page: ppiPage } : {}
  return client.get(`/protein/${uniprotId}`, { params })
}

export function searchOrganisms(q, limit = 10) {
  return client.get('/organisms/search', { params: { q, limit } })
}

export function getProteinPpi(uniprotId, params = {}) {
  return client.get(`/protein/${uniprotId}/ppi`, { params })
}

export function getProteinOrthologs(uniprotId) {
  return client.get(`/protein/${uniprotId}/orthologs`)
}

export function checkCitations(uniprotIds) {
  return client.post('/proteins/citations', { uniprot_ids: uniprotIds })
}

export function buildExportUrl(params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) {
      value.forEach(v => search.append(key, v))
    } else {
      search.append(key, value)
    }
  }
  // The browser navigates to this URL directly — it is a file download, not an
  // XHR — so it never passes through the axios instance and does not inherit
  // its baseURL. It has to apply the deployment base itself, or a build served
  // under /v2/ silently links to /api, which is a different deployment.
  return `${import.meta.env.BASE_URL}api/proteins/export?${search.toString()}`
}
