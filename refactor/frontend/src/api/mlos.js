import client from './client'

export function getMlos(category = null) {
  return client.get('/mlos', { params: category ? { category } : {} })
}

export function getMlo(mlo, params = {}) {
  return client.get(`/mlo/${mlo}`, { params })
}
