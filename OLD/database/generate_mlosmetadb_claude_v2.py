#!/usr/bin/env python3
"""
Generate MlosMetadb v2 dataset by consolidating updated source databases:
  - llpsdb   (llpsdb_proteins.csv, LLPS_entries.csv)
  - drllps   (LLPS.txt)
  - phasepdb (summary, detail, mlo_entries)
  - phasepro (download_full.json)
  - cdcode   (protein2cdcode_v2.2.tsv, proteins CSV)

For proteins already in v1: IDRs, LCRs, pfam_domains and llps_regions are
carried forward.  For new proteins: IDRs/LCRs come from llpsdb when available,
llps_regions come from phasepro boundaries; pfam_domains default to empty.
"""

import json
import re
import pandas as pd
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path('/biodata/forti/proyectos/mlos/mlosmetadb/database/databases_input_data')
OUT_DIR = Path('/biodata/forti/proyectos/mlos/mlosmetadb/database/databases_input_data/mlosmetadb_v2')
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# MLO normalization helper
# ---------------------------------------------------------------------------
_MLO_OVERRIDES = {
    'p granule':           'p_granule',
    'p-granule':           'p_granule',
    'p-body':              'p_body',
    'pbody':               'p_body',
    'pml nuclear body':    'pml_nuclear_body',
    'pml body':            'pml_nuclear_body',
    'cajal body':          'cajal_body',
    'stress granule':      'stress_granule',
    'nuclear speckle':     'nuclear_speckle',
    'nuclear speckles':    'nuclear_speckle',
    'postsynaptic density':'postsynaptic_density',
    'centrosome/spindle pole body': 'centrosome/spindle_pole_body',
    'germ plasm/polar granule':     'germ_plasm/polar_granule',
}

def normalize_mlo(raw: str) -> str:
    raw = str(raw).strip().rstrip('.')
    if not raw or raw.lower() in ('_', 'na', 'nan', 'none', '-', ''):
        return 'na'
    lower = raw.lower()
    if lower in _MLO_OVERRIDES:
        return _MLO_OVERRIDES[lower]
    # generic: lowercase, spaces→_, hyphens→_  (preserve /)
    normalized = re.sub(r'[ \t]+', '_', lower)
    normalized = re.sub(r'-', '_', normalized)
    normalized = re.sub(r'_+', '_', normalized)
    return normalized.strip('_')


def parse_mlos_field(raw: str) -> list[str]:
    """Split a comma- or semicolon-separated MLO string into normalized names."""
    if not raw or str(raw).strip().lower() in ('nan', '_', 'na', 'none'):
        return ['na']
    parts = re.split(r'[;,]', str(raw))
    result = [normalize_mlo(p) for p in parts if p.strip()]
    return result if result else ['na']


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------
DRLLPS_ROLE = {'Scaffold': 'driver', 'Client': 'client', 'Regulator': 'regulator'}
PHASEPDB_CLASS_ROLE = {'PS-self': 'driver', 'PS-other': 'client'}


def clean_idr_lcr(raw) -> str:
    """Normalise IDR/LCR strings; return '' for missing/zero values."""
    s = str(raw).strip()
    if s in ('nan', 'NaN', '', '0-0', '0'):
        return ''
    return s


def parse_phasepro_boundaries(raw: str, source: str) -> list[str]:
    """
    Parse a PhasePro boundaries field like '1-168' or '461-553; 606-694'
    into a list of 'start-end_source' strings.
    """
    if not raw or str(raw).strip().lower() in ('nan', 'none', '', 'n/a'):
        return []
    regions = []
    for part in re.split(r'[;,]', str(raw)):
        part = part.strip()
        m = re.search(r'(\d+)\s*[-–]\s*(\d+)', part)
        if m:
            regions.append(f'{m.group(1)}-{m.group(2)}_{source}')
    return regions


# ---------------------------------------------------------------------------
# Load all sources
# ---------------------------------------------------------------------------
print('Loading source databases...')

# v1 (carry-over for idrs/lcrs/pfam/llps_regions)
with open(BASE / 'mlosmetadb_v1' / 'mlosmetadb_dataset.json') as fh:
    v1_raw = json.load(fh)
v1 = v1_raw['entries']

# llpsdb
llpsdb_prot = pd.read_csv(BASE / 'llpsdb' / 'llpsdb_proteins.csv')
llpsdb_prot = llpsdb_prot[llpsdb_prot['Uniprot ID'].notna()]
llpsdb_prot = llpsdb_prot[~llpsdb_prot['Uniprot ID'].isin(['', 'nan'])]
llpsdb_by_acc = llpsdb_prot.set_index('Uniprot ID').to_dict('index')

# drllps
drllps = pd.read_csv(BASE / 'drllps' / 'LLPS.txt', sep='\t')
drllps = drllps[drllps['UniProt ID'].notna()]

# phasepdb
phasepdb_sum = pd.read_csv(BASE / 'phasepdb' / 'phasepdb_summary_database_2026-03-20.csv')
phasepdb_det = pd.read_csv(BASE / 'phasepdb' / 'phasepdb_detail_database_2026-03-20.csv')
phasepdb_mlo = pd.read_csv(BASE / 'phasepdb' / 'phasepdb_mlo_entries_from_script.tsv', sep='\t')
phasepdb_mlo = phasepdb_mlo[phasepdb_mlo['uniprot_id'].notna()]
phasepdb_mlo = phasepdb_mlo[phasepdb_mlo['uniprot_id'] != '_']

# phasepro
with open(BASE / 'phasepro' / 'download_full.json') as fh:
    phasepro = json.load(fh)

# cdcode
cdcode_p2c = pd.read_csv(BASE / 'cdcode' / 'protein2cdcode_v2.2.tsv', sep='\t')
cdcode_prot = pd.read_csv(BASE / 'cdcode' / 'proteins_202603181653.csv')
# Build acc → species_name map
cdcode_species = {}
for _, row in cdcode_prot.iterrows():
    acc = str(row.get('uniprot_id', '')).strip()
    sp  = str(row.get('species_name', '')).strip()
    if acc and acc not in ('nan', ''):
        cdcode_species[acc] = sp

print(f'  v1:       {len(v1):>7,} entries')
print(f'  llpsdb:   {len(llpsdb_prot):>7,} proteins')
print(f'  drllps:   {len(drllps):>7,} entries')
print(f'  phasepdb_summary: {len(phasepdb_sum):>5,}')
print(f'  phasepdb_detail:  {len(phasepdb_det):>5,}')
print(f'  phasepdb_mlo:     {len(phasepdb_mlo):>5,}')
print(f'  phasepro: {len(phasepro):>7,} entries')
print(f'  cdcode:   {len(cdcode_p2c):>7,} protein-condensate pairs')

# ---------------------------------------------------------------------------
# Accumulator per UniProt accession
# ---------------------------------------------------------------------------
acc_data: dict[str, dict] = defaultdict(lambda: {
    'organism': '',
    'databases': set(),
    'roles': set(),
    'mlos': set(),
    'mlos_entries': [],
    'idrs': '',
    'lcrs': '',
    'llps_regions': [],
    'pfam_domains': '',
})

def set_organism(acc: str, organism: str, priority: int):
    """Set organism only when it improves over existing (higher priority wins)."""
    d = acc_data[acc]
    if not d.get('_org_priority') or priority > d['_org_priority']:
        if organism and str(organism).strip().lower() not in ('nan', 'none', ''):
            d['organism'] = str(organism).strip()
            d['_org_priority'] = priority


# ---------------------------------------------------------------------------
# 1.  llpsdb  (role = driver for all curated LLPS proteins)
# ---------------------------------------------------------------------------
print('\nProcessing llpsdb...')
for _, row in llpsdb_prot.iterrows():
    acc = str(row['Uniprot ID']).strip()
    d = acc_data[acc]
    d['databases'].add('llpsdb')
    d['roles'].add('driver')
    set_organism(acc, row.get('Species', ''), priority=3)

    idr = clean_idr_lcr(row.get('IDR', ''))
    lcr = clean_idr_lcr(row.get('LCR', ''))
    if idr and not d['idrs']:
        d['idrs'] = idr
    if lcr and not d['lcrs']:
        d['lcrs'] = lcr

    d['mlos'].add('na')
    d['mlos_entries'].append({
        'source_acc':      acc,
        'source_mlo':      'na',
        'rol':             'driver',
        'source_database': 'llpsdb',
        'source_dataset':  'llpsdb',
        'mlo':             'na',
    })

# ---------------------------------------------------------------------------
# 2.  DrLLPS
# ---------------------------------------------------------------------------
print('Processing drllps...')
for _, row in drllps.iterrows():
    acc  = str(row['UniProt ID']).strip()
    role = DRLLPS_ROLE.get(str(row.get('LLPS Type', '')).strip(), 'client')
    org  = str(row.get('Species', '')).strip()

    d = acc_data[acc]
    d['databases'].add('drllps')
    d['roles'].add(role)
    set_organism(acc, org, priority=2)

    cond_raw = str(row.get('Condensate', '')).strip()
    condensates = [c.strip() for c in cond_raw.split(',') if c.strip()] or ['na']
    for cond in condensates:
        mlo = normalize_mlo(cond)
        d['mlos'].add(mlo)
        d['mlos_entries'].append({
            'source_acc':      acc,
            'source_mlo':      cond,
            'rol':             role,
            'source_database': 'drllps',
            'source_dataset':  'drllps',
            'mlo':             mlo,
        })

# ---------------------------------------------------------------------------
# 3.  PhasePdb
#
# Role logic:
#   phasepdb_summary (1,873 proteins): ALL phase-separate → driver
#     (PhasePdb is a database of phase-separating proteins; PS-self and PS-other
#     both describe proteins that undergo LLPS, just autonomous vs partner-driven)
#   phasepdb_mlo_entries proteins NOT in summary: found in condensates by
#     high-throughput screens but don't phase-separate themselves → client
#   phasepdb_mlo_entries proteins also in summary: role already set to driver
# ---------------------------------------------------------------------------
print('Processing phasepdb (summary + detail)...')

phasepdb_summary_accs = set(phasepdb_sum['UniProt ID'].dropna().str.strip())

# Build organism + MLO info from summary and detail
phasepdb_org = {}
for _, row in phasepdb_sum.iterrows():
    acc = str(row.get('UniProt ID', '')).strip()
    if acc:
        phasepdb_org[acc] = str(row.get('Organism', '')).strip()

# All summary proteins → driver; use detail rows for per-MLO entries
for _, row in phasepdb_det.iterrows():
    acc   = str(row.get('UniProt ID', '')).strip()
    if not acc or acc in ('nan', ''):
        continue
    mlo_r = str(row.get('MLO', '')).strip()
    mlo   = normalize_mlo(mlo_r) if mlo_r and mlo_r.lower() not in ('nan', '', 'none') else 'na'
    org   = phasepdb_org.get(acc, str(row.get('Organism', '')).strip())
    # All proteins in phasepdb_summary phase-separate → driver
    role  = 'driver'

    d = acc_data[acc]
    d['databases'].add('phasepdb')
    d['roles'].add(role)
    set_organism(acc, org, priority=2)
    d['mlos'].add(mlo)
    d['mlos_entries'].append({
        'source_acc':      acc,
        'source_mlo':      mlo_r if mlo_r else '_',
        'rol':             role,
        'source_database': 'phasepdb',
        'source_dataset':  'phasepdb_detail',
        'mlo':             mlo,
    })

print('Processing phasepdb (mlo_entries)...')
for _, row in phasepdb_mlo.iterrows():
    acc  = str(row.get('uniprot_id', '')).strip()
    if not acc or acc in ('nan', '_', ''):
        continue
    mlo_norm = normalize_mlo(str(row.get('mlo_normalized', '')).strip())
    mlo_src  = str(row.get('mlo_source',      '')).strip()
    org      = str(row.get('organism',         '')).strip()
    # Proteins already in summary are drivers; mlo_entries-only proteins are clients
    # (found in condensates by HT screens, not curated as phase-separating)
    role = 'driver' if acc in phasepdb_summary_accs else 'client'

    d = acc_data[acc]
    d['databases'].add('phasepdb')
    d['roles'].add(role)
    set_organism(acc, org, priority=2)
    d['mlos'].add(mlo_norm)
    d['mlos_entries'].append({
        'source_acc':      acc,
        'source_mlo':      mlo_src if mlo_src else mlo_norm,
        'rol':             role,
        'source_database': 'phasepdb',
        'source_dataset':  'phasepdb_mloht',
        'mlo':             mlo_norm,
    })

# ---------------------------------------------------------------------------
# 4.  PhasePro
# ---------------------------------------------------------------------------
print('Processing phasepro...')
for acc, entry in phasepro.items():
    acc = str(acc).strip()
    org = str(entry.get('organism', '')).strip()

    # organelles → MLOs
    org_raw = str(entry.get('organelles', '')).strip()
    organelle_list = [o.strip().rstrip('.') for o in re.split(r'[\n;,]', org_raw) if o.strip()]
    if not organelle_list:
        organelle_list = ['na']

    # boundaries → llps_regions
    boundaries_raw = str(entry.get('boundaries', '')).strip()
    regions = parse_phasepro_boundaries(boundaries_raw, 'phasepro')

    d = acc_data[acc]
    d['databases'].add('phasepro')
    d['roles'].add('driver')
    set_organism(acc, org, priority=4)
    d['llps_regions'].extend(regions)

    for org_mlo in organelle_list:
        mlo = normalize_mlo(org_mlo)
        d['mlos'].add(mlo)
        d['mlos_entries'].append({
            'source_acc':      acc,
            'source_mlo':      org_mlo,
            'rol':             'driver',
            'source_database': 'phasepro',
            'source_dataset':  'phasepro',
            'mlo':             mlo,
        })

# ---------------------------------------------------------------------------
# 5.  CDCode
# ---------------------------------------------------------------------------
print('Processing cdcode...')
for _, row in cdcode_p2c.iterrows():
    acc      = str(row.get('uniprotkb_ac', '')).strip()
    cond_name = str(row.get('condensate_name', '')).strip()
    if not acc or acc in ('nan', ''):
        continue

    mlo = normalize_mlo(cond_name)
    sp  = cdcode_species.get(acc, '')

    d = acc_data[acc]
    d['databases'].add('cdcode')
    d['roles'].add('client')
    set_organism(acc, sp, priority=1)
    d['mlos'].add(mlo)
    d['mlos_entries'].append({
        'source_acc':      acc,
        'source_mlo':      cond_name,
        'rol':             'client',
        'source_database': 'cdcode',
        'source_dataset':  'cdcode',
        'mlo':             mlo,
    })

# ---------------------------------------------------------------------------
# 6.  Carry over v1 idrs / lcrs / pfam_domains / llps_regions
# ---------------------------------------------------------------------------
print('Carrying over v1 annotations...')
for acc, v1e in v1.items():
    if acc not in acc_data:          # protein dropped from all current sources → skip
        continue
    d = acc_data[acc]
    # v1 idrs/lcrs were computed by external tools (IUPred/SEG) → prefer over llpsdb values
    if v1e.get('idrs'):
        d['idrs'] = v1e['idrs']
    if v1e.get('lcrs'):
        d['lcrs'] = v1e['lcrs']
    if not d['pfam_domains'] and v1e.get('pfam_domains'):
        d['pfam_domains'] = v1e['pfam_domains']
    # Merge v1 llps_regions (avoid duplicates)
    existing_regions = set(d['llps_regions'])
    for reg in (v1e.get('llps_regions') or '').split(','):
        reg = reg.strip()
        if reg and reg not in existing_regions:
            d['llps_regions'].append(reg)
            existing_regions.add(reg)
    # Organism fall-through
    if not d.get('organism') and v1e.get('organism'):
        d['organism'] = v1e['organism']

# ---------------------------------------------------------------------------
# 7.  Assemble final entries
# ---------------------------------------------------------------------------
print('Assembling v2 entries...')

def sort_roles(roles: set) -> str:
    order = ['driver', 'client', 'regulator']
    sorted_r = [r for r in order if r in roles] + \
               sorted(roles - set(order))
    return ','.join(sorted_r)


def sort_mlos(mlos: set) -> str:
    cleaned = {m for m in mlos if m and m not in ('na',)}
    result   = sorted(cleaned)
    if 'na' in mlos and not result:
        result = ['na']
    return ','.join(result) if result else 'na'


final_entries = {}
for acc, d in sorted(acc_data.items()):
    llps_regions_str = ','.join(r for r in d['llps_regions'] if r)

    final_entries[acc] = {
        'organism':        d.get('organism', ''),
        'database_source': ','.join(sorted(d['databases'])),
        'llps_roles':      sort_roles(d['roles']),
        'mlos':            sort_mlos(d['mlos']),
        'idrs':            d.get('idrs', ''),
        'lcrs':            d.get('lcrs', ''),
        'llps_regions':    llps_regions_str,
        'pfam_domains':    d.get('pfam_domains', ''),
        'mlos_entries':    d.get('mlos_entries', []),
    }

# ---------------------------------------------------------------------------
# 8.  Statistics
# ---------------------------------------------------------------------------
n = len(final_entries)
new_accs = set(final_entries) - set(v1)
print(f'\n=== v2 Summary ===')
print(f'  Total entries:       {n:,}')
print(f'  Entries in v1:       {len(v1):,}')
print(f'  New entries in v2:   {len(new_accs):,}')

db_counts = defaultdict(int)
role_counts = defaultdict(int)
for e in final_entries.values():
    for db in e['database_source'].split(','):
        db_counts[db] += 1
    for r in e['llps_roles'].split(','):
        role_counts[r] += 1

print('\n  Database source counts:')
for db, cnt in sorted(db_counts.items()):
    print(f'    {db:12s}: {cnt:,}')
print('\n  LLPS role counts:')
for r, cnt in sorted(role_counts.items()):
    print(f'    {r:12s}: {cnt:,}')

# ---------------------------------------------------------------------------
# 9.  Write JSON
# ---------------------------------------------------------------------------
out_json = OUT_DIR / 'mlosmetadb_v2_dataset.json'
output = {'n': n, 'entries': final_entries}
with open(out_json, 'w') as fh:
    json.dump(output, fh, separators=(',', ':'))
print(f'\nWrote JSON → {out_json}')

# ---------------------------------------------------------------------------
# 10. Write TSV  (flat, no mlos_entries column)
# ---------------------------------------------------------------------------
out_tsv = OUT_DIR / 'mlosmetadb_v2_dataset.tsv'
tsv_cols = ['acc', 'organism', 'database_source', 'llps_roles',
            'mlos', 'idrs', 'lcrs', 'llps_regions', 'pfam_domains']
rows = []
for acc, e in final_entries.items():
    rows.append({
        'acc':             acc,
        'organism':        e['organism'],
        'database_source': e['database_source'],
        'llps_roles':      e['llps_roles'],
        'mlos':            e['mlos'],
        'idrs':            e['idrs'],
        'lcrs':            e['lcrs'],
        'llps_regions':    e['llps_regions'],
        'pfam_domains':    e['pfam_domains'],
    })
df_out = pd.DataFrame(rows, columns=tsv_cols)
df_out.to_csv(out_tsv, sep='\t', index=False)
print(f'Wrote TSV  → {out_tsv}')
print('\nDone.')
