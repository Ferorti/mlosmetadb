# MLOsMetaDB Update

## Project goal

Regenerate the MLOsMetaDB unified dataset from 5 source databases.
Each source is parsed independently into a common intermediate schema,
then merged and mapped to unified MLO and role vocabularies.

The mapping step (mlo_mapping.tsv, role_mapping.tsv) is a later stage.
In this session: implement and run the 5 parsers only.

## Directory structure

```
mlosmetadb_update/
├── database/
│   ├── raw/          # source files — never modify
│   ├── interim/      # one TSV per parser output
│   ├── mappings/
│   │   ├── mlo_mapping.tsv
│   │   └── role_mapping.tsv
│   └── schemas/
│       └── intermediate.py
├── parsers/
│   ├── parse_phasedb.py
│   ├── parse_drllps.py
│   ├── parse_llpsdb.py
│   ├── parse_phasepro.py
│   └── parse_cdcode.py
├── integrate.py
└── CLAUDE.md
```

## Source files (data/raw/)

| Filename | Database | Used by |
|---|---|---|
| phasedb_mlo_entries.csv | PhaseDB | parse_phasedb.py |
| phasedb_detail.csv | PhaseDB | parse_phasedb.py |
| drllps_llps.tsv | DrLLPS | parse_drllps.py |
| llpsdb_entries.csv | LLPSDB | parse_llpsdb.py |
| llpsdb_proteins.csv | LLPSDB | parse_llpsdb.py |
| phasepro.tsv | PhasePro | parse_phasepro.py |
| cdcode_proteins.csv | CDCODE | (reference only, not parsed) |
| cdcode_protein2condensate.tsv | CDCODE | parse_cdcode.py |
| cdcode_condensates.csv | CDCODE | (reference only) |
| cdcode_cmods.csv | CDCODE | (not used) |

## Intermediate schema

See schemas/intermediate.py for the canonical definition.

Output columns (every parser must produce exactly these):

| column | type | notes |
|---|---|---|
| uniprot_id | str | required — drop rows where missing or empty |
| source_db | str | fixed string per parser |
| source_mlo | str | raw name from source — drop rows where missing or empty |
| source_role | str | raw value from source, or "NULL" where not available |
| evidence | str | PMID(s), semicolon-separated if multiple, or "NULL" |
| organism | str | species name if available, or "NULL" |

## General rules

- Never modify files in data/raw/
- One row per (uniprot_id, source_db, source_mlo) combination
- If a source field contains a list of MLOs, explode into multiple rows (one per MLO)
- If a source field contains a list of PMIDs, keep as semicolon-separated string
- **Drop rows only when uniprot_id is missing or empty** — these cannot be linked to proteins. Log count and reason.
- **Never drop rows due to missing MLO or role.** Use `"NotInformed"` as the value when source_mlo or source_role is empty/null.
- **Never discard MLO tokens because they look generic** (e.g. "Others", "other", "Unknown", "Droplet", etc.). Keep the raw token from the source database as-is. Only the `"Others"` → drop rule in DrLLPS is removed; all tokens are now preserved.
- Strip whitespace from all fields
- Output files go to data/interim/{source_db_lowercase}.tsv

## Parser specifications

### parse_phasedb.py

Two input files, both produce source_db = "PhaseDB".
Concatenate outputs before writing to data/interim/phasedb.tsv.

**phasedb_mlo_entries.csv** (TSV, has header):
```
id  psid  pmid  organism  organism_common_name  protein_name
primary_name  gene_names  cell_line  name  uniprot_id  mlo  mlo_normalized
```
- uniprot_id → uniprot_id
- mlo_normalized → source_mlo
- pmid → evidence
- organism → organism
- source_role = "client" (fixed for all rows in this file)
- Drop rows where mlo_normalized is empty or whitespace

**phasedb_detail.csv** (CSV, has header):
```
Gene Name, UniProt ID, Organism, MLO, Material State, Class, Location,
PubMed ID, MLO Association Summary, PS Behavior Summary, Key Regions,
Experiment Types, Material Properties, Material State Transition,
Key Supporting Statements
```
- UniProt ID → uniprot_id
- MLO → source_mlo
- PubMed ID → evidence
- Organism → organism
- source_role = "driver" (fixed — applies to both PS-self and PS-other)
- Drop rows where MLO is empty or whitespace

---

### parse_drllps.py

Input: drllps_llps.tsv (TSV, has header)
```
DrLLPS ID  UniProt ID  Gene name  Ensembl Gene ID  Species
Condensate  LLPS Type  References  Protein Sequence
```
- UniProt ID → uniprot_id
- Condensate: split on ", " → explode into one row per MLO → source_mlo
  - If a token equals "Droplet" → source_mlo = "in vitro droplet"
  - If a token equals "Others" → drop that row
- LLPS Type → source_role
- References → evidence (normalize separators to ";")
- Species → organism
- Discard Protein Sequence column
- source_db = "DrLLPS"
- Output: data/interim/drllps.tsv

---

### parse_llpsdb.py

Input files: llpsdb_entries.csv, llpsdb_proteins.csv (both CSV, have headers)

**llpsdb_entries.csv** relevant columns:
- PSID: join key to group experiments per protein
- Protein ID (format "p0001"): join key to llpsdb_proteins.csv
- PMID → evidence

**llpsdb_proteins.csv** relevant columns:
- First column (internal protein ID, format "p0001"): join key
- UniProt accession column → uniprot_id
- Species column → organism

Steps:
1. Verify join key format between the two files before joining
2. Join on internal protein ID
3. Deduplicate by (uniprot_id) — keep one row per unique uniprot_id,
   collect all PMIDs as semicolon-separated string
4. source_mlo = "in vitro droplet" (fixed)
5. source_role = "driver" (fixed)
6. source_db = "LLPSDB"
7. Output: data/interim/llpsdb.tsv

---

### parse_phasepro.py

Input: phasepro.tsv (TSV, no header — use positional columns, 0-indexed)

Verify column positions by printing first 2 rows with indices before parsing.
Expected positions (confirm before using):
- col[2]: uniprot_id
- col[3]: organism
- col[10]: pmid → evidence
- col[14]: mlo (may be semicolon-separated list → explode into one row per MLO)

Rules:
- Split col[14] on "; " → explode into multiple rows → source_mlo
- Drop rows where col[14] is empty or whitespace-only
- source_role = "driver" (fixed)
- source_db = "PhasePro"
- Output: data/interim/phasepro.tsv

---

### parse_cdcode.py

Input: cdcode_protein2condensate.tsv (TSV, has header)
```
uniprotkb_ac  condensate_id  condensate_name
```
- uniprotkb_ac → uniprot_id
- condensate_name → source_mlo
- source_role = "NULL"
- evidence = "NULL"
- organism = "NULL"
- source_db = "CDCODE"
- Output: data/interim/cdcode.tsv

---

## After parsers complete

Run this to inspect unique values for the mapping stage:

```bash
python extract_unique_values.py
```

This script (to be created) should print:
- Unique source_mlo values per source_db
- Unique source_role values per source_db
- Row counts per source_db
- Rows dropped per parser and reason
