/**
 * Display helpers for the four MLO classification axes.
 *
 * These replaced the single `category` field on 2026-08-12 (see
 * database/mappings/_archive/mlo_mapping_decisions.md §13.2). The old category
 * mixed places (Nuclear) with lineages (Procariota), cell types (Neuronal) and
 * processes (Autofagia), so `MloBadges.vue` and `MlosPage.vue` each carried
 * their own half-map of Spanish values and both printed "Other" for anything
 * unexpected. One module now owns labels, colors and the two caveats the
 * biological audit asked us to surface.
 *
 * Values arrive from the API already normalised (English, lowercase, `_`-joined;
 * Latin names for the taxonomic axis). Every label function falls back to
 * humanising the raw value rather than to a placeholder: the vocabulary can grow
 * a value before this file knows about it, and showing "Podocyte" for an unknown
 * `podocyte` is right, while showing "Other" is a lie.
 */

const HUMANIZE_EXCEPTIONS = {
  in_vitro: 'In vitro',
  nucleus_and_cytoplasm: 'Nucleus & cytoplasm',
  t_cell: 'T cell',
  stress_induced: 'Stress-induced',
}

function humanize(value) {
  if (!value) return ''
  if (HUMANIZE_EXCEPTIONS[value]) return HUMANIZE_EXCEPTIONS[value]
  return value.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

// ── spatial_location ────────────────────────────────────────────────────────
// Nucleus stays blue and cytoplasm amber, the two the home grid already used for
// the Spanish categories, so the change does not reshuffle familiar colors.
const SPATIAL_COLORS = {
  nucleus: 'bg-blue-500',
  nucleus_and_cytoplasm: 'bg-blue-400',
  cytoplasm: 'bg-amber-400',
  cytoskeleton: 'bg-violet-400',
  plasma_membrane: 'bg-teal-500',
  extracellular: 'bg-rose-400',
  mitochondrion: 'bg-orange-600',
  plastid: 'bg-green-600',
  in_vitro: 'bg-gray-300',
  unspecified: 'bg-gray-200',
}

export function spatialLocationColor(value) {
  return SPATIAL_COLORS[value] ?? 'bg-gray-300'
}

export function spatialLocationLabel(value) {
  return humanize(value)
}

/**
 * The auditor derived 121 of the 177 spatial values from the curated v6 category
 * and assigned the other 56 by hand from the organelle's biology, asking
 * explicitly that those be reviewed (docs/review/findings.csv R3-OWN-spatial-56).
 * Returns a tooltip for the pending ones and '' for the rest, so the caveat
 * travels with the value instead of living in a doc nobody opens.
 */
export function spatialLocationNote(mlo) {
  if (mlo?.spatial_location_evidence !== 'hand_assigned') return ''
  return 'Location assigned from the organelle’s biology by the biological audit, pending curator review'
}

export function isSpatialLocationProvisional(mlo) {
  return mlo?.spatial_location_evidence === 'hand_assigned'
}

// ── taxonomic_scope ─────────────────────────────────────────────────────────

export function taxonomicScopeLabel(value) {
  if (!value) return ''
  // `pan_Fungi+Metazoa` marks a term where no kingdom reached 80% of its
  // proteins. Reading it as a compound label is clearer than exposing the
  // prefix, which looks like a typo to anyone who has not read the schema.
  if (value.startsWith('pan_')) {
    return value.slice(4).split('+').join(' + ')
  }
  return value
}

/** Below this many proteins with a known organism, the axis is a hint, not a claim. */
export const TAXONOMIC_SUPPORT_THIN = 2

export function isTaxonomicScopeThin(mlo) {
  const n = mlo?.taxonomic_support_n
  return n != null && n <= TAXONOMIC_SUPPORT_THIN
}

/**
 * The tooltip that keeps the taxonomic axis honest. It is derived from the
 * organisms of the *annotated proteins*, so it describes this dataset and not
 * the organelle concept: `aggresome` reads Bacteria because its six annotated
 * proteins are all E. coli, while the literature's aggresome is a mammalian
 * structure. 63 of 177 terms rest on two proteins or fewer.
 */
export function taxonomicScopeNote(mlo) {
  const n = mlo?.taxonomic_support_n
  if (n == null) return ''
  if (n === 0) {
    return 'No annotated protein has a known organism, so no taxonomic scope could be derived'
  }
  const base = `Derived from ${n} annotated protein${n === 1 ? '' : 's'} with a known organism — describes this dataset’s annotations, not the organelle itself`
  return n <= TAXONOMIC_SUPPORT_THIN ? `${base}. Too few to read as a claim about taxonomic range.` : base
}

// ── physiological_state / cell_type_context ─────────────────────────────────

export function physiologicalStateLabel(value) {
  return humanize(value)
}

export function cellTypeContextLabel(value) {
  return humanize(value)
}

// ── the axes as filterable dimensions ───────────────────────────────────────
// Drives the filter controls: one entry per axis, in the order a reader is most
// likely to reach for. `cell_type_context` is last and empty for 143 of the 177
// terms by design — the axis applies only where the cell type is part of the
// organelle's definition.
export const AXIS_FILTERS = [
  { key: 'spatial_location',    label: 'Location',    allLabel: 'Any location',     format: spatialLocationLabel },
  { key: 'physiological_state', label: 'State',       allLabel: 'Any state',        format: physiologicalStateLabel },
  { key: 'taxonomic_scope',     label: 'Taxonomy',    allLabel: 'Any taxonomy',     format: taxonomicScopeLabel },
  { key: 'cell_type_context',   label: 'Cell type',   allLabel: 'Any cell type',    format: cellTypeContextLabel },
]

/** Distinct non-null values of one axis across a list of MLOs, sorted by label. */
export function axisValues(mlos, axis) {
  const seen = new Set()
  for (const mlo of mlos ?? []) {
    if (mlo?.[axis]) seen.add(mlo[axis])
  }
  const format = AXIS_FILTERS.find(a => a.key === axis)?.format ?? humanize
  return [...seen].sort((a, b) => format(a).localeCompare(format(b)))
}
