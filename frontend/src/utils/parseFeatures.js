/**
 * Parse protein_summary JSON fields into arrays for SequenceFeatureViewer.
 * All inputs may be null, undefined, or JSON strings.
 */

export function parseIdrRegions(idrJson) {
  if (!idrJson) return []
  try {
    const parsed = typeof idrJson === 'string' ? JSON.parse(idrJson) : idrJson
    // Use mobidb_lite as primary source; fall back to alphafold
    const source = parsed.mobidb_lite ?? parsed.alphafold ?? []
    return source.map(([start, end]) => ({ start, end }))
  } catch { return [] }
}

export function parseLcdRegions(lcrJson) {
  if (!lcrJson) return []
  try {
    const parsed = typeof lcrJson === 'string' ? JSON.parse(lcrJson) : lcrJson
    const source = parsed.mobidb_lite ?? []
    return source.map(r => ({ start: r.start, end: r.end, label: r.label ?? 'LCD' }))
  } catch { return [] }
}

export function parseDomains(domainsJson) {
  if (!domainsJson) return []
  try {
    const parsed = typeof domainsJson === 'string' ? JSON.parse(domainsJson) : domainsJson
    const all = Object.values(parsed).flat()
    // Deduplicate by label
    const seen = new Set()
    return all
      .filter(d => { if (seen.has(d.label)) return false; seen.add(d.label); return true })
      .map(d => ({ start: d.start, end: d.end, label: d.label, accession: d.accession }))
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
