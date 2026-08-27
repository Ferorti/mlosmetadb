/**
 * Parse sequence feature data into arrays.
 * Handles two formats:
 *   - New (protein detail): direct arrays of {start, end, source, ...}
 *   - Old (result summary): nested objects {mobidb_lite: [...]}
 */

export function parseIdrRegions(idrJson) {
  if (!idrJson) return []
  try {
    const parsed = typeof idrJson === 'string' ? JSON.parse(idrJson) : idrJson
    if (Array.isArray(parsed)) {
      return parsed.map(r => ({ start: r.start, end: r.end, source: r.source ?? null }))
    }
    // Old format: {mobidb_lite: [[start, end], ...], alphafold: [[start, end], ...]}
    if (parsed.alphafold) {
      return parsed.alphafold.map(([start, end]) => ({ start, end, source: 'AlphaFold-disorder' }))
    }
    const arr = parsed.mobidb_lite ?? []
    return arr.map(([start, end]) => ({ start, end, source: 'MobiDB-lite' }))
  } catch { return [] }
}

export function parseLcdRegions(lcrJson) {
  if (!lcrJson) return []
  try {
    const parsed = typeof lcrJson === 'string' ? JSON.parse(lcrJson) : lcrJson
    if (Array.isArray(parsed)) {
      return parsed.map(r => ({ start: r.start, end: r.end, source: r.source ?? null, label: r.label ?? null }))
    }
    // Old format: {mobidb_lite: [{start, end, label}, ...]}
    const arr = parsed.mobidb_lite ?? []
    return arr.map(r => ({ start: r.start, end: r.end, source: 'MobiDB-lite-sub', label: r.label ?? null }))
  } catch { return [] }
}

export function parseDomains(domainsJson) {
  if (!domainsJson) return []
  try {
    const parsed = typeof domainsJson === 'string' ? JSON.parse(domainsJson) : domainsJson
    let all = []
    if (Array.isArray(parsed)) {
      // New format: flat array with database field (lowercase)
      all = parsed.filter(d => d.database?.toLowerCase() === 'pfam')
    } else {
      // Old format: keyed object {Pfam: [...], SMART: [...]}
      all = parsed.Pfam ?? parsed.pfam ?? []
    }
    // Deduplicate by accession+start+end to remove exact duplicates
    const seen = new Set()
    return all
      .filter(d => {
        const key = `${d.accession ?? d.label}|${d.start}|${d.end}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      .map(d => ({ start: d.start, end: d.end, label: d.label, accession: d.accession, database: d.database }))
  } catch { return [] }
}

/**
 * Coverage percentage of a list of regions over total sequence length.
 * Uses a mask to avoid double-counting overlapping regions.
 */
export function calcCoverage(regions, seqLen) {
  if (!regions.length || !seqLen) return null
  const mask = new Uint8Array(seqLen + 1)
  regions.forEach(({ start, end }) => {
    for (let i = start; i <= Math.min(end, seqLen); i++) mask[i] = 1
  })
  const covered = mask.reduce((a, b) => a + b, 0)
  return Math.round((covered / seqLen) * 100)
}

/**
 * Build the inline stats string: "IDRs: 54% · LCD: 12% · 3 domains · 526 aa"
 */
export function buildFeatureStats({ idrRegions, lcdRegions, domains, sequenceLength }) {
  const parts = []
  const idrPct = calcCoverage(idrRegions, sequenceLength)
  const lcdPct = calcCoverage(lcdRegions, sequenceLength)

  if (idrPct != null) parts.push(`IDRs: ${idrPct}%`)
  if (lcdPct != null) parts.push(`LCD: ${lcdPct}%`)
  if (domains.length)  parts.push(`${domains.length} domain${domains.length > 1 ? 's' : ''}`)
  if (sequenceLength)  parts.push(`${sequenceLength.toLocaleString()} aa`)

  return parts.join(' · ')
}
