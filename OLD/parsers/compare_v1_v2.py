"""
Comparación MLOsMetaDB V1 vs V2.

Lee:
  - database/databases_input_data/mlosmetadb_v1/entrada_llps_proteins.csv  (V1)
  - database/interim/*.tsv  (V2, concatenado)

Imprime:
  1. Conteos globales
  2. Solapamiento por UniProt (global y por source_db)
  3. Coincidencia fina (uniprot + db + MLO)
  4. Coincidencia incluyendo rol (uniprot + db + MLO + rol)
  5. Detalle de proteínas perdidas y cambios de rol
"""

from pathlib import Path
from collections import Counter
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "database" / "interim"
V1_PATH = ROOT / "database" / "databases_input_data" / "mlosmetadb_v1" / "entrada_llps_proteins.csv"

# ── Mapeo de db names de V1 a source_db de V2 ────────────────────────────────
DB_MAP = {
    "drllps_clients":    "DrLLPS",
    "drllps_regulators": "DrLLPS",
    "drllps_scaffolds":  "DrLLPS",
    "phasepdb_ht":       "PhaseDB",
    "phasepdb_lt":       "PhaseDB",
    "phasepdb_ps":       "PhaseDB",
    "phasepro":          "PhasePro",
    "llpsdb":            "LLPSDB",
}


def load_v2() -> pd.DataFrame:
    return pd.concat(
        [pd.read_csv(f, sep="\t", dtype=str, keep_default_na=False) for f in INTERIM.glob("*.tsv")],
        ignore_index=True,
    )


def load_v1() -> pd.DataFrame:
    df = pd.read_csv(V1_PATH, dtype=str, keep_default_na=False)
    df["source_db"] = df["db"].map(DB_MAP)
    # Normalizar MLO: Droplet → in vitro droplet, vacíos → NotInformed
    df["mlo_norm"] = df["mlo_db"].str.strip()
    df.loc[df["mlo_norm"] == "Droplet", "mlo_norm"] = "in vitro droplet"
    df.loc[df["mlo_norm"].isin(["", "_"]), "mlo_norm"] = "NotInformed"
    # Normalizar rol: vacíos → NotInformed
    df["rol_norm"] = df["rol_db"].str.strip()
    df.loc[df["rol_norm"].isin(["", "_"]), "rol_norm"] = "NotInformed"
    return df


def section(title: str) -> None:
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def main() -> None:
    v1 = load_v1()
    v2 = load_v2()

    # ── 1. Conteos globales ───────────────────────────────────────────────────
    section("1. CONTEOS GLOBALES")
    print(f"  V1 filas totales:       {len(v1):>7}")
    print(f"  V2 filas totales:       {len(v2):>7}")
    print(f"  V1 UniProt únicos:      {v1['uniprot'].nunique():>7}")
    print(f"  V2 UniProt únicos:      {v2['uniprot_id'].nunique():>7}")
    print("\n  V1 por db:")
    print(v1["db"].value_counts().to_string())
    print("\n  V2 por source_db:")
    print(v2["source_db"].value_counts().to_string())

    # ── 2. Solapamiento por UniProt ───────────────────────────────────────────
    section("2. SOLAPAMIENTO POR UNIPROT_ID")
    uid_v1 = set(v1["uniprot"])
    uid_v2 = set(v2["uniprot_id"])
    shared  = uid_v1 & uid_v2
    only_v1 = uid_v1 - uid_v2
    only_v2 = uid_v2 - uid_v1
    print(f"  Compartidas (V1 ∩ V2):  {len(shared):>7}  ({100*len(shared)/len(uid_v1):.1f}% de V1 | {100*len(shared)/len(uid_v2):.1f}% de V2)")
    print(f"  Solo en V1 (perdidas):  {len(only_v1):>7}  ({100*len(only_v1)/len(uid_v1):.1f}% de V1)")
    print(f"  Solo en V2 (nuevas):    {len(only_v2):>7}  ({100*len(only_v2)/len(uid_v2):.1f}% de V2)")

    print("\n  Por source_db (sin CDCODE):")
    for db in ["PhaseDB", "DrLLPS", "LLPSDB", "PhasePro"]:
        u1 = set(v1[v1["source_db"] == db]["uniprot"])
        u2 = set(v2[v2["source_db"] == db]["uniprot_id"])
        s, o1, o2 = u1 & u2, u1 - u2, u2 - u1
        print(f"    {db:<10}  v1={len(u1):>5}  v2={len(u2):>5}  shared={len(s):>5}  only_v1={len(o1):>5}  only_v2={len(o2):>5}")
    u2_cd = set(v2[v2["source_db"] == "CDCODE"]["uniprot_id"])
    print(f"    {'CDCODE':<10}  v1=    -  v2={len(u2_cd):>5}  (fuente nueva en V2)")

    # ── 3. Coincidencia fina (uniprot + db + MLO) ─────────────────────────────
    section("3. COINCIDENCIA FINA: (uniprot, source_db, source_mlo)\n   [CDCODE excluido]")
    key3_v1     = set(zip(v1["uniprot"],    v1["source_db"], v1["mlo_norm"]))
    v2_nocd     = v2[v2["source_db"] != "CDCODE"]
    key3_v2     = set(zip(v2_nocd["uniprot_id"], v2_nocd["source_db"], v2_nocd["source_mlo"]))
    sh3  = key3_v1 & key3_v2
    o3_1 = key3_v1 - key3_v2
    o3_2 = key3_v2 - key3_v1
    print(f"  Tripletas únicas V1:             {len(key3_v1):>7}")
    print(f"  Tripletas únicas V2 (sin CD):    {len(key3_v2):>7}")
    print(f"  Coincidentes exactas:            {len(sh3):>7}  ({100*len(sh3)/len(key3_v1):.1f}% de V1)")
    print(f"  Solo en V1 (perdidas):           {len(o3_1):>7}  ({100*len(o3_1)/len(key3_v1):.1f}% de V1)")
    print(f"  Solo en V2 (nuevas):             {len(o3_2):>7}")
    print("\n  Perdidas por source_db:")
    c = Counter(db for _, db, _ in o3_1)
    for db, n in c.most_common():
        print(f"    {db}: {n}")
    print("\n  Nuevas por source_db:")
    c2 = Counter(db for _, db, _ in o3_2)
    for db, n in c2.most_common():
        print(f"    {db}: {n}")

    # ── 4. Coincidencia incluyendo rol ────────────────────────────────────────
    section("4. COINCIDENCIA CON ROL: (uniprot, source_db, source_mlo, rol)\n   [CDCODE excluido]")
    key4_v1 = set(zip(v1["uniprot"],         v1["source_db"], v1["mlo_norm"],       v1["rol_norm"]))
    key4_v2 = set(zip(v2_nocd["uniprot_id"], v2_nocd["source_db"], v2_nocd["source_mlo"], v2_nocd["source_role"]))
    sh4  = key4_v1 & key4_v2
    o4_1 = key4_v1 - key4_v2
    o4_2 = key4_v2 - key4_v1
    print(f"  Cuaternas únicas V1:             {len(key4_v1):>7}")
    print(f"  Cuaternas únicas V2 (sin CD):    {len(key4_v2):>7}")
    print(f"  Coincidentes exactas:            {len(sh4):>7}  ({100*len(sh4)/len(key4_v1):.1f}% de V1)")
    print(f"  Solo en V1 (perdidas):           {len(o4_1):>7}")
    print(f"  Solo en V2 (nuevas):             {len(o4_2):>7}")

    # Tripletas compartidas con rol distinto
    rol_diff = sh3 - {(u, db, mlo) for u, db, mlo, _ in sh4}
    print(f"\n  Tripletas con (uid+db+mlo) iguales pero rol distinto: {len(rol_diff)}")

    if rol_diff:
        changes = []
        kv1_dict = {}
        for u, db, mlo, r in key4_v1:
            kv1_dict.setdefault((u, db, mlo), set()).add(r)
        kv2_dict = {}
        for u, db, mlo, r in key4_v2:
            kv2_dict.setdefault((u, db, mlo), set()).add(r)
        for k in rol_diff:
            changes.append({
                "source_db": k[1],
                "rol_v1":    ";".join(sorted(kv1_dict.get(k, {}))),
                "rol_v2":    ";".join(sorted(kv2_dict.get(k, {}))),
            })
        df_c = pd.DataFrame(changes)
        print("\n  Pares de cambio más frecuentes:")
        print(df_c.groupby(["rol_v1", "rol_v2"]).size().sort_values(ascending=False).head(10).to_string())
        print("\n  Por source_db:")
        print(df_c.groupby("source_db").size().to_string())

    # ── 5. Proteínas perdidas ────────────────────────────────────────────────
    section("5. PROTEÍNAS SOLO EN V1 (detalle)")
    lost = v1[v1["uniprot"].isin(only_v1)][["uniprot", "source_db", "mlo_norm"]].drop_duplicates()
    print(f"  Total: {lost['uniprot'].nunique()} proteínas únicas")
    print("\n  Por source_db:")
    print(lost.groupby("source_db")["uniprot"].nunique().to_string())
    print("\n  Muestra (15 primeras):")
    print(lost.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
