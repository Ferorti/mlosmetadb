#!/usr/bin/env python3
"""
parse_orthologs.py — OrthoDB v12 → ortholog_groups + ortholog_members
"""

import gzip
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
DB       = ROOT / "database" / "mlosmetadb.db"
CROSSREF = ROOT / "database" / "crossref"

LEVELS_FILE   = CROSSREF / "odb12v2_levels.tab.gz"
OGS_FILE      = CROSSREF / "odb12v2_OGs.tab.gz"
GENES_FILE    = CROSSREF / "odb12v2_genes.tab.gz"
XREFS_FILE    = CROSSREF / "odb12v2_gene_xrefs.tab.gz"
OG2GENES_FILE = CROSSREF / "odb12v2_OG2genes.tab.gz"

TEST_PROTEINS = ["P35637", "Q92520", "P09651", "P38919", "Q9NQC3"]


# ── Inspección de archivos ────────────────────────────────────────────────────

def inspect_files() -> None:
    files = [
        ("levels",   LEVELS_FILE),
        ("OGs",      OGS_FILE),
        ("genes",    GENES_FILE),
        ("xrefs",    XREFS_FILE),
        ("OG2genes", OG2GENES_FILE),
    ]
    for name, path in files:
        print(f"\n=== {path.name} ===")
        if not path.exists():
            print("  (archivo no encontrado)")
            continue
        with gzip.open(path, "rt") as f:
            for i, line in enumerate(f):
                print(f"  {line.rstrip()[:120]}")
                if i >= 2:
                    break


# ── Creación de tablas ────────────────────────────────────────────────────────

def create_tables(con: sqlite3.Connection) -> None:
    # Paso 0: backup de tabla orthologs OMA
    existing = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "orthologs" in existing and "orthologs_oma_backup" not in existing:
        print("Renombrando orthologs → orthologs_oma_backup ...")
        con.execute("ALTER TABLE orthologs RENAME TO orthologs_oma_backup")
        con.commit()

    con.executescript("""
        CREATE TABLE IF NOT EXISTS ortholog_groups (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            uniprot_id     TEXT NOT NULL REFERENCES proteins(uniprot_id),
            og_id          TEXT NOT NULL,
            og_name        TEXT,
            level_taxon_id INTEGER NOT NULL,
            level_name     TEXT,
            gene_count     INTEGER,
            is_default     INTEGER DEFAULT 0,
            UNIQUE(uniprot_id, og_id)
        );
        CREATE INDEX IF NOT EXISTS idx_og_uniprot ON ortholog_groups(uniprot_id);
        CREATE INDEX IF NOT EXISTS idx_og_ogid    ON ortholog_groups(og_id);

        CREATE TABLE IF NOT EXISTS ortholog_members (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            og_id      TEXT NOT NULL,
            uniprot_id TEXT NOT NULL,
            organism   TEXT,
            taxon_id   INTEGER,
            in_db      INTEGER DEFAULT 0,
            UNIQUE(og_id, uniprot_id)
        );
        CREATE INDEX IF NOT EXISTS idx_om_ogid ON ortholog_members(og_id);
        CREATE INDEX IF NOT EXISTS idx_om_indb ON ortholog_members(in_db);
    """)
    con.commit()


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_levels(path: Path) -> dict:
    """taxon_id (int) → level_name (str)"""
    levels: dict[int, str] = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 2:
                continue
            try:
                levels[int(cols[0])] = cols[1]
            except ValueError:
                continue
    return levels


def load_ogs(path: Path) -> dict:
    """og_id → {"taxon_id": int, "name": str}"""
    ogs: dict[str, dict] = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 3:
                continue
            try:
                taxon_id = int(cols[1])
            except ValueError:
                continue
            ogs[cols[0]] = {"taxon_id": taxon_id, "name": cols[2]}
    return ogs


def load_genes(path: Path) -> tuple[dict, dict]:
    """
    Parsea genes.tab: gene_id(col0), organism_id(col1), ..., uniprot(col4)
    Solo filas donde col4 no está vacía.

    Returns:
      gene_to_uniprot: gene_id → uniprot_id
      gene_to_taxon:   gene_id → taxon_id  (int del prefijo organism_id)
    """
    gene_to_uniprot: dict[str, str] = {}
    gene_to_taxon:   dict[str, int] = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 5:
                continue
            uniprot = cols[4].strip()
            if not uniprot:
                continue
            gene_id = cols[0]
            try:
                taxon_id = int(cols[1].split("_")[0])
            except (ValueError, IndexError):
                continue
            gene_to_uniprot[gene_id] = uniprot
            gene_to_taxon[gene_id]   = taxon_id
    return gene_to_uniprot, gene_to_taxon


def load_xrefs(path: Path) -> dict:
    """
    Parsea gene_xrefs.tab filtrando source == 'UniProt'.
    Returns uniprot_id → gene_id
    """
    uniprot_to_gene: dict[str, str] = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 3 or cols[2].strip() != "UniProt":
                continue
            xref = cols[1].strip()
            if xref:
                uniprot_to_gene[xref] = cols[0]
    return uniprot_to_gene


def load_og2genes(path: Path) -> tuple[dict, dict]:
    """
    Parsea OG2genes.tab: og_id(col0), gene_id(col1)
    Returns:
      og_to_genes:  og_id → [gene_ids]
      gene_to_ogs:  gene_id → [og_ids]
    """
    og_to_genes: dict[str, list] = defaultdict(list)
    gene_to_ogs: dict[str, list] = defaultdict(list)
    with gzip.open(path, "rt") as f:
        for line in f:
            cols = line.rstrip().split("\t")
            if len(cols) < 2:
                continue
            og_id, gene_id = cols[0], cols[1]
            og_to_genes[og_id].append(gene_id)
            gene_to_ogs[gene_id].append(og_id)
    return dict(og_to_genes), dict(gene_to_ogs)


# ── Lógica is_default ────────────────────────────────────────────────────────

def select_default_og(
    uid: str,
    og_ids: list,
    og_to_genes: dict,
    gene_to_uniprot: dict,
    db_proteins: set,
) -> str | None:
    """
    El OG default es el más específico (menor gene_count) con >=2
    miembros in_db distintos del propio uid.
    Si ninguno cumple, el más específico disponible.
    """
    if not og_ids:
        return None
    candidates = []
    for og_id in og_ids:
        members    = og_to_genes.get(og_id, [])
        gene_count = len(members)
        in_db_count = sum(
            1 for mg in members
            if gene_to_uniprot.get(mg, "") in db_proteins
            and gene_to_uniprot.get(mg) != uid
        )
        candidates.append((og_id, gene_count, in_db_count))
    candidates.sort(key=lambda x: x[1])  # más específico primero
    for og_id, _, in_db_count in candidates:
        if in_db_count >= 2:
            return og_id
    return candidates[0][0]  # fallback: más específico


# ── Test ──────────────────────────────────────────────────────────────────────

def run_test(
    db_proteins: set,
    uniprot_to_gene: dict,
    gene_to_ogs: dict,
    og_to_genes: dict,
    ogs: dict,
    levels: dict,
    gene_to_uniprot: dict,
    gene_to_taxon: dict,
) -> bool:
    print("\n" + "="*60)
    print("=== TEST con TEST_PROTEINS ===")
    print("="*60)

    for uid in TEST_PROTEINS:
        gene_id = uniprot_to_gene.get(uid)
        print(f"\n  {uid}:")
        print(f"    gene_id: {gene_id or '(no encontrado en OrthoDB)'}")
        if not gene_id:
            continue

        og_ids = gene_to_ogs.get(gene_id, [])
        if not og_ids:
            print("    OGs: (ninguno)")
            continue

        og_rows = []
        for og_id in og_ids:
            og_meta    = ogs.get(og_id, {})
            taxon_id   = og_meta.get("taxon_id", 0)
            level_name = levels.get(taxon_id, "Unknown")
            gene_count = len(og_to_genes.get(og_id, []))
            og_rows.append((og_id, level_name, gene_count))
        og_rows.sort(key=lambda x: x[2])

        default_og = select_default_og(uid, og_ids, og_to_genes, gene_to_uniprot, db_proteins)

        print(f"    OGs ({len(og_rows)}):")
        for og_id, level_name, gene_count in og_rows:
            flag = " ← DEFAULT" if og_id == default_og else ""
            print(f"      {og_id:28s}  {level_name:35s}  genes={gene_count:>6}{flag}")

        if default_og:
            members_indb = [
                (gene_to_uniprot[mg], gene_to_taxon.get(mg, 0))
                for mg in og_to_genes.get(default_og, [])
                if gene_to_uniprot.get(mg, "") in db_proteins
                and gene_to_uniprot.get(mg) != uid
            ]
            print(f"    Miembros in_db=1 del OG default (primeros 5):")
            for mu, mt in members_indb[:5]:
                org = levels.get(mt, str(mt))
                print(f"      {mu}  taxon={mt}  level={org}")

    # Sanity check: FUS debe tener ortólogo en ratón (taxon 10090) con in_db=1
    fus_gene = uniprot_to_gene.get("P35637")
    if not fus_gene:
        print("\n  FAIL: P35637 no encontrado en OrthoDB xrefs")
        return False

    fus_og_ids = gene_to_ogs.get(fus_gene, [])
    default_og = select_default_og("P35637", fus_og_ids, og_to_genes, gene_to_uniprot, db_proteins)

    has_mouse_default = any(
        gene_to_taxon.get(mg) == 10090
        and gene_to_uniprot.get(mg, "") in db_proteins
        for mg in og_to_genes.get(default_og or "", [])
    )
    has_mouse_any = any(
        gene_to_taxon.get(mg) == 10090
        and gene_to_uniprot.get(mg, "") in db_proteins
        for og in fus_og_ids
        for mg in og_to_genes.get(og, [])
    )

    print()
    if has_mouse_default:
        print("  PASS ✓ — P35637 tiene ortólogo en ratón (in_db=1) en OG default")
        return True
    elif has_mouse_any:
        print("  PASS ✓ — P35637 tiene ortólogo en ratón (in_db=1) en algún OG")
        return True
    else:
        print("  WARN — P35637 sin ortólogo en ratón con in_db=1 en ningún OG")
        return False


# ── Pipeline completo ─────────────────────────────────────────────────────────

def run_pipeline(
    con: sqlite3.Connection,
    db_proteins: set,
    uniprot_to_gene: dict,
    gene_to_ogs: dict,
    og_to_genes: dict,
    ogs: dict,
    levels: dict,
    gene_to_uniprot: dict,
    gene_to_taxon: dict,
) -> None:
    print("\n--- Pipeline completo ---")

    # Paso 7: ortholog_groups
    group_batch: list[tuple] = []
    ogs_to_process: set[str] = set()
    n_done = n_no_gene = n_no_og = 0

    for uniprot_id in db_proteins:
        gene_id = uniprot_to_gene.get(uniprot_id)
        if not gene_id:
            n_no_gene += 1
            continue

        og_ids = gene_to_ogs.get(gene_id, [])
        if not og_ids:
            n_no_og += 1
            continue

        for og_id in og_ids:
            og_meta    = ogs.get(og_id, {})
            taxon_id   = og_meta.get("taxon_id", 0)
            level_name = levels.get(taxon_id, "Unknown")
            gene_count = len(og_to_genes.get(og_id, []))
            group_batch.append((uniprot_id, og_id, og_meta.get("name"), taxon_id, level_name, gene_count))
            ogs_to_process.add(og_id)

        n_done += 1
        if n_done % 1000 == 0:
            print(f"  [{n_done}] proteínas procesadas ...")

    con.executemany(
        "INSERT OR IGNORE INTO ortholog_groups "
        "(uniprot_id, og_id, og_name, level_taxon_id, level_name, gene_count) "
        "VALUES (?,?,?,?,?,?)",
        group_batch,
    )
    con.commit()
    print(f"  ortholog_groups: {len(group_batch):,} filas insertadas")
    print(f"  Sin gene_id en OrthoDB: {n_no_gene:,}")
    print(f"  Con gene_id pero sin OG: {n_no_og:,}")

    # Paso 8: ortholog_members
    print(f"\nInsertando miembros para {len(ogs_to_process):,} OGs únicos ...")
    member_batch: list[tuple] = []
    n_members = 0

    for i, og_id in enumerate(ogs_to_process):
        for mg in og_to_genes.get(og_id, []):
            mu = gene_to_uniprot.get(mg)
            if not mu:
                continue
            taxon_id = gene_to_taxon.get(mg, 0)
            organism = levels.get(taxon_id, "Unknown")
            in_db    = 1 if mu in db_proteins else 0
            member_batch.append((og_id, mu, organism, taxon_id, in_db))

        if len(member_batch) >= 50000:
            con.executemany(
                "INSERT OR IGNORE INTO ortholog_members "
                "(og_id, uniprot_id, organism, taxon_id, in_db) VALUES (?,?,?,?,?)",
                member_batch,
            )
            con.commit()
            n_members += len(member_batch)
            member_batch.clear()

        if (i + 1) % 10000 == 0:
            print(f"  [{i+1:,}/{len(ogs_to_process):,}] OGs, {n_members:,} miembros ...")

    if member_batch:
        con.executemany(
            "INSERT OR IGNORE INTO ortholog_members "
            "(og_id, uniprot_id, organism, taxon_id, in_db) VALUES (?,?,?,?,?)",
            member_batch,
        )
        con.commit()
        n_members += len(member_batch)

    print(f"  ortholog_members: {n_members:,} filas insertadas")

    # Paso 9: is_default
    print("\nMarcando is_default ...")
    updates = []
    for uniprot_id in db_proteins:
        gene_id = uniprot_to_gene.get(uniprot_id)
        if not gene_id:
            continue
        og_ids = gene_to_ogs.get(gene_id, [])
        default_og = select_default_og(uniprot_id, og_ids, og_to_genes, gene_to_uniprot, db_proteins)
        if default_og:
            updates.append((uniprot_id, default_og))

    con.executemany(
        "UPDATE ortholog_groups SET is_default = 1 WHERE uniprot_id = ? AND og_id = ?",
        updates,
    )
    con.commit()
    print(f"  {len(updates):,} proteínas con OG default marcado")


# ── Verificación final ────────────────────────────────────────────────────────

def print_verification(con: sqlite3.Connection) -> None:
    print("\n" + "="*60)
    print("=== Verificación final ===")
    print("="*60)

    n = con.execute("SELECT COUNT(DISTINCT uniprot_id) FROM ortholog_groups").fetchone()[0]
    print(f"\nCobertura: {n:,} proteínas con al menos un OG")

    print("\nDistribución de niveles taxonómicos (top 20):")
    for row in con.execute("""
        SELECT level_name, COUNT(DISTINCT uniprot_id) AS proteinas
        FROM ortholog_groups
        GROUP BY level_name
        ORDER BY proteinas DESC
        LIMIT 20
    """):
        print(f"  {row[0]:45s}  {row[1]:>6,}")

    print("\nOGs de FUS (P35637):")
    for row in con.execute("""
        SELECT og.og_id, og.level_name, COUNT(*) AS total_members,
               SUM(om.in_db) AS in_db_members
        FROM ortholog_groups og
        JOIN ortholog_members om ON og.og_id = om.og_id
        WHERE og.uniprot_id = 'P35637'
        GROUP BY og.og_id, og.level_name
        ORDER BY in_db_members DESC
    """):
        print(f"  {row[0]:28s}  {row[1]:35s}  total={row[2]:>5}  in_db={row[3]}")

    print("\nSanity check — FUS ortólogo en ratón (taxon 10090) desde OG default:")
    rows = con.execute("""
        SELECT om.uniprot_id, om.organism, om.in_db
        FROM ortholog_groups og
        JOIN ortholog_members om ON og.og_id = om.og_id
        WHERE og.uniprot_id = 'P35637'
          AND og.is_default = 1
          AND om.taxon_id = 10090
    """).fetchall()
    if rows:
        for row in rows:
            print(f"  {row[0]}  organism_level={row[1]}  in_db={row[2]}")
    else:
        print("  (ninguno en OG default — revisar is_default)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== Verificando estructura de archivos ===")
    inspect_files()

    for f in [LEVELS_FILE, OGS_FILE, GENES_FILE, XREFS_FILE, OG2GENES_FILE]:
        if not f.exists():
            print(f"\nERROR: falta {f}")
            sys.exit(1)

    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    create_tables(con)

    # Paso 6
    db_proteins = {r[0] for r in con.execute("SELECT uniprot_id FROM proteins")}
    print(f"\nProteínas en DB: {len(db_proteins):,}")

    # Paso 1
    print("Cargando levels ...")
    levels = load_levels(LEVELS_FILE)
    print(f"  {len(levels):,} niveles")

    # Paso 2
    print("Cargando OGs ...")
    ogs = load_ogs(OGS_FILE)
    print(f"  {len(ogs):,} grupos OG")

    # Paso 3
    print("Cargando genes ...")
    gene_to_uniprot, gene_to_taxon = load_genes(GENES_FILE)
    print(f"  gene_to_uniprot: {len(gene_to_uniprot):,}")
    print(f"  gene_to_taxon:   {len(gene_to_taxon):,}")

    # Paso 4
    print("Cargando xrefs (UniProt) ...")
    uniprot_to_gene = load_xrefs(XREFS_FILE)
    # Complementar con genes.tab col4 para db_proteins no encontradas en xrefs
    for gene_id, upid in gene_to_uniprot.items():
        if upid in db_proteins and upid not in uniprot_to_gene:
            uniprot_to_gene[upid] = gene_id
    print(f"  uniprot_to_gene: {len(uniprot_to_gene):,}")

    # Paso 5
    print("Cargando OG2genes ...")
    og_to_genes, gene_to_ogs = load_og2genes(OG2GENES_FILE)
    print(f"  OGs únicos: {len(og_to_genes):,}")
    print(f"  genes con OG: {len(gene_to_ogs):,}")

    # ── TEST ──────────────────────────────────────────────────────────────────
    test_ok = run_test(
        db_proteins, uniprot_to_gene, gene_to_ogs, og_to_genes,
        ogs, levels, gene_to_uniprot, gene_to_taxon,
    )

    if not test_ok:
        print("\nTest fallido. Abortando pipeline completo.")
        con.close()
        sys.exit(1)

    # ── PIPELINE COMPLETO ─────────────────────────────────────────────────────
    run_pipeline(
        con, db_proteins, uniprot_to_gene, gene_to_ogs, og_to_genes,
        ogs, levels, gene_to_uniprot, gene_to_taxon,
    )

    print_verification(con)
    con.close()


if __name__ == "__main__":
    main()
