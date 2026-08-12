import client from './client'

// The four orthogonal axes that replaced the single `category` column
// (see database/mappings/_archive/mlo_mapping_decisions.md §13.2). Exported so
// the pages that build filter controls iterate this list instead of repeating
// the field names — adding a fifth axis should touch one line here.
export const MLO_AXES = [
  'spatial_location',
  'taxonomic_scope',
  'physiological_state',
  'cell_type_context',
]

/**
 * GET /mlos, optionally filtered by any combination of the four axes.
 *
 * Axis filters conjoin server-side, so
 * `{ spatial_location: 'nucleus', physiological_state: 'stress_induced' }`
 * returns the 5 nuclear stress-induced organelles — a question the old
 * `?category=` could not express, because its values mixed places (Nuclear)
 * with lineages (Procariota), cell types (Neuronal) and processes (Autofagia).
 *
 * `?category=` is gone from the API and is NOT translated. Passing it would be
 * worse than an error: FastAPI ignores unknown query params, so the request
 * silently returns the whole vocabulary unfiltered.
 */
export function getMlos(axes = {}) {
  const params = {}
  for (const axis of MLO_AXES) {
    if (axes[axis]) params[axis] = axes[axis]
  }
  return client.get('/mlos', { params })
}

export function getMlo(mlo, params = {}) {
  return client.get(`/mlo/${mlo}`, { params })
}
