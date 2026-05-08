export function formatMlo(str) {
  if (!str) return ''
  return str.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

export function formatCount(n) {
  if (n == null) return '—'
  return n.toLocaleString()
}

export function toMloSlug(displayName) {
  if (!displayName) return ''
  return displayName.trim().toLowerCase().replace(/\s+/g, '_')
}

export function formatOrganism(str) {
  if (!str) return ''
  return str.replace(/\s*\(strain[^)]*\)/i, '').trim()
}

export function formatPmids(pmidStr) {
  if (!pmidStr) return []
  return pmidStr.split(';').map(id => ({
    id: id.trim(),
    url: `https://pubmed.ncbi.nlm.nih.gov/${id.trim()}`
  }))
}
