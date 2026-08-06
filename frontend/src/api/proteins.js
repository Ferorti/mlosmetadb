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
  return `/api/proteins/export?${search.toString()}`
}
