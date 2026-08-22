<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStats } from '@/api/stats'
import { getMlos } from '@/api/mlos'
import { formatMlo, formatCount, formatOrganism } from '@/utils/format'
import { spatialLocationLabel } from '@/utils/mloAxes'
import StatBar from '@/components/ui/StatBar.vue'
import RoleCards from '@/components/browse/RoleCards.vue'
import SearchBox from '@/components/search/SearchBox.vue'
const router = useRouter()
const stats = ref(null)
const mlos = ref([])

onMounted(async () => {
  const [statsRes, mlosRes] = await Promise.all([getStats(), getMlos()])
  stats.value = statsRes.data
  mlos.value  = mlosRes.data.mlos ?? []
})

// Raw ingestion tags, in canonical display order -- matches
// mlo_definitions.source_db (used unmodified by /mlos) and
// mlo_annotations.source_db (used unmodified by /stats' by_source).
const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

// Real per-source blurbs, copied verbatim from
// components/unification/SourcesSection.vue:26-30 -- not the mock's
// invented text (spec §2.2).
const SOURCE_BLURBS = {
  CDCODE:   'Community-editable database of biomolecular condensates.',
  DrLLPS:   'Scaffold, regulator, and client proteins involved in LLPS.',
  LLPSDB:   'Proteins with LLPS behavior observed in vitro, with experimental conditions.',
  PhaSepDB: 'Manually curated database of proteins linked to LLPS.',
  PhasePro: 'Proteins and regions experimentally validated as LLPS drivers.',
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

const organismRows = computed(() => {
  const byOrg = stats.value?.proteins?.by_organism ?? {}
  const entries = Object.entries(byOrg).sort((a, b) => b[1] - a[1])
  const max = entries[0]?.[1] ?? 1
  return entries.slice(0, 8).map(([name, count]) => ({
    name: formatOrganism(name), count, pct: Math.round((count / max) * 100),
  }))
})

const coverageRows = computed(() => {
  return [...mlos.value]
    .sort((a, b) => (b.protein_count ?? 0) - (a.protein_count ?? 0))
    .slice(0, 14)
    .map(m => ({
      unified_mlo:   m.unified_mlo,
      spatial_location: m.spatial_location,
      protein_count: m.protein_count,
      cells: SOURCE_ORDER.map(src => {
        const def = (m.definitions ?? []).find(d => d.source_db === src)
        return {
          source: src,
          on:     !!def,
          title:  def ? `${src}: ${def.source_name ?? def.definition ?? ''}` : `${src}: not annotated`,
        }
      }),
    }))
})

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
    <section class="bg-surface border-b border-border">
      <div class="max-w-[1080px] mx-auto px-8 pt-[70px] pb-9">

        <h1 class="font-display font-bold text-[52px] leading-[1.05] tracking-[-0.035em] text-ink max-w-[15ch]">
          Proteins in membraneless organelles
        </h1>
        <p class="mt-5 text-[17px] leading-relaxed text-ink2 max-w-[56ch]">
          A meta-database of proteins associated with membraneless organelles
          involved in liquid-liquid phase separation. Integrates proteins from
          PhaSepDB, DrLLPS, PhaSePro, LLPSDB and CD-CODE.
        </p>

        <div class="mt-[34px] max-w-[660px]">
          <SearchBox
            :show-search-options="true"
            :initial-query="''"
            @search="handleSearch"
          />
          <div class="flex items-center gap-3 mt-3 font-mono text-[11.5px] text-muted">
            <span>TRY</span>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('FUS')">FUS</button>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('P35637')">P35637</button>
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
    <section class="max-w-4xl mx-auto px-6 pb-5">
      <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Browse by component role</h2>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        You can also reach proteins without naming one: pick the role they play across their annotations.
      </p>
      <RoleCards :stats="stats" />
    </section>

    <!-- Source databases + Model organisms -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16 grid grid-cols-1 md:grid-cols-2 gap-14 items-start">
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

      <div>
        <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Model organisms</h2>
          <span class="font-mono text-[11px] text-muted">{{ organismRows.length }} species</span>
        </div>
        <div class="flex flex-col gap-3">
          <div v-for="o in organismRows" :key="o.name" class="grid grid-cols-[1fr_74px] gap-3.5 items-start">
            <div>
              <span class="text-[13.5px] italic text-ink">{{ o.name }}</span>
              <div class="h-[5px] bg-track rounded-[1px] mt-1">
                <div class="h-[5px] bg-brand rounded-[1px]" :style="{ width: o.pct + '%' }"></div>
              </div>
            </div>
            <div class="font-mono text-xs text-ink text-right leading-[18px]">{{ formatCount(o.count) }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Organelle coverage -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16">
      <div class="flex items-baseline justify-between gap-5 border-b border-border pb-[11px] mb-3">
        <div class="flex items-baseline gap-3.5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Organelle coverage</h2>
          <span class="font-mono text-[11px] text-muted">top {{ coverageRows.length }} of {{ mlos.length }} unified terms</span>
        </div>
        <RouterLink to="/mlos" class="font-mono text-[11.5px] text-brand hover:text-ink hover:underline">All organelles →</RouterLink>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        A mark shows the organelle is annotated in that database. Hover a mark for the term the source itself uses.
      </p>
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ORGANELLE</th>
            <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">COMPARTMENT</th>
            <th v-for="c in SOURCE_ORDER" :key="c" class="text-center px-2 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 w-[78px]">{{ c }}</th>
            <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">PROTEINS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in coverageRows" :key="row.unified_mlo" class="border-b border-border-soft">
            <td class="py-[11px] pr-3 text-[13.5px]">
              <RouterLink :to="`/mlo/${row.unified_mlo}`" class="text-ink hover:text-brand">{{ formatMlo(row.unified_mlo) }}</RouterLink>
            </td>
            <td class="py-[11px] px-3 font-mono text-[11px] text-muted">{{ spatialLocationLabel(row.spatial_location) }}</td>
            <td v-for="cell in row.cells" :key="cell.source" :title="cell.title" class="py-[11px] px-2 text-center">
              <span v-if="cell.on" class="inline-block w-[7px] h-[7px] rounded-full bg-ink"></span>
              <span v-else class="inline-block w-[7px] h-px bg-border-strong"></span>
            </td>
            <td class="py-[11px] pl-3 text-right font-mono text-xs text-ink">{{ formatCount(row.protein_count) }}</td>
          </tr>
        </tbody>
      </table>
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
