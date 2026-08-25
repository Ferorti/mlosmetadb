# PPI partner queries anchored only to `uniprot_id_a` broke bidirectional correspondence

**Labels:** `bug`, `api`, `ppi`, `data-correctness`
**Severity:** high (silent data loss affecting most of the dataset, large
blast radius: the protein-page summary counts, the Interactions table, and
the D3 partner graph all inherit it).
**Status:** **resolved 2026-08-21.** Found during a general audit of the PPI
code path requested by the user ("controlar que ande bien todo lo relativo a
las PPIs... que haya correspondencia bidireccional").

---

## Summary

`get_ppi_summary`, `get_ppi_all` and `get_ppi_page`
(`api/queries/protein_queries.py`) all queried `ppi` with
`WHERE uniprot_id_a = ?`, treating the relationship as if a protein's
partners were only ever recorded with that protein in the `uniprot_id_a`
column. `ppi` does not guarantee that: each BioGRID record is stored as a
single directional row, and `scripts/parse_biogrid.py` only swaps the
*not-yet-in-dataset* interactor into `uniprot_id_a` — when **both**
interactors of a pair are already in `proteins`, whichever accession BioGRID
called "Interactor A" simply keeps that column. So a protein's own partner
can legitimately be recorded with that protein itself sitting in
`uniprot_id_b`, and every query anchored only to `uniprot_id_a` silently
missed it.

The result: protein A's partner table/graph would list B, but B's own
partner table/graph would not list A back — the exact "correspondencia
bidireccional" check requested.

## Root cause

`ppi` has no reverse row for most pairs: 94% of distinct ordered pairs in the
live DB (795,987 of 847,051) have no separate `(b, a)` row alongside their
`(a, b)` row. The `get_ppi_*` functions never accounted for this — each
queried only the `uniprot_id_a` side of the relationship, implicitly
assuming the reverse row would exist if the interaction mattered from the
other protein's perspective. It doesn't.

## Evidence

Concrete pair, both in-dataset: **P04050** (RPO21, RNA Pol II largest
subunit) and **Q12149** (RRP6). The only row in `ppi` for this pair is
`(P04050, Q12149)`:

```
GET /protein/P04050/ppi   -> Q12149 present as a partner        (correct, always was)
GET /protein/Q12149/ppi   -> P04050 absent from Q12149's list   (bug: not the same relationship, viewed from the other side)
```

Scale check against the live DB: expanding a protein's own partner query to
also match `uniprot_id_b = ?` (i.e. treating the relationship as symmetric)
raised Q12149's own partner count from 415 to 438 — 23 real partners that
were invisible from Q12149's own page, table and graph, purely because of
which column BioGRID happened to store them in.

## Failure scenario

Any protein that ends up in `uniprot_id_b` for one or more of its own
interactions (a majority of in-dataset pairs, per the 94% figure above) has
an under-counted `ppi.total_partners`/`partners_in_mlosmetadb`, an
incomplete partner table, and a graph missing nodes/edges for those
partners — while the *other* protein in each such pair sees the interaction
correctly. A user cross-checking two related proteins' Interactions tabs (as
requested) would see A's page list B, and B's page not list A: a visible,
reproducible correctness bug, not a cosmetic one.

## What was done

1. **`get_ppi_summary`, `get_ppi_all`, `get_ppi_page`** (all in
   `api/queries/protein_queries.py`) rewritten to match
   `(uniprot_id_a = ? OR uniprot_id_b = ?)` and compute the partner id as
   `CASE WHEN uniprot_id_a = ? THEN uniprot_id_b ELSE uniprot_id_a END`,
   instead of hardcoding `uniprot_id_b` as "the partner" and `uniprot_id_a`
   as "always the query protein".
2. **`in_db` (partner-in-`proteins`) is derived correctly for both
   directions**, without an extra lookup: the stored `in_db` column already
   means "is `uniprot_id_b` in `proteins`", which is exactly right when the
   query protein is found via `uniprot_id_a`. When the query protein is
   found via `uniprot_id_b` instead, the partner is `uniprot_id_a` — and
   `uniprot_id_a` is *always* in `proteins` by construction
   (`parse_biogrid.py`'s normalization guarantees the in-dataset interactor,
   if any, lands there), so that partner is unconditionally `in_db = 1`.
   Encoded as `CASE WHEN uniprot_id_a = ? THEN in_db ELSE 1 END`.
3. **`get_ppi_inter_edges`** (edges *between* two partners, excluding the
   hub) needed no change — it already matches `uniprot_id_a IN (...) AND
   uniprot_id_b IN (...)` against the partner-id list, which doesn't care
   which column either side landed in.
4. **Tests**: `api/tests/conftest_ppi.py` gained `PREV01`, an in-dataset
   partner recorded as `(PREV01, P35637)` — the hub in `uniprot_id_b`, not
   `uniprot_id_a`. `api/tests/test_ppi.py` gained a "Finding 6" section
   (6 tests) asserting `get_ppi_summary`/`get_ppi_all`/`get_ppi_page` and the
   `/protein/{id}/ppi` endpoint all find `PREV01`, plus an explicit
   bidirectional-correspondence test comparing `get_ppi_all("P35637")` and
   `get_ppi_all("PREV01")` against each other. All pre-existing partner-count
   assertions for the `P35637` hub were bumped from 3 to 4 to account for the
   new fixture partner.

## Verification

```
# Concrete live-DB pair, before this fix: only one direction worked.
GET /protein/P04050/ppi              -> Q12149 present            (unchanged, always correct)
GET /protein/Q12149/ppi              -> before: P04050 absent
                                         after:  P04050 present    <-- fixed
GET /protein/Q12149                  -> before: ppi.total_partners = 415
                                         after:  ppi.total_partners = 438,
                                                 partners_in_mlosmetadb = 170
```

Full suite: 131 passed in `tests/`, 158 passed in `api/tests/` (28 in
`api/tests/test_ppi.py`, up from 22 -- 6 new "Finding 6" tests, plus 4
pre-existing tests whose expected counts were updated for the new fixture
partner).
