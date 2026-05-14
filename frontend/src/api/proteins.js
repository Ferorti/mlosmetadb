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
