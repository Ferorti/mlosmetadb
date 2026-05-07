#!/usr/bin/env python3
"""
parse_orthologs.py — parsea archivos OrthoDB → tabla orthologs en mlosmetadb.db

Archivos requeridos en database/crossref/:
  odb12v2_genes.tab.gz        gene_id | taxon_id | protein_id | uniprot | ...
  odb12v2_OGs.tab.gz          og_id | level_taxid | og_name | ...
  odb12v2_OG2genes.tab.gz     og_id | gene_id
  odb12v2_gene_xrefs.tab.gz   gene_id | xref_id | xref_type   (auxiliar, ya disponible)
  odb12v2_species.tab.gz      taxon_id | taxon_code | name | assembly

Descargar desde: https://v12.orthodb.org/download/
  odb12v2_genes.tab.gz
  odb12v2_OGs.tab.gz
  odb12v2_OG2genes.tab.gz
"""

import gzip
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CROSSREF = ROOT / "database" / "crossref"

GENES_FILE    = CROSSREF / "odb12v2_genes.tab.gz"
OGS_FILE      = CROSSREF / "odb12v2_OGs.tab.gz"
OG2GENES_FILE = CROSSREF / "odb12v2_OG2genes.tab.gz"
SPECIES_FILE  = CROSSREF / "odb12v2_species.tab.gz"
XREFS_FILE    = CROSSREF / "odb12v2_gene_xrefs.tab.gz"

TARGET_TAXONS = {
    9606:  "Homo sapiens",
    10090: "Mus musculus",
    7955:  "Danio rerio",
    7227:  "Drosophila melanogaster",
    6239:  "Caenorhabditis elegans",
    4932:  "Saccharomyces cerevisiae",
    3702:  "Arabidopsis thaliana",
    44689: "Dictyostelium discoideum",
    83333: "Escherichia coli K-12",
}

TEST_PROTEINS = {"P35637", "Q92520", "P09651", "P38919", "Q9NQC3"}


def check_required_files() -> bool:
    missing = []
    for f in [GENES_FILE, OGS_FILE, OG2GENES_FILE]:
        if not f.exists():
            missing.append(f.name)
    if missing:
        print("ERROR: faltan archivos requeridos de OrthoDB v12:")
        for m in missing:
            print(f"  ✗ database/crossref/{m}")
        print()
        print("Descargar desde https://v12.orthodb.org/download/")
        print("Archivos necesarios:")
        print("  odb12v2_genes.tab.gz      — gene_id, taxon_id, protein_id, UniProt accession")
        print("  odb12v2_OGs.tab.gz        — ortholog group definitions")
        print("  odb12v2_OG2genes.tab.gz   — OG → gene_id mappings")
        return False
    return True


def inspect_files() -> None:
    """Imprime las primeras 3 líneas de cada archivo para verificar estructura."""
    files = {
        "genes":    GENES_FILE,
        "OGs":      OGS_FILE,
        "OG2genes": OG2GENES_FILE,
        "species":  SPECIES_FILE,
        "xrefs":    XREFS_FILE,
    }
    for name, path in files.items():
        print(f"\n=== {path.name} ===")
        if not path.exists():
            print("  (archivo no disponible)")
            continue
        with gzip.open(path, "rt") as f:
            for i, line in enumerate(f):
                print(f"  {line.rstrip()[:120]}")
                if i >= 2:
                    break


def create_tables(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS orthologs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            uniprot_id      TEXT NOT NULL REFERENCES proteins(uniprot_id),
            ortholog_id     TEXT NOT NULL,
            organism        TEXT NOT NULL,
            taxon_id        INTEGER NOT NULL,
            og_id           TEXT,
            in_db           INTEGER NOT NULL DEFAULT 0,
            source          TEXT DEFAULT 'OrthoDB',
            source_version  TEXT DEFAULT 'odb12v2'
        );
        CREATE INDEX IF NOT EXISTS idx_orth_uniprot ON orthologs(uniprot_id);
        CREATE INDEX IF NOT EXISTS idx_orth_indb    ON orthologs(in_db);
        CREATE INDEX IF NOT EXISTS idx_orth_taxon   ON orthologs(taxon_id);
    """)
    con.commit()


def load_species(species_file: Path) -> tuple[dict, dict]:
    """Devuelve (taxon_code → taxon_id, taxon_code → species_name)."""
    code_to_taxid: dict[str, int] = {}
    code_to_name: dict[str, str] = {}
    with gzip.open(species_file, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 3:
                continue
            try:
                taxid = int(cols[0])
            except ValueError:
                continue
            code = cols[1]
            name = cols[2]
            code_to_taxid[code] = taxid
            code_to_name[code] = name
    return code_to_taxid, code_to_name


def load_genes(
    genes_file: Path,
    db_proteins: set[str],
    code_to_taxid: dict[str, int],
) -> tuple[dict, dict, dict]:
    """
    Parsea genes.tab — sin header, 11 columnas:
      0: gene_id   1: taxon_code   2: ncbi_protein_acc   3: gene_symbol
      4: uniprot_accession   5-10: otros campos

    Devuelve:
      uniprot_to_gene  — uniprot → gene_id  (solo genes relevantes)
      gene_to_taxon    — gene_id → taxon_id
      gene_to_uniprot  — gene_id → uniprot
    """
    uniprot_to_gene: dict[str, str] = {}
    gene_to_taxon: dict[str, int] = {}
    gene_to_uniprot: dict[str, str] = {}

    target_codes = {
        code for code, tid in code_to_taxid.items() if tid in TARGET_TAXONS
    }

    with gzip.open(genes_file, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 5:
                continue
            gene_id   = cols[0]
            tax_code  = cols[1]
            uniprot   = cols[4].strip()

            if not uniprot:
                continue

            taxid = code_to_taxid.get(tax_code)
            if taxid is None:
                continue

            gene_to_taxon[gene_id]   = taxid
            gene_to_uniprot[gene_id] = uniprot

            if taxid in TARGET_TAXONS or uniprot in db_proteins:
                uniprot_to_gene[uniprot] = gene_id

    return uniprot_to_gene, gene_to_taxon, gene_to_uniprot


def load_og2genes(og2genes_file: Path) -> tuple[dict, dict]:
    """
    Devuelve (gene_to_og, og_to_genes).
    """
    gene_to_og: dict[str, str] = {}
    og_to_genes: dict[str, list] = defaultdict(list)

    with gzip.open(og2genes_file, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 2:
                continue
            og_id, gene_id = cols[0], cols[1]
            gene_to_og[gene_id] = og_id
            og_to_genes[og_id].append(gene_id)

    return gene_to_og, og_to_genes


def build_orthologs(
    db_proteins: set[str],
    uniprot_to_gene: dict,
    gene_to_og: dict,
    og_to_genes: dict,
    gene_to_taxon: dict,
    gene_to_uniprot: dict,
    filter_to: set[str] | None = None,
) -> list[tuple]:
    rows = []
    proteins_to_process = filter_to if filter_to else db_proteins

    for uniprot_id in proteins_to_process:
        gene_id = uniprot_to_gene.get(uniprot_id)
        if not gene_id:
            continue

        og_id = gene_to_og.get(gene_id)
        if not og_id:
            continue

        for member_gene_id in og_to_genes.get(og_id, []):
            member_taxon  = gene_to_taxon.get(member_gene_id)
            member_uniprot = gene_to_uniprot.get(member_gene_id)

            if not member_taxon or member_taxon not in TARGET_TAXONS:
                continue
            if not member_uniprot or member_uniprot == uniprot_id:
                continue

            in_db = 1 if member_uniprot in db_proteins else 0
            rows.append((
                uniprot_id,
                member_uniprot,
                TARGET_TAXONS[member_taxon],
                member_taxon,
                og_id,
                in_db,
            ))

    return rows


def print_test_results(rows: list[tuple]) -> None:
    from collections import defaultdict
    by_uid: dict = defaultdict(list)
    for r in rows:
        by_uid[r[0]].append(r)

    print("\n=== TEST RESULTS ===")
    for uid in sorted(TEST_PROTEINS):
        results = by_uid.get(uid, [])
        by_org: dict = defaultdict(list)
        for r in results:
            by_org[r[2]].append(r[1])
        print(f"\n  {uid}: {len(results)} ortólogos")
        for org, ids in sorted(by_org.items()):
            in_db_flag = " (in_db=1)" if any(
                r[5] == 1 for r in results if r[2] == org
            ) else ""
            print(f"    {org}: {', '.join(ids[:3])}{in_db_flag}")


def main() -> None:
    print("=== Verificando estructura de archivos ===")
    inspect_files()

    if not check_required_files():
        sys.exit(1)

    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    create_tables(con)

    db_proteins = {r[0] for r in con.execute("SELECT uniprot_id FROM proteins")}
    print(f"\nProteínas en DB: {len(db_proteins)}")

    already_done = {r[0] for r in con.execute("SELECT DISTINCT uniprot_id FROM orthologs")}
    if already_done:
        print(f"Ya procesadas: {len(already_done)} — modo append")

    print("\nCargando species ...")
    code_to_taxid, code_to_name = load_species(SPECIES_FILE)

    print("Cargando genes ...")
    uniprot_to_gene, gene_to_taxon, gene_to_uniprot = load_genes(
        GENES_FILE, db_proteins, code_to_taxid
    )
    print(f"  genes con UniProt: {len(gene_to_uniprot):,}")
    print(f"  genes relevantes (dataset + target taxons): {len(uniprot_to_gene):,}")

    print("Cargando OG2genes ...")
    gene_to_og, og_to_genes = load_og2genes(OG2GENES_FILE)
    print(f"  genes con OG: {len(gene_to_og):,}")
    print(f"  grupos OG totales: {len(og_to_genes):,}")

    # ── TEST ──────────────────────────────────────────────────────────────
    print("\n--- Test con TEST_PROTEINS ---")
    test_rows = build_orthologs(
        db_proteins, uniprot_to_gene, gene_to_og, og_to_genes,
        gene_to_taxon, gene_to_uniprot, filter_to=TEST_PROTEINS,
    )
    print_test_results(test_rows)

    fus_mouse = any(r[0] == "P35637" and r[3] == 10090 for r in test_rows)
    print(f"\n  Test FUS ortólogo en ratón: {'PASS ✓' if fus_mouse else 'WARN — Q60900 no encontrado'}")

    if not test_rows:
        print("No se encontraron ortólogos para proteínas de test. Revisar columnas de genes.tab.")
        con.close()
        sys.exit(1)

    # ── PIPELINE COMPLETO ─────────────────────────────────────────────────
    print("\n--- Pipeline completo ---")
    all_rows = build_orthologs(
        db_proteins, uniprot_to_gene, gene_to_og, og_to_genes,
        gene_to_taxon, gene_to_uniprot, filter_to=None,
    )

    # Idempotencia
    existing = {
        (r[0], r[1], r[3])
        for r in con.execute("SELECT uniprot_id, ortholog_id, taxon_id FROM orthologs")
    }
    new_rows = [r for r in all_rows if (r[0], r[1], r[3]) not in existing]

    if new_rows:
        con.executemany(
            "INSERT INTO orthologs (uniprot_id, ortholog_id, organism, taxon_id, og_id, in_db) "
            "VALUES (?,?,?,?,?,?)",
            new_rows,
        )
        con.commit()

    total   = len(all_rows)
    in_db_1 = sum(1 for r in all_rows if r[5] == 1)
    n_with_gene = sum(1 for uid in db_proteins if uid in uniprot_to_gene)
    n_with_og   = sum(1 for uid in db_proteins
                      if uid in uniprot_to_gene
                      and gene_to_og.get(uniprot_to_gene[uid]))
    n_no_orth   = sum(1 for uid in db_proteins
                      if uid in uniprot_to_gene
                      and gene_to_og.get(uniprot_to_gene[uid])
                      and not any(r[0] == uid for r in all_rows))

    print()
    print("=== Reporte final parse_orthologs ===")
    print(f"Proteínas en dataset:          {len(db_proteins):>8,}")
    print(f"Con gene_id en OrthoDB:        {n_with_gene:>8,}")
    print(f"Con og_id asignado:            {n_with_og:>8,}")
    print(f"Sin ortólogo en ningún taxon:  {n_no_orth:>8,}")
    print(f"Filas insertadas:              {total:>8,}")
    print(f"  - con in_db = 1:             {in_db_1:>8,}")
    print("\nPor organismo:")
    for taxon_id, name in sorted(TARGET_TAXONS.items(), key=lambda x: x[1]):
        n = sum(1 for r in all_rows if r[3] == taxon_id)
        print(f"  {name:35s} {n:>8,}")

    con.close()


if __name__ == "__main__":
    main()
