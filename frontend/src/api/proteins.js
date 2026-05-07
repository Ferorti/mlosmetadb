import client from './client'

export function getProteins(params = {}) {
  return client.get('/proteins', { params })
}

export function getProtein(uniprotId, ppiPage = null) {
  const params = ppiPage ? { ppi_page: ppiPage } : {}
  return client.get(`/protein/${uniprotId}`, { params })
}
