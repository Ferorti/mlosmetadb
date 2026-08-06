export function formatMlo(str) {
  if (!str) return ''
  if (str === 'NotInformed') return 'No MLO associated'
  return str.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

// 'NotInformed' is a real, kept vocabulary entry (see BIOLOGY.md's "NotInformed"
// section), not something to drop from the data. But displaying it alongside a
// protein's real MLOs adds no information ("has MLO X" already implies "not
// uninformed"), so any view listing a protein's MLOs for some scope (whole
// protein, or in the future per source-db) should show it only when it is the
// only entry in that scope.
export function filterMlos(mlos) {
  if (!mlos?.length) return []
  const real = mlos.filter(m => m !== 'NotInformed')
  return real.length ? real : ['NotInformed']
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
