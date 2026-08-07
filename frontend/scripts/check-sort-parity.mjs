#!/usr/bin/env node
/**
 * Checks that src/utils/sortProteins.js orders a protein list exactly the way
 * api/queries/protein_queries.py::_build_sort() does.
 *
 * _build_sort's docstring says the two must stay in sync and warns that "there
 * is no test suite that would catch the drift". Neither side can test this
 * alone — one is Python against SQLite's BINARY collation, the other is
 * JavaScript — so it lives here, as a script run against a live API.
 *
 *   python3 -m uvicorn main:app --port 8765     # from api/
 *   node frontend/scripts/check-sort-parity.mjs [http://127.0.0.1:8765]
 *
 * Exits non-zero on any divergence, so it can gate a release.
 *
 * How it works: the API returns a page already sorted server-side. A prefix of
 * a total order, re-sorted by that same total order, must come back unchanged —
 * so shuffling the page and running the client comparator over it has to
 * reproduce the server's sequence exactly, ties included.
 */

import http from 'node:http'
import https from 'node:https'
import { readFileSync } from 'node:fs'

// sortProteins.js is ESM, but package.json has no "type": "module" — and it
// cannot get one, because postcss.config.js is CommonJS and Tailwind would stop
// building. Node would therefore load the .js as CommonJS and find no named
// exports, so it is imported as source instead. No build step, no dependency,
// and the file under test is the real one the app ships.
const { sortProteins } = await import(
  'data:text/javascript;base64,' +
  Buffer.from(readFileSync(new URL('../src/utils/sortProteins.js', import.meta.url), 'utf8')).toString('base64')
)

const API = process.argv[2] ?? 'http://127.0.0.1:8765'

const SORT_KEYS = ['gene_name', 'mlo_count', 'source_db_count', 'disorder_mobidb_lite_dc', 'role']

// Different corpora because sort bugs hide in whichever one holds the NULLs.
const CORPORA = [
  { label: 'unfiltered',           params: {} },
  { label: 'mlo=stress_granule',   params: { mlo: 'stress_granule' } },
  { label: 'role=driver',          params: { role: 'driver' } },
  { label: 'organism=Homo sapiens',params: { organism: 'Homo sapiens' } },
]

function fetchJson(url) {
  const client = url.startsWith('https') ? https : http
  return new Promise((resolve, reject) => {
    client.get(url, (res) => {
      let body = ''
      res.on('data', (d) => (body += d))
      res.on('end', () => {
        try { resolve(JSON.parse(body)) } catch (e) { reject(new Error(`${url}: ${body.slice(0, 120)}`)) }
      })
    }).on('error', reject)
  })
}

function get(path, params = {}) {
  const url = new URL(API + path)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  return fetchJson(url.toString())
}

// Seeded, so a reported divergence is reproducible.
function shuffle(input, seed = 12345) {
  const arr = [...input]
  let s = seed
  const rnd = () => (s = (s * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

let checked = 0
let diverged = 0

for (const corpus of CORPORA) {
  for (const sortBy of SORT_KEYS) {
    for (const sortOrder of ['asc', 'desc']) {
      const res = await get('/proteins', { ...corpus.params, sort_by: sortBy, sort_order: sortOrder, page: 1, per_page: 50 })
      const rows = res.proteins ?? []
      if (rows.length < 2) continue

      checked++
      const server = rows.map((p) => p.uniprot_id)
      const client = sortProteins(shuffle(rows), sortBy, sortOrder).map((p) => p.uniprot_id)

      if (server.join('|') === client.join('|')) continue

      diverged++
      const at = server.findIndex((id, i) => id !== client[i])
      const window = (arr) => arr.slice(Math.max(0, at - 1), at + 3).join(', ')
      const row = rows.find((p) => p.uniprot_id === server[at])
      console.error(`DIVERGENCE  ${corpus.label}  sort_by=${sortBy} sort_order=${sortOrder}  at index ${at}`)
      console.error(`  server: ${window(server)}`)
      console.error(`  client: ${window(client)}`)
      console.error(`  row:    ${JSON.stringify({
        uniprot_id: row.uniprot_id,
        gene_name: row.gene_name,
        mlo_count: row.mlo_count,
        source_db_count: row.source_db_count,
        disorder_mobidb_lite_dc: row.disorder_mobidb_lite_dc,
        has_driver: row.has_driver,
        has_client: row.has_client,
      })}`)
    }
  }
}

if (diverged) {
  console.error(`\n${diverged} of ${checked} combinations diverge — sortProteins.js and _build_sort() are out of sync.`)
  process.exit(1)
}
console.log(`sort parity OK — ${checked} combinations, client and server agree.`)
