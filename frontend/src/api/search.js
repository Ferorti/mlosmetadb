import client from './client'

export function searchBasic(q, mode = 'fuzzy') {
  return client.get('/search', { params: { q, mode } })
}

export function searchAdvanced(params) {
  return client.get('/search/advanced', { params })
}
