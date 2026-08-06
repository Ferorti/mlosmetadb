// Client-side re-implementation of the backend's protein list sort
// (refactor/api/queries/protein_queries.py::_build_sort), used only for
// the plain-text /search fallback path, which has no sort_by concept of its
// own. That path returns results in uniprot_id-ascending order: the UI always
// sends mode=fuzzy (src/api/search.js's default), which routers/search.py
// routes to search_proteins_like() -- a plain LIKE query with
// `ORDER BY p.uniprot_id`. The FTS5 branch (search_proteins_fts,
// `ORDER BY rank`) is only reachable with mode=exact, which the UI never sends.
//
// KEEP IN SYNC: this file and _build_sort() must agree. Changing the sort
// semantics in either one without the other silently makes the free-text
// search path order results differently from every other search path.
//
// Mirrors the backend rules exactly:
//   - NULL/missing values always sort last, regardless of direction.
//   - Every key ties-break on uniprot_id ascending.
//   - 'role' direction is baked into a rank (asc: driver=0, client=1, else=2;
//     desc: client=0, driver=1, else=2), not into ASC/DESC on the compare.

// Plain ordinal (code-unit) comparison, not localeCompare: SQLite's default
// text collation is BINARY (byte-wise, case-sensitive, no COLLATE override
// anywhere in queries/), which this matches for ASCII text -- localeCompare
// would apply locale-aware/case-insensitive-ish ordering that can diverge.
function ordinalCompare(a, b) {
  if (a < b) return -1
  if (a > b) return 1
  return 0
}

function byUniprotIdAsc(a, b) {
  return ordinalCompare(a.uniprot_id ?? '', b.uniprot_id ?? '')
}

// Builds a comparator for a numeric/string field where nulls always sort
// last regardless of sortOrder, ties broken by uniprot_id ascending.
function fieldComparator(getValue, compareFn, sortOrder) {
  return (a, b) => {
    const av = getValue(a)
    const bv = getValue(b)
    const aNull = av === null || av === undefined
    const bNull = bv === null || bv === undefined
    if (aNull && bNull) return byUniprotIdAsc(a, b)
    if (aNull) return 1
    if (bNull) return -1
    const cmp = sortOrder === 'asc' ? compareFn(av, bv) : compareFn(bv, av)
    return cmp !== 0 ? cmp : byUniprotIdAsc(a, b)
  }
}

const compareStrings = ordinalCompare
const compareNumbers = (a, b) => a - b

function roleRank(p, sortOrder) {
  if (sortOrder === 'asc') {
    if (p.has_driver) return 0
    if (p.has_client) return 1
    return 2
  }
  if (p.has_client) return 0
  if (p.has_driver) return 1
  return 2
}

/**
 * Sort a ProteinSummary[] array the same way the sort dropdown's seven
 * options (five distinct sort_by keys x direction) would sort it
 * server-side. Returns a new array (does not mutate the input).
 */
export function sortProteins(proteins, sortBy, sortOrder) {
  if (!Array.isArray(proteins)) return proteins
  const arr = [...proteins]

  switch (sortBy) {
    case 'gene_name':
      arr.sort(fieldComparator(p => p.gene_name, compareStrings, sortOrder))
      break
    case 'disorder_mobidb_lite_dc':
      arr.sort(fieldComparator(p => p.disorder_mobidb_lite_dc, compareNumbers, sortOrder))
      break
    case 'source_db_count':
      arr.sort(fieldComparator(p => p.source_db_count, compareNumbers, sortOrder))
      break
    case 'mlo_count':
      arr.sort(fieldComparator(p => p.mlo_count, compareNumbers, sortOrder))
      break
    case 'role':
      arr.sort((a, b) => {
        const cmp = roleRank(a, sortOrder) - roleRank(b, sortOrder)
        return cmp !== 0 ? cmp : byUniprotIdAsc(a, b)
      })
      break
    default:
      // Unrecognized sort_by: mirror the backend's own fallthrough default.
      arr.sort(byUniprotIdAsc)
  }
  return arr
}
