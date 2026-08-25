<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStats } from '@/api/stats'
import { getMlos } from '@/api/mlos'
import { formatMlo, formatCount, formatOrganism } from '@/utils/format'
import { spatialLocationLabel } from '@/utils/mloAxes'
import { filterMlosByQuery } from '@/utils/mloMatch'
import StatBar from '@/components/ui/StatBar.vue'
import RoleCards from '@/components/browse/RoleCards.vue'
import SearchBox from '@/components/search/SearchBox.vue'
const router = useRouter()
const stats = ref(null)
const mlos = ref([])
const BASE_URL = import.meta.env.BASE_URL

onMounted(async () => {
  const [statsRes, mlosRes] = await Promise.all([getStats(), getMlos()])
  stats.value = statsRes.data
  mlos.value  = mlosRes.data.mlos ?? []
})

// Raw ingestion tags, in canonical display order -- matches
// mlo_definitions.source_db (used unmodified by /mlos) and
// mlo_annotations.source_db (used unmodified by /stats' by_source).
const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

// Each source's own tagline, kept in sync with
// components/unification/SourcesSection.vue's SOURCE_BLURBS.
const SOURCE_BLURBS = {
  CDCODE:   'Crowdsourcing condensate database and encyclopedia.',
  DrLLPS:   'Data resource of liquid-liquid phase separation.',
  LLPSDB:   'Proteins undergoing liquid-liquid phase separation in vitro.',
  PhaSepDB: 'The comprehensive knowledgebase for protein phase separation and biomolecular condensates.',
  PhasePro: 'Comprehensive database of proteins driving liquid-liquid phase separation (LLPS) in living cells.',
}
const SOURCE_DISPLAY_NAMES = { CDCODE: 'CD-CODE', DrLLPS: 'DrLLPS', LLPSDB: 'LLPSDB', PhaSepDB: 'PhaSepDB', PhasePro: 'PhasePro' }

// `/stats`' mlo_annotations.unique_proteins_by_source is built server-side with
// policy.canonical_source_case_sql(), which remaps two of the five raw tags to
// their canonical display form (api/main.py + policy.py CANONICAL_SOURCE_NAMES,
// confirmed against api/tests/test_stats.py:46 and the frontend's own
// data/stats.json fallback) -- "CDCODE" -> "CD-CODE" and "PhasePro" -> "PhaSePro".
// The other three keys ("DrLLPS", "LLPSDB", "PhaSepDB") pass through unchanged.
// This map is only for reading that one field; SOURCE_ORDER itself stays on the
// raw tags because that's what mlo_definitions.source_db (the coverage matrix)
// and mlo_annotations.by_source both use unmodified.
const UNIQUE_BY_SOURCE_KEY = { CDCODE: 'CD-CODE', DrLLPS: 'DrLLPS', LLPSDB: 'LLPSDB', PhaSepDB: 'PhaSepDB', PhasePro: 'PhaSePro' }

const sourceRows = computed(() => {
  const counts = stats.value?.mlo_annotations?.unique_proteins_by_source ?? {}
  return SOURCE_ORDER.map(key => ({
    name:  SOURCE_DISPLAY_NAMES[key],
    blurb: SOURCE_BLURBS[key],
    count: counts[UNIQUE_BY_SOURCE_KEY[key]] ?? 0,
  }))
})

const totalOrganismCount = computed(() => stats.value?.proteins?.total_organisms ?? 0)

const organismRows = computed(() => {
  const byOrg     = stats.value?.proteins?.by_organism ?? {}
  const byDrivers = stats.value?.proteins?.by_organism_drivers ?? {}
  const entries = Object.entries(byOrg).sort((a, b) => b[1] - a[1])
  const max = entries[0]?.[1] ?? 1
  return entries.slice(0, 10).map(([name, count]) => ({
    rawName: name,
    name: formatOrganism(name),
    count,
    driverCount: byDrivers[name] ?? 0,
    pct: Math.round((count / max) * 100),
  }))
})

// Browse by MLO — same behavior as the pre-redesign MloBadges.vue: text
// filter over the unified name and every source alias, sorted by driver
// count desc, capped at 20 unfiltered / 30 filtered (a filter can
// legitimately match many). Now rendered as a table row instead of a card,
// with the 5-source coverage dots added alongside the original
// protein/driver counts and the "explore proteins" link.
const MLO_DISPLAY_LIMIT  = 20
const MLO_FILTERED_LIMIT = 30
const mloFilter = ref('')

const mlosByDrivers = computed(() =>
  [...mlos.value].sort((a, b) => (b.driver_count ?? 0) - (a.driver_count ?? 0))
)
const mloMatches = computed(() => filterMlosByQuery(mlosByDrivers.value, mloFilter.value))
const mloShown = computed(() =>
  mloMatches.value.slice(0, mloFilter.value.trim() ? MLO_FILTERED_LIMIT : MLO_DISPLAY_LIMIT)
)
const mloHiddenCount = computed(() => Math.max(0, mloMatches.value.length - mloShown.value.length))

const mloRows = computed(() => mloShown.value.map(m => ({
  unified_mlo:      m.unified_mlo,
  spatial_location: m.spatial_location,
  protein_count:    m.protein_count,
  driver_count:     m.driver_count,
  cells: SOURCE_ORDER.map(src => {
    const on  = m.sources?.includes(src) ?? false
    const def = (m.definitions ?? []).find(d => d.source_db?.toLowerCase() === src.toLowerCase())
    return {
      source: src,
      on,
      title:  on ? `${src}: ${def?.source_name ?? def?.definition ?? 'annotated'}` : `${src}: not annotated`,
    }
  }),
})))

// No `field` is emitted any more: a protein search always covers accession,
// gene name and protein name at once. Organelles are not searched here — the
// MLO grid below links straight to ?mlo=<slug>.
function handleSearch({ q, role, mode }) {
  if (!q) return
  const query = { q }
  if (role)  query.role = role
  if (mode)  query.mode = mode
  router.push({ path: '/results', query })
}

function searchExample(term) {
  router.push({ path: '/results', query: { q: term, mode: 'fuzzy' } })
}

</script>

<template>
  <div class="bg-white">

    <!-- Hero + Search -->
    <section class="bg-[#EAF2FA] border-b border-[#D2E3F1] text-center">
      <div class="max-w-3xl mx-auto px-8 pt-8 pb-7">

        <div class="flex justify-center mb-1">
          <img :src="`${BASE_URL}loguito_horizontal.svg`" alt="MLOsMetaDB" class="h-7 w-auto">
        </div>

        <h1 class="font-display font-bold text-[30px] leading-tight tracking-[-0.015em] text-ink">
          MLOsMetaDB
        </h1>
        <p class="mt-3 text-[15px] leading-relaxed text-ink2">
          A meta-database of proteins associated with membraneless organelles
          involved in liquid-liquid phase separation. Integrates proteins from
          PhaSepDB, DrLLPS, PhaSePro, LLPSDB and CD-CODE.
        </p>

        <div class="mt-6">
          <SearchBox
            :show-search-options="true"
            :initial-query="''"
            @search="handleSearch"
          />
          <div class="flex items-center justify-center gap-1 mt-3 text-[11.5px] text-muted">
            <span>Examples:</span>
            <button class="text-brand hover:text-ink hover:underline mx-1" @click="searchExample('FUS')">FUS</button>
            <span>·</span>
            <button class="text-brand hover:text-ink hover:underline mx-1" @click="searchExample('P35637')">P35637</button>
          </div>
        </div>

      </div>
    </section>

    <!-- StatBar — flush below hero 
    <section class="max-w-4xl mx-auto px-6 py-4">
      <StatBar :stats="stats" />
    </section>
-->
    <div class=" mx-6 my-4"></div>

    <!-- Browse by role -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16">
      <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Browse by component role</h2>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        You can also reach proteins without naming one: pick the role they play across their annotations.
      </p>
      <RoleCards :stats="stats" />
    </section>

    <!-- Browse by MLO -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16">
      <div class="flex items-baseline justify-between gap-5 border-b border-border pb-[11px] mb-3">
        <div class="flex items-baseline gap-3.5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Membraneless organelles (MLOs)</h2>
          <span class="font-mono text-[11px] text-muted">{{ mloRows.length }} of {{ mlos.length }} unified terms</span>
        </div>
        <RouterLink to="/mlos" class="font-mono text-[11.5px] text-brand hover:text-ink hover:underline">All organelles →</RouterLink>
      </div>
      <p class="text-[13.5px] text-ink3 mb-4">
        Or find proteins by the organelle they are associated with. The filter
        also reads the names each source database uses, so "GW-body" finds
        P body. A mark below shows the organelle is annotated in that
        database — hover a mark for the term the source itself uses.
      </p>

      <input
        v-model="mloFilter"
        type="text"
        placeholder="Filter organelles — try GW-body, foci, nucleolus"
        class="w-full max-w-md text-[13px] text-ink border border-border rounded-[2px] px-3 py-2 mb-4 focus:outline-none focus:border-brand"
      />

      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ORGANELLE</th>
            <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">COMPARTMENT</th>
            <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">PROTEINS</th>
            <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">DRIVERS</th>
            <th v-for="c in SOURCE_ORDER" :key="c" class="text-center px-1 pb-[9px] border-b border-border-strong font-mono text-[10px] font-normal text-ink3">{{ c }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in mloRows" :key="row.unified_mlo" class="border-b border-border-soft">
            <td class="py-[11px] pr-3 text-[13.5px]">
              <RouterLink :to="{ path: '/results', query: { mlo: row.unified_mlo } }" class="text-brand hover:text-ink hover:underline">{{ formatMlo(row.unified_mlo) }}</RouterLink>
            </td>
            <td class="py-[11px] px-3 font-mono text-[11px] text-muted">{{ spatialLocationLabel(row.spatial_location) }}</td>
            <td class="py-[11px] px-3 text-right font-mono text-xs text-ink">{{ formatCount(row.protein_count) }}</td>
            <td class="py-[11px] px-3 text-right font-mono text-xs text-brand">{{ formatCount(row.driver_count) }}</td>
            <td v-for="cell in row.cells" :key="cell.source" :title="cell.title" class="py-[11px] px-1 text-center">
              <span v-if="cell.on" class="text-ink3 text-[11px] leading-none">✓</span>
              <span v-else class="inline-block w-[7px] h-px bg-border-strong"></span>
            </td>
          </tr>
        </tbody>
      </table>

      <p v-if="mloHiddenCount" class="mt-3 text-[12px] text-ink3">
        {{ mloHiddenCount }} more match{{ mloHiddenCount === 1 ? 'es' : '' }} — refine the filter or <RouterLink to="/mlos" class="text-brand hover:underline">view all</RouterLink>.
      </p>
    </section>

    <!-- Model organisms + Source databases -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16 grid grid-cols-1 md:grid-cols-2 gap-14 items-start">
      <div>
        <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Model organisms</h2>
          <span class="font-mono text-[11px] text-muted">top {{ organismRows.length }} of {{ totalOrganismCount }} species</span>
        </div>
        <div class="flex flex-col gap-2">
          <RouterLink
            v-for="o in organismRows"
            :key="o.name"
            :to="{ path: '/results', query: { organism: o.rawName } }"
            class="grid grid-cols-[170px_1fr_140px] items-center gap-3 hover:opacity-75 transition-opacity"
          >
            <span class="text-[13.5px] italic text-ink truncate">{{ o.name }}</span>
            <div class="h-[5px] bg-track rounded-[1px]">
              <div class="h-[5px] bg-brand rounded-[1px]" :style="{ width: o.pct + '%' }"></div>
            </div>
            <div class="font-mono text-[11px] text-ink text-right whitespace-nowrap">
              {{ formatCount(o.count) }}<span class="text-muted"> · {{ formatCount(o.driverCount) }} drivers</span>
            </div>
          </RouterLink>
        </div>
      </div>

      <div>
        <div class="border-b border-border pb-[11px] mb-5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Source databases</h2>
        </div>
        <table class="w-full border-collapse text-[13.5px]">
          <tbody>
            <tr v-for="src in sourceRows" :key="src.name" class="border-b border-border-soft">
              <td class="py-[11px] pr-3"><span class="font-medium text-ink">{{ src.name }}</span></td>
              <td class="py-[11px] px-3 text-[13px] text-ink3">{{ src.blurb }}</td>
              <td class="py-[11px] pl-3 text-right font-mono text-xs text-ink whitespace-nowrap">{{ formatCount(src.count) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="mt-4 text-[12.5px] leading-relaxed text-ink3 max-w-[64ch]">
          Entries are merged on UniProt accession. Where sources disagree on an
          organelle name, both the unified term and the original string are kept.
        </p>
      </div>
    </section>

    <!-- Get the data -->
    <section class="max-w-[1080px] mx-auto px-8 pb-24">
      <div class="border-b border-border pb-[11px] mb-6">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Get the data</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <RouterLink to="/api" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">REST API</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">Query proteins, organelles and annotations as JSON. No key required.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Documentation →</div>
        </RouterLink>
        <RouterLink to="/data" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">Bulk download</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">Full database as TSV, with the source annotation preserved per row.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Files and schema →</div>
        </RouterLink>
        <RouterLink to="/data" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">Term mapping</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">The table that maps every source organelle name to its unified term.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Browse mapping →</div>
        </RouterLink>
      </div>
    </section>

    <!-- Advanced search link 
    <section class="max-w-4xl mx-auto px-6 pb-12 text-center">
      <RouterLink
        to="/results"
        class="text-sm text-[#2B6CB0] font-medium hover:underline transition-colors"
      >
        Need complex queries? Try the Advanced Search →
      </RouterLink>
    </section>-->

  </div>
</template>
