# Three bugs in the PPI query path: silently dropped evidence, MLO-unscoped driver flag, silently ignored role values

**Labels:** `bug`, `api`, `ppi`
**Severity:** high for #1 (silent data loss, large blast radius), medium for #2
and #3 (wrong/ignored filter, no data loss).
**Status:** **resolved 2026-08-21.** Found the same day during a general API
bug/route audit (no specific report triggered it).

---

## Summary

All three live in the PPI code path — `api/queries/protein_queries.py`'s
`get_ppi_page`/`get_ppi_all`, and the two endpoints that call them,
`GET /protein/{uniprot_id}?ppi_page=N` and `GET /protein/{uniprot_id}/ppi`.
None is covered by `api/tests/` — there is no test file exercising either
function or either endpoint's `ppi_page`/`role`/`mlo` parameters.

## 1. `get_ppi_page` collapses multi-evidence PPI rows via a bare, non-aggregated `GROUP BY`

**File**: `api/queries/protein_queries.py:576-600` (`get_ppi_page`), used by
`GET /protein/{uniprot_id}?ppi_page=N` (`api/routers/proteins.py:243-292`).

```python
SELECT
    p.uniprot_id_b AS partner_uniprot_id,
    pr.gene_name AS partner_gene,
    p.in_db,
    p.experimental_system,
    p.pubmed_id,
    p.source_version AS source
FROM ppi p
LEFT JOIN proteins pr ON p.uniprot_id_b = pr.uniprot_id
WHERE p.uniprot_id_a = ?
GROUP BY p.uniprot_id_b
```

`ppi` has no unique constraint on `(uniprot_id_a, uniprot_id_b)` — each row is
one BioGRID evidence record, and most partners have several. `experimental_system`,
`pubmed_id`, `source_version` are bare (non-aggregated) columns under
`GROUP BY p.uniprot_id_b`, so which row's value SQLite keeps is unspecified —
it can change with query plan, SQLite version, or a DB rebuild.

The sibling function `get_ppi_all` (same file, lines 463-475) does this
correctly for the identical relationship, via `GROUP_CONCAT(DISTINCT ...)` +
`COUNT(...)`. `get_ppi_page` was never brought in line with it.

### Evidence

`ppi` rows for `uniprot_id_a='P0DTD1' AND uniprot_id_b='Q9Y6K9'`:

```
Biochemical Activity      36075915
Co-crystal Structure      36075915
Affinity Capture-Western  35856559
Reconstituted Complex     38514841
Affinity Capture-MS       39400381
```

Five independent evidence rows, four distinct PMIDs. `get_ppi_page`'s query
shape returns exactly one of them for that partner — non-deterministically.

Scale check against the live DB: **55,463** distinct `(uniprot_id_a,
uniprot_id_b)` pairs in `ppi` have more than one evidence row. Every one of
them is affected whenever the hub side is paged via `ppi_page`. A second
example, `P04637`/`Q00987`, has 9 evidence rows spanning 8+ PMIDs and 8+ distinct
experimental systems (Co-crystal Structure, Reconstituted Complex,
Co-purification, Affinity Capture-MS, Affinity Capture-Western, Proximity
Label-MS, Affinity Capture-RNA, Biochemical Activity, PCA, FRET) — all but one
silently dropped by this code path.

### Failure scenario

`GET /protein/P0DTD1?ppi_page=1` → the item for partner `Q9Y6K9` reports
`evidence_types: ["Biochemical Activity"]`, `pubmed_id: "36075915"` — as if
that were the only evidence for the interaction, silently hiding the other 4
evidence records and 3 PMIDs. This is the paginated-interactions view embedded
in `GET /protein/{id}` (`ppi_page` query param), so any UI built on top of it
shows fabricated single-evidence PPIs for the majority-multi-evidence case.

## 2. `role=driver` on `/protein/{id}/ppi?mlo=X` checks the partner's global driver flag, not driver-of-X

**File**: `api/queries/protein_queries.py:440-459` (`get_ppi_all`), used by
`GET /protein/{uniprot_id}/ppi?role=&mlo=`.

```python
if role == "driver":
    extra_where.append("COALESCE(ps.has_driver, 0) = 1")   # global flag, any MLO
...
if mlo:
    extra_where.append(
        f"EXISTS (SELECT 1 FROM mlo_annotations ma "
        f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND ma.unified_mlo = ? AND {policy.active_annotation_clause('ma')})"
    )
```

The two clauses are ANDed independently: "partner drives *some* MLO" AND
"partner has *any* annotation, any role, for MLO X" — not "partner drives MLO
X". This is exactly the bug class `_scoped_role_counts` (same file, its own
docstring at lines 172-181) was written to fix for `/proteins` and
`/search/advanced`'s facets; the fix was never carried over to this endpoint.

### Evidence

`P35189` (TAF14): driver of `in_vitro_droplet`/`NotInformed`, but only a
plain (non-driver) annotation for `transcriptional_condensate`. It's a PPI
partner of `P04050`.

```
GET /protein/P04050/ppi?role=driver&mlo=transcriptional_condensate
→ item for P35189: {"has_driver": true, "mlos": ["NotInformed", "in_vitro_droplet", "transcriptional_condensate"], ...}
```

`has_driver: true` under this filter reads as "drives transcriptional
condensates" — false; its only driver evidence is for a different organelle
entirely.

### Failure scenario

Any `role=driver&mlo=X` query on `/protein/{id}/ppi` mislabels every partner
that drives *some other* MLO while merely being annotated (any role) for X.

## 3. `role` on `/protein/{id}/ppi` silently no-ops for anything other than `"driver"`/`"component"`

**File**: `api/queries/protein_queries.py:450-453`; `api/routers/proteins.py:298`
(`role: str | None = Query(default=None)`, no validation).

```python
if role == "driver":
    extra_where.append("COALESCE(ps.has_driver, 0) = 1")
elif role == "component":
    extra_where.append("COALESCE(ps.has_driver, 0) = 0")
# no else, no validation
```

`role=regulator` — a value meaningful everywhere else in this API — or a typo
like `role=drivr`, adds no condition at all, so the full unfiltered partner
list is returned, indistinguishable from `role` being omitted. Every other
enum-like parameter in this API (`sort_by`, `sort_order`, `/search`'s `mode`)
raises `422 invalid_parameter` for an unrecognized value instead.

### Evidence

```
GET /protein/P04050/ppi              → total 72
GET /protein/P04050/ppi?role=regulator → total 72   (identical — filter silently ignored)
GET /protein/P04050/ppi?role=driver    → total 24   (this one does filter)
```

### Failure scenario

A client passing `role=regulator` (reasonable, since `component`/`regulator`
are real buckets in `/mlo/{id}`'s `by_role`) gets back all 72 partners
unfiltered, with no indication the parameter had no effect.

## What was done

1. **Finding 1 (`get_ppi_page`)**: rewritten to aggregate exactly like
   `get_ppi_all` — `GROUP_CONCAT(DISTINCT ...)` for `experimental_system` →
   `experimental_systems`, `pubmed_id` → `pubmed_ids`, `source_version` →
   `sources`, plus `COUNT(p.id) AS evidence_count`. `models/schemas.py`'s
   `PpiInteractionItem` changed from singular `pubmed_id: str | None` to
   `pubmed_ids: list[str]` (matching `PpiPartner`'s existing shape) and gained
   `evidence_count: int`; `routers/proteins.py`'s `_build_ppi_item` updated to
   match. This is an API contract change for `GET /protein/{id}?ppi_page=N`,
   but nothing in `frontend/` is affected: `ProteinPage.vue` calls
   `fetchProtein(id)` with no `ppiPage` argument, so `ppi_page` is never sent
   today (confirmed via `frontend/src/composables/useProtein.js` and
   `frontend/src/pages/ProteinPage.vue`) — the rendered Interactions tab uses
   `GET /protein/{id}/ppi` (`get_ppi_all`/`PpiPartner`) exclusively, which was
   already correctly aggregated.
2. **Finding 2 (`get_ppi_all`)**: when `mlo` is given, `role` is now checked
   against an `EXISTS` scoped to that MLO (`LOWER(ma.unified_role) = 'driver'`
   for `role=driver`, `policy.component_role_clause('ma')` for
   `role=component`, both `AND policy.active_annotation_clause('ma')`) instead
   of ANDing the global `protein_summary.has_driver` flag with a
   role-oblivious `mlo` existence check. `role` with no `mlo`, and `mlo` with
   no `role`, are unchanged — only the combination was wrong. Mirrors
   `_scoped_role_counts`'s existing per-MLO driver check in the same file.
3. **Finding 3**: `routers/proteins.py`'s `get_protein_ppi` now validates
   `role` against `_VALID_PPI_ROLES = {"driver", "component"}` (the same
   two-bucket vocabulary this endpoint's `protein_summary.has_driver`-derived
   filter already implements — see api/CLAUDE.md's `by_role` vocabulary
   table, row 3) and raises `422 invalid_parameter` for anything else,
   instead of silently adding no filter.
4. **Tests**: none of the three had any prior coverage — `api/tests/conftest.py`'s
   shared fixture carries no `ppi` rows at all. Added
   `api/tests/conftest_ppi.py` (a purpose-built `ppi_db` fixture, kept apart
   from the shared fixture for the same reason `conftest_search.py` is: the
   shared one is tuned to exact global counts asserted by `/stats`/facets/export
   tests, and a new protein there would shift those for unrelated reasons) and
   `api/tests/test_ppi.py` (9 tests covering all three findings, at both the
   query-function and the router/HTTP level).

## Verification

Expected: all three symptoms from the Evidence sections above stop reproducing
against the live `database/mlosmetadb.db` (local `uvicorn`, post-fix).

```
# Finding 1 -- P0DTD1/Q9Y6K9, called directly against the live DB
get_ppi_page('P0DTD1', page=1, per_page=10000) → Q9Y6K9 row:
  experimental_systems: Biochemical Activity,Co-crystal Structure,Affinity Capture-Western,Reconstituted Complex,Affinity Capture-MS
  pubmed_ids: 36075915,35856559,38514841,39400381
  evidence_count: 5
(was: a single arbitrary evidence_type/pubmed_id, e.g. "Biochemical Activity"/36075915 alone)

# Finding 2
GET /protein/P04050/ppi?role=driver&mlo=transcriptional_condensate
  → total 2, P35189 absent (was: total 3, P35189 present with has_driver=true)

# Finding 3
GET /protein/P04050/ppi?role=regulator
  → 422 invalid_parameter: "role must be one of: component, driver"
  (was: 200, full 72-partner list, identical to no role filter at all)
```

Full suite: 131 passed in `tests/`, 138 passed in `api/tests/` (was 123 before
this fix's 9 new tests, plus the 6 from docs/issues/002 landing the same day).
