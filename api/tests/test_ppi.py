import asyncio

from fastapi.testclient import TestClient

from main import app
from queries.protein_queries import get_ppi_all, get_ppi_page, get_ppi_summary
from tests.conftest_ppi import ppi_db  # noqa: F401  (pytest fixture)

# docs/issues/003-ppi-endpoint-role-and-evidence-bugs.md -- three bugs in the
# PPI query path, all previously untested:
#   1. get_ppi_page's bare GROUP BY silently collapsed multi-evidence partners
#      to one arbitrary evidence row.
#   2. role=driver&mlo=X checked the partner's GLOBAL driver flag, not
#      driver-of-X, so a partner driving a different MLO was mislabeled.
#   3. role values other than driver/component were silently ignored instead
#      of rejected, on GET /protein/{id}/ppi.
#
# docs/issues/004-ppi-self-interaction-and-regulator-role.md -- two more,
# found while fixing a report about the interaction graph:
#   4. A protein's own self-interaction row (uniprot_id_a = uniprot_id_b,
#      e.g. P04637/p53 homodimerizing) was never excluded, so it showed up as
#      its own "partner" -- the graph's center node duplicated elsewhere in
#      the same network.
#   5. role="regulator" is now accepted (mirrors /proteins?role=regulator's
#      mutually-exclusive "regulator, never a driver" bucket), and every
#      returned partner now carries has_regulator.


# ---------------------------------------------------------------------------
# Finding 1: get_ppi_page must aggregate, not arbitrarily pick one row
# ---------------------------------------------------------------------------

def test_get_ppi_page_aggregates_all_evidence_for_a_multi_evidence_partner(ppi_db):
    total, rows = asyncio.run(get_ppi_page("P35637", page=1, per_page=10))
    by_partner = {r["partner_uniprot_id"]: r for r in rows}

    assert total == 4  # PCLIENT, PSCOPED, PREG01, PREV01 -- P35637's own self-interaction is excluded
    pclient = by_partner["PCLIENT"]
    assert set(pclient["experimental_systems"].split(",")) == {"Affinity Capture-MS", "Two-hybrid"}
    assert set(pclient["pubmed_ids"].split(",")) == {"11111111", "22222222"}
    assert pclient["evidence_count"] == 2


def test_get_ppi_page_single_evidence_partner_is_unaffected(ppi_db):
    _, rows = asyncio.run(get_ppi_page("P35637", page=1, per_page=10))
    pscoped = next(r for r in rows if r["partner_uniprot_id"] == "PSCOPED")
    assert pscoped["experimental_systems"] == "Affinity Capture-MS"
    assert pscoped["pubmed_ids"] == "33333333"
    assert pscoped["evidence_count"] == 1


def test_protein_detail_ppi_page_surfaces_every_evidence_type_and_pmid(ppi_db):
    """End-to-end through GET /protein/{id}?ppi_page=N and PpiInteractionItem
    -- the shape an API consumer actually receives."""
    with TestClient(app) as client:
        r = client.get("/protein/P35637", params={"ppi_page": 1, "ppi_per_page": 10})
    assert r.status_code == 200
    items = {i["partner_uniprot_id"]: i for i in r.json()["ppi"]["interactions"]["items"]}
    pclient = items["PCLIENT"]
    assert set(pclient["evidence_types"]) == {"Affinity Capture-MS", "Two-hybrid"}
    assert set(pclient["pubmed_ids"]) == {"11111111", "22222222"}
    assert pclient["evidence_count"] == 2


# ---------------------------------------------------------------------------
# Finding 2: role=driver&mlo=X must check driver-of-X, not "drives something
# AND has any annotation in X"
# ---------------------------------------------------------------------------

def test_get_ppi_all_role_driver_without_mlo_uses_the_global_flag(ppi_db):
    """Documented, correct existing behaviour: with no mlo scope, role=driver
    means "drives anything" -- PSCOPED qualifies (has_driver=1)."""
    total, rows = asyncio.run(get_ppi_all("P35637", role="driver", mlo=None, limit=500))
    assert {r["partner_uniprot_id"] for r in rows} == {"PSCOPED"}
    assert total == 1


def test_get_ppi_all_role_driver_scoped_to_a_mlo_the_partner_does_not_drive_excludes_it(ppi_db):
    """PSCOPED drives stress_granule, not p_granule -- it has only a client
    annotation there. Before the fix this returned PSCOPED anyway (global
    has_driver=1 AND *any* annotation in p_granule, ANDed independently)."""
    total, rows = asyncio.run(get_ppi_all("P35637", role="driver", mlo="p_granule", limit=500))
    assert rows == []
    assert total == 0


def test_get_ppi_all_role_driver_scoped_to_the_mlo_the_partner_does_drive_includes_it(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role="driver", mlo="stress_granule", limit=500))
    assert {r["partner_uniprot_id"] for r in rows} == {"PSCOPED"}
    assert total == 1


def test_get_ppi_all_mlo_alone_still_matches_any_role_in_that_mlo(ppi_db):
    """Unscoped-by-role behaviour is unchanged: mlo alone means "has any
    annotation there", regardless of role -- PCLIENT (client of p_granule)
    and PSCOPED (client of p_granule too) both qualify."""
    total, rows = asyncio.run(get_ppi_all("P35637", role=None, mlo="p_granule", limit=500))
    assert {r["partner_uniprot_id"] for r in rows} == {"PCLIENT", "PSCOPED"}
    assert total == 2


# ---------------------------------------------------------------------------
# Finding 3: an unrecognized role must be rejected, not silently ignored
# ---------------------------------------------------------------------------

def test_protein_ppi_endpoint_accepts_driver_component_and_regulator(ppi_db):
    with TestClient(app) as client:
        driver     = client.get("/protein/P35637/ppi", params={"role": "driver"})
        component  = client.get("/protein/P35637/ppi", params={"role": "component"})
        regulator  = client.get("/protein/P35637/ppi", params={"role": "regulator"})
    assert driver.status_code == component.status_code == regulator.status_code == 200


def test_protein_ppi_endpoint_rejects_an_unrecognized_role_instead_of_ignoring_it(ppi_db):
    with TestClient(app) as client:
        unfiltered = client.get("/protein/P35637/ppi")
        bogus = client.get("/protein/P35637/ppi", params={"role": "banana"})
    assert unfiltered.status_code == 200
    assert bogus.status_code == 422
    assert bogus.json()["error"] == "invalid_parameter"


# ---------------------------------------------------------------------------
# Finding 4: a protein's own self-interaction must never appear as a partner
# ---------------------------------------------------------------------------

def test_get_ppi_summary_excludes_the_hubs_own_self_interaction(ppi_db):
    summary = asyncio.run(get_ppi_summary("P35637"))
    # 4 real partners (PCLIENT, PSCOPED, PREG01, PREV01), not 5 -- the
    # fixture's P35637<->P35637 row must not count itself as a partner.
    assert summary["total_partners"] == 4
    assert summary["partners_in_mlosmetadb"] == 4


def test_get_ppi_all_never_returns_the_hub_as_its_own_partner(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role=None, mlo=None, limit=500))
    assert "P35637" not in {r["partner_uniprot_id"] for r in rows}
    assert total == 4


def test_get_ppi_page_never_returns_the_hub_as_its_own_partner(ppi_db):
    total, rows = asyncio.run(get_ppi_page("P35637", page=1, per_page=10))
    assert "P35637" not in {r["partner_uniprot_id"] for r in rows}
    assert total == 4


# ---------------------------------------------------------------------------
# Finding 5: role="regulator" -- the mutually-exclusive "regulator, never a
# driver" bucket, mirroring /proteins?role=regulator -- plus has_regulator
# on every returned partner
# ---------------------------------------------------------------------------

def test_get_ppi_all_has_regulator_flag_is_true_only_for_the_regulator_partner(ppi_db):
    _, rows = asyncio.run(get_ppi_all("P35637", role=None, mlo=None, limit=500))
    by_partner = {r["partner_uniprot_id"]: bool(r["has_regulator"]) for r in rows}
    assert by_partner == {"PCLIENT": False, "PSCOPED": False, "PREG01": True, "PREV01": False}


def test_get_ppi_all_role_regulator_matches_only_the_regulator_only_partner(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role="regulator", mlo=None, limit=500))
    assert {r["partner_uniprot_id"] for r in rows} == {"PREG01"}
    assert total == 1


def test_get_ppi_all_role_regulator_scoped_to_its_mlo_still_matches(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role="regulator", mlo="nucleolus", limit=500))
    assert {r["partner_uniprot_id"] for r in rows} == {"PREG01"}
    assert total == 1


def test_get_ppi_all_role_regulator_scoped_to_a_different_mlo_excludes_it(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role="regulator", mlo="p_granule", limit=500))
    assert rows == []
    assert total == 0


def test_protein_ppi_endpoint_role_regulator_end_to_end(ppi_db):
    with TestClient(app) as client:
        r = client.get("/protein/P35637/ppi", params={"role": "regulator"})
    assert r.status_code == 200
    body = r.json()
    assert {i["partner_uniprot_id"] for i in body["items"]} == {"PREG01"}
    assert body["items"][0]["has_regulator"] is True
    assert body["items"][0]["has_driver"] is False


# ---------------------------------------------------------------------------
# Finding 6: PPI partner queries anchored only to uniprot_id_a = hub missed
# interactions recorded with the hub in uniprot_id_b -- docs/issues/006.
#
# parse_biogrid.py (scripts/) only swaps the not-in-dataset interactor into
# uniprot_id_a; when BOTH sides of a pair are already in `proteins`,
# whichever BioGRID called "Interactor A" keeps that column. So a protein's
# own partner can legitimately be recorded with the protein itself in
# uniprot_id_b. Live-DB scale check: 795,987 of 847,051 distinct ordered
# pairs (94%) have no separate reverse row, so a query anchored only to
# uniprot_id_a systematically misses partners recorded the other way around
# -- not a rare edge case. Concrete live example: P04050 (RPO21) lists
# Q12149 (RRP6) as a partner, but Q12149's own /ppi never listed P04050
# back, because the only row is (P04050, Q12149).
# ---------------------------------------------------------------------------

def test_get_ppi_all_finds_a_partner_recorded_with_the_hub_in_uniprot_id_b(ppi_db):
    total, rows = asyncio.run(get_ppi_all("P35637", role=None, mlo=None, limit=500))
    assert "PREV01" in {r["partner_uniprot_id"] for r in rows}
    assert total == 4


def test_get_ppi_summary_counts_a_partner_recorded_with_the_hub_in_uniprot_id_b(ppi_db):
    summary = asyncio.run(get_ppi_summary("P35637"))
    assert summary["total_partners"] == 4
    assert summary["partners_in_mlosmetadb"] == 4


def test_get_ppi_page_finds_a_partner_recorded_with_the_hub_in_uniprot_id_b(ppi_db):
    total, rows = asyncio.run(get_ppi_page("P35637", page=1, per_page=10))
    assert "PREV01" in {r["partner_uniprot_id"] for r in rows}
    assert total == 4


def test_ppi_partner_correspondence_is_bidirectional(ppi_db):
    """If X's partner list includes Y, Y's partner list must include X --
    regardless which column BioGRID happened to store each protein in for
    that particular row. PREV01/P35637 is stored as a single row
    (PREV01, P35637); both directions of /ppi must agree it exists."""
    _, from_hub  = asyncio.run(get_ppi_all("P35637", role=None, mlo=None, limit=500))
    _, from_prev = asyncio.run(get_ppi_all("PREV01", role=None, mlo=None, limit=500))
    assert "PREV01" in {r["partner_uniprot_id"] for r in from_hub}
    assert "P35637" in {r["partner_uniprot_id"] for r in from_prev}


def test_protein_ppi_endpoint_finds_a_partner_recorded_with_the_hub_in_uniprot_id_b(ppi_db):
    with TestClient(app) as client:
        r = client.get("/protein/P35637/ppi")
    assert r.status_code == 200
    assert "PREV01" in {i["partner_uniprot_id"] for i in r.json()["items"]}
