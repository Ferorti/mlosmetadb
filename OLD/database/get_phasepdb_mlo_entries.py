import requests
import time
import pandas as pd

mlo_req = requests.get("https://db.phasep.pro/api/mlos/")
mlos = mlo_req.json()
mlo_names = [mlo.get("name") for mlo in mlos]


mlo_entries = {}

for mlo_name in mlo_names:
    print(mlo_name)
    entries = requests.get(f"https://db.phasep.pro/api/mlos/{mlo_name}/mloht-entries"
                           , params={"limit": 10000}).json()['data']
    print(len(entries))
    mlo_entries[mlo_name] = entries
    time.sleep(10)
    print()

mlo_entries_list = []
for mlo_name, entries in mlo_entries.items():
    df = pd.DataFrame.from_dict(entries)
    df['mlo_source'] = mlo_name
    mlo_entries_list.append(df)

phasepdb_mlos = pd.concat(mlo_entries_list)
phasepdb_mlos['llps_rol_source'] = 'client'

phasepdb_mlos.to_csv("databases_input_data/phasepdb/phasepdb_mlo_entries_from_script.tsv",
                     index=False, sep='\t')
