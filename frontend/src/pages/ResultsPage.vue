<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchBasic, searchAdvanced } from '@/api/search'
import { getProteins } from '@/api/proteins'
import { toMloSlug } from '@/utils/format'
import { parseIdrRegions, parseLcdRegions, parseDomains, calcCoverage } from '@/utils/parseFeatures'
import SearchBox from '@/components/search/SearchBox.vue'
import FilterSidebar from '@/components/search/FilterSidebar.vue'
import ResultsPanel from '@/components/results/ResultsPanel.vue'

const route  = useRoute()
const router = useRouter()

const results         = ref(null)
const total           = ref(0)
const facets          = ref(null)
const loading         = ref(false)
const error           = ref(null)
const downloadLoading = ref(false)

function computeFacetsFromProteins(proteins) {
  if (!proteins?.length) return null
  const by_organism = {}
  const by_role = {}
  const by_mlo = {}
  for (const p of proteins) {
    if (p.organism) by_organism[p.organism] = (by_organism[p.organism] || 0) + 1
    if (p.has_driver) by_role.driver = (by_role.driver || 0) + 1
    if (!p.has_driver) by_role.component = (by_role.component || 0) + 1
    for (const m of p.mlos ?? []) by_mlo[m] = (by_mlo[m] || 0) + 1
  }
  return { by_organism, by_role, by_mlo }
}

const activeFilters = computed(() => ({ ...route.query }))

function hasAnyFilter(f) {
  return Object.keys(f).some(k => !['page', 'per_page', 'mode', 'sort_by', 'sort_order'].includes(k) && f[k])
}

function buildExtraFilters(f, overrides = {}) {
  const params = {}
  if (f.role?.trim())              params.role              = f.role
  if (f.mlo?.trim())               params.mlo               = f.mlo
  if (f.organism?.trim())          params.organism          = f.organism
  if (f.feature_type?.trim())      params.feature_type      = f.feature_type
  if (f.feature_accession?.trim()) params.feature_accession = f.feature_accession
  params.sort_by    = f.sort_by?.trim()    || 'mlo_count'
  params.sort_order = f.sort_order?.trim() || 'desc'
  params.page     = Number(f.page)     || 1
  params.per_page = Number(f.per_page) || 20
  return { ...params, ...overrides }
}

async function runSearch(f, overrides = {}) {
  const field       = f.field ?? 'all'
  const extraFilters = buildExtraFilters(f, overrides)

  if (f.q) {
    const q = f.q.trim()
    if (field === 'all') {
      const uniprotPattern = /^[A-Z][0-9][A-Z0-9]{3}[0-9]([A-Z][A-Z0-9]{1}[0-9])?$/i
      if (uniprotPattern.test(q)) {
        return getProteins({ uniprot_id: q.toUpperCase(), ...extraFilters })
      }
      const searchRes = await searchBasic(q, f.mode ?? 'fuzzy')
      const mloHits   = searchRes.data?.mlos ?? []
      if (mloHits.length > 0) {
        return getProteins({ mlo: mloHits[0].unified_mlo, ...extraFilters })
      } else if (f.organism || f.role) {
        return searchAdvanced({ gene_name: q, ...extraFilters })
      }
      return searchRes
    } else if (field === 'uniprot_id') {
      return getProteins({ uniprot_id: q, ...extraFilters })
    } else if (field === 'gene_name') {
      return getProteins({ gene_name: q, ...extraFilters })
    } else if (field === 'mlo') {
      return getProteins({ mlo: toMloSlug(q), ...extraFilters })
    }
  }
  return getProteins(extraFilters)
}

async function fetchResults() {
  const f = activeFilters.value
  if (!hasAnyFilter(f)) { results.value = null; total.value = 0; facets.value = null; return }

  loading.value = true
  error.value   = null
  try {
    const res = await runSearch(f)
    if (!res) { results.value = []; total.value = 0; facets.value = null; return }
    const data    = res.data
    results.value = data.proteins ?? data.items ?? data.results ?? []
    total.value   = data.total    ?? data.total_hits ?? 0
    facets.value  = data.facets ?? computeFacetsFromProteins(results.value)
  } catch (e) {
    console.error('[fetchResults error]', e)
    error.value   = e?.response?.data?.message ?? e?.message ?? 'Error fetching results'
    results.value = []
    total.value   = 0
    facets.value  = null
  } finally {
    loading.value = false
  }
}

function buildTsv(proteins) {
  const header = [
    'uniprot_id', 'gene_name', 'protein_name', 'organism', 'role',
    'mlos', 'source_dbs', 'idr_percent', 'lcd_percent', 'domain_count', 'sequence_length',
  ].join('\t')
  const rows = proteins.map(p => {
    const idrPct  = calcCoverage(parseIdrRegions(p.idr_regions), p.sequence_length) ?? ''
    const lcdPct  = calcCoverage(parseLcdRegions(p.lcr_regions), p.sequence_length) ?? ''
    const domains = parseDomains(p.domains)
    const role    = p.has_driver ? 'driver' : 'component'
    return [
      p.uniprot_id    ?? '',
      p.gene_name     ?? '',
      p.protein_name  ?? '',
      p.organism      ?? '',
      role,
      (p.mlos       ?? []).join(';'),
      (p.source_dbs ?? []).join(';'),
      idrPct,
      lcdPct,
      domains.length,
      p.sequence_length ?? '',
    ].join('\t')
  })
  return [header, ...rows].join('\n')
}

function triggerDownload(content, filename) {
  const blob = new Blob([content], { type: 'text/tab-separated-values' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function downloadResults() {
  const f = activeFilters.value
  if (!hasAnyFilter(f)) return
  downloadLoading.value = true
  // MAX_PER_PAGE on the backend is 200 — paginate in batches
  const BATCH = 200
  try {
    const all = []
    let page  = 1
    let total = null
    do {
      const res = await runSearch(f, { per_page: BATCH, page, sort_by: undefined, sort_order: undefined })
      if (!res) break
      const data  = res.data
      const batch = data.proteins ?? data.items ?? data.results ?? []
      all.push(...batch)
      if (total === null) total = data.total ?? data.total_hits ?? batch.length
      if (batch.length < BATCH) break
      page++
    } while (all.length < total)
    triggerDownload(buildTsv(all), 'mlosmetadb_results.tsv')
  } catch (e) {
    console.error('[downloadResults error]', e)
  } finally {
    downloadLoading.value = false
  }
}

watch(() => route.query, fetchResults, { immediate: true, deep: true })

function onSearch({ q, field }) {
  const query = {}
  if (q)                        query.q     = q
  if (field && field !== 'all') query.field = field
  router.push({ query })
}

function onFiltersUpdate(newFilters) {
  router.push({ query: { ...newFilters, page: 1 } })
}

function onRemoveFilter(key) {
  const q = { ...route.query }
  delete q[key]
  q.page = 1
  router.push({ query: q })
}

function onPageChange(page) {
  router.push({ query: { ...route.query, page } })
}

function onResetFilters() {
  const query = {}
  if (route.query.q)     query.q     = route.query.q
  if (route.query.field) query.field = route.query.field
  router.push({ query })
}
</script>

<template>
  <div class="flex flex-col min-h-0">

    <!-- Search bar: full width with own background -->
    <div class="bg-[#EBF3FB] border-b border-[#C8DFF2]">
      <div class="max-w-6xl mx-auto px-6 py-3">
        <SearchBox
          compact
          :initial-query="route.query.q ?? ''"
          :initial-field="route.query.field ?? 'all'"
          @search="onSearch"
        />
      </div>
    </div>

    <!-- Sidebar + results: centered -->
    <div class="max-w-6xl mx-auto px-6 w-full flex flex-1 gap-0 mt-6">
      <FilterSidebar
        :filters="activeFilters"
        :facets="facets"
        @update:filters="onFiltersUpdate"
        @reset-filters="onResetFilters"
      />
      <ResultsPanel
        :results="results"
        :total="total"
        :page="Number(route.query.page ?? 1)"
        :per-page="Number(route.query.per_page ?? 20)"
        :loading="loading"
        :query="route.query.q ?? ''"
        :active-filters="activeFilters"
        :error="error"
        :download-loading="downloadLoading"
        @page-change="onPageChange"
        @remove-filter="onRemoveFilter"
        @download="downloadResults"
      />
    </div>

  </div>
</template>
