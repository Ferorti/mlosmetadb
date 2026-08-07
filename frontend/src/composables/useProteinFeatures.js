import { computed, toValue } from 'vue'
import {
  parseIdrRegions,
  parseLcdRegions,
  parseDomains,
  buildFeatureStats,
} from '@/utils/parseFeatures.js'

/**
 * Normalizes a protein's sequence features into one flat list that the track,
 * the sequence block, the feature table and the structure viewer all key off
 * the same way.
 *
 * Every entry carries a `ranges` array rather than a single start/end, because
 * a Pfam domain that repeats along the protein is one *feature* drawn in
 * several places: hovering its table row lights every instance at once. For
 * IDRs, LCDs and MoRFs `ranges` always holds exactly one entry.
 */

export const FEATURE_COLORS = {
  IDR:    '#F5A0A0',
  LCD:    '#FAC775',
  Domain: '#86C865',
  MoRF:   '#C4B5FD',
}

export const FEATURE_TYPE_LABELS = {
  IDR:    'Intrinsically Disordered Region',
  LCD:    'Composition Bias',
  Domain: 'Domain',
  MoRF:   'MoRF',
}

// Table group order, and also the SVG paint order (later types draw on top).
const GROUP_ORDER = ['Domain', 'IDR', 'LCD', 'MoRF']

const PAINT_ORDER = { IDR: 0, LCD: 1, Domain: 2, MoRF: 3 }

export function formatSource(src) {
  if (!src) return '—'
  if (src.toLowerCase() === 'pfam')  return 'Pfam'
  if (src.toLowerCase() === 'smart') return 'SMART'
  return src
}

export function formatRanges(ranges) {
  return ranges.map(r => `${r.start}–${r.end}`).join(', ')
}

/**
 * @param featuresSource getter/ref returning `protein.sequence_features`
 * @param lengthSource   getter/ref returning `protein.sequence_length`
 */
export function useProteinFeatures(featuresSource, lengthSource) {
  const raw = computed(() => toValue(featuresSource) ?? null)
  const sequenceLength = computed(() => toValue(lengthSource) ?? 0)

  // Source filtering matches what the track has always drawn: only the primary
  // curated predictors, not every predictor MobiDB reports.
  const idrRegions = computed(() =>
    parseIdrRegions(raw.value?.idr_regions ?? raw.value?.idrs ?? null)
      .filter(r => r.source === 'MobiDB-lite')
  )
  const lcdRegions = computed(() =>
    parseLcdRegions(raw.value?.lcr_regions ?? raw.value?.lcds ?? null)
      .filter(r => r.source === 'MobiDB-lite-sub')
  )
  const domainRegions = computed(() => parseDomains(raw.value?.domains ?? null))
  const morfRegions   = computed(() => raw.value?.morfs ?? [])

  function simpleFeature(type, r, label, extra = {}) {
    return {
      id:     `${type}:${r.source ?? '—'}:${r.start}-${r.end}`,
      type,
      ranges: [{ start: r.start, end: r.end }],
      label,
      accession: null,
      source: r.source ?? null,
      color:  FEATURE_COLORS[type],
      ...extra,
    }
  }

  // Domains group by accession: one feature, many ranges.
  const domainFeatures = computed(() => {
    const byKey = new Map()
    for (const d of domainRegions.value) {
      const key = d.accession ?? d.label ?? `${d.start}-${d.end}`
      if (!byKey.has(key)) {
        byKey.set(key, {
          id:        `Domain:${key}`,
          type:      'Domain',
          ranges:    [],
          label:     d.label ?? '—',
          accession: d.accession ?? '—',
          source:    d.database ?? null,
          color:     FEATURE_COLORS.Domain,
        })
      }
      byKey.get(key).ranges.push({ start: d.start, end: d.end })
    }
    for (const f of byKey.values()) f.ranges.sort((a, b) => a.start - b.start)
    return [...byKey.values()].sort((a, b) => a.ranges[0].start - b.ranges[0].start)
  })

  const features = computed(() => [
    ...domainFeatures.value,
    ...idrRegions.value.map(r => simpleFeature('IDR', r, 'IDR')),
    ...lcdRegions.value.map(r => simpleFeature('LCD', r, 'Low complexity region')),
    ...morfRegions.value.map(r => simpleFeature('MoRF', r, r.label ?? 'MoRF')),
  ])

  /** One entry per drawn rectangle — what the SVG and the sequence overlay iterate. */
  const featureSpans = computed(() => {
    const spans = []
    for (const f of features.value) {
      for (const r of f.ranges) {
        spans.push({ featureId: f.id, type: f.type, color: f.color, label: f.label, source: f.source, ...r })
      }
    }
    return spans.sort((a, b) => PAINT_ORDER[a.type] - PAINT_ORDER[b.type])
  })

  const byId = computed(() => new Map(features.value.map(f => [f.id, f])))

  /** Table groups, in a fixed order, skipping types with no features. */
  const groups = computed(() =>
    GROUP_ORDER
      .map(type => ({
        type,
        color: FEATURE_COLORS[type],
        label: FEATURE_TYPE_LABELS[type],
        items: features.value.filter(f => f.type === type),
      }))
      .filter(g => g.items.length > 0)
  )

  const stats = computed(() => buildFeatureStats({
    idrRegions:     idrRegions.value,
    lcdRegions:     lcdRegions.value,
    domains:        domainFeatures.value,
    sequenceLength: sequenceLength.value,
  }))

  const hasFeatures = computed(() => features.value.length > 0)

  /** Feature spans covering a 1-based residue position, topmost paint order last. */
  function spansAt(pos) {
    return featureSpans.value.filter(s => pos >= s.start && pos <= s.end)
  }

  return { features, featureSpans, byId, groups, stats, hasFeatures, sequenceLength, spansAt }
}
