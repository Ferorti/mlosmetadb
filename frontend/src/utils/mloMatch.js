import { formatMlo } from '@/utils/format'

/**
 * Matches a query against an organelle's unified name *and* the names its
 * source databases use.
 *
 * 241 aliases across 102 organelles cannot be derived from the unified name —
 * "GW-body" is p_body, "Dense Fibrillar Component" is nucleolus, "cGAS foci"
 * is cgas_dna_complex — so a filter that only reads the unified name misses
 * most of the vocabulary people actually type.
 *
 * Returns which aliases matched, not just whether any did: a card that lights
 * up for "GW-body" while showing an unrelated name reads as a bug.
 */
export function matchMlo(mlo, query) {
  const q = (query ?? '').trim().toLowerCase()
  if (!q) return { matched: true, via: [] }

  const unified = mlo.unified_mlo ?? ''
  const byName =
    unified.toLowerCase().includes(q) ||
    unified.replace(/_/g, ' ').toLowerCase().includes(q) ||
    formatMlo(unified).toLowerCase().includes(q)

  const via = (mlo.source_names ?? []).filter(n => n.toLowerCase().includes(q))

  // When the visible name already explains the hit, report no aliases. The
  // grey line on a card has to mean "this matched under a name you cannot see"
  // — searching "stress" should annotate DNA damage foci (via "53BP1 Mitotic
  // Stress Body"), not Stress granule, whose title says it already.
  return { matched: byName || via.length > 0, via: byName ? [] : via }
}

/**
 * Filter a list, annotating each survivor with the aliases that matched.
 * `via` is empty when the unified name alone explains the hit — the card has
 * nothing extra to justify then.
 */
export function filterMlosByQuery(mlos, query) {
  const out = []
  for (const mlo of mlos ?? []) {
    const { matched, via } = matchMlo(mlo, query)
    if (matched) out.push({ ...mlo, matchedNames: via })
  }
  return out
}
