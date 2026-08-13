import client from './client'

export async function getUnificationStats() {
  const { data } = await client.get('/unification/stats')
  return data
}

export function discrepantPairsExportUrl() {
  return `${import.meta.env.BASE_URL}api/unification/discrepant-pairs/export`
}

export function mloTermMappingExportUrl() {
  return `${import.meta.env.BASE_URL}api/unification/mlo-term-mapping/export`
}
