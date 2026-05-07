export function formatMlo(str) {
  if (!str) return ''
  return str.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

export function formatCount(n) {
  if (n == null) return '—'
  return n.toLocaleString()
}

export function formatPmids(pmidStr) {
  if (!pmidStr) return []
  return pmidStr.split(';').map(id => ({
    id: id.trim(),
    url: `https://pubmed.ncbi.nlm.nih.gov/${id.trim()}`
  }))
}
