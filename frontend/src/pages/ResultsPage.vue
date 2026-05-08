<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchBasic, searchAdvanced } from '@/api/search'
import { getProteins } from '@/api/proteins'
import { toMloSlug } from '@/utils/format'
import SearchBox from '@/components/search/SearchBox.vue'
import FilterSidebar from '@/components/search/FilterSidebar.vue'
import ResultsPanel from '@/components/results/ResultsPanel.vue'

const route  = useRoute()
const router = useRouter()

const results = ref(null)
const total   = ref(0)
const loading = ref(false)
const error   = ref(null)

const activeFilters = computed(() => ({ ...route.query }))

function hasAnyFilter(f) {
  return Object.keys(f).some(k => !['page', 'per_page', 'mode'].includes(k) && f[k])
}

function buildExtraFilters(f) {
  const params = {}
  if (f.role?.trim())              params.role              = f.role
  if (f.mlo?.trim())               params.mlo               = f.mlo
  if (f.organism?.trim())          params.organism          = f.organism
  if (f.feature_type?.trim())      params.feature_type      = f.feature_type
  if (f.feature_accession?.trim()) params.feature_accession = f.feature_accession
  params.page     = Number(f.page)     || 1
  params.per_page = Number(f.per_page) || 20
  return params
}

async function fetchResults() {
  const f = activeFilters.value

  if (!hasAnyFilter(f)) {
    results.value = null
    total.value   = 0
    return
  }

  loading.value = true
  error.value   = null

  try {
    const field = f.field ?? 'all'
    let res

    if (f.q) {
      if (field === 'all') {
        const q = f.q.trim()
        // Detect UniProt accession: letter + 5 alphanums + optional 2-char suffix
        const uniprotPattern = /^[A-Z][0-9][A-Z0-9]{3}[0-9]([A-Z][A-Z0-9]{1}[0-9])?$/i
        if (uniprotPattern.test(q)) {
          res = await getProteins({ uniprot_id: q.toUpperCase(), ...buildExtraFilters(f) })
        } else {
          const searchRes = await searchBasic(q, f.mode ?? 'fuzzy')
          const mloHits = searchRes.data?.mlos ?? []
          if (mloHits.length > 0) {
            // MLO match found — fetch all proteins for that MLO (paginated, with filters)
            res = await getProteins({ mlo: mloHits[0].unified_mlo, ...buildExtraFilters(f) })
          } else if (f.organism || f.role) {
            // No MLO match but has filters — use advanced search by gene_name
            res = await searchAdvanced({ gene_name: q, ...buildExtraFilters(f) })
          } else {
            res = searchRes
          }
        }
      } else if (field === 'uniprot_id') {
        res = await getProteins({ uniprot_id: f.q, ...buildExtraFilters(f) })
      } else if (field === 'gene_name') {
        res = await getProteins({ gene_name: f.q, ...buildExtraFilters(f) })
      } else if (field === 'mlo') {
        res = await getProteins({ mlo: toMloSlug(f.q), ...buildExtraFilters(f) })
      }
    } else {
      res = await getProteins(buildExtraFilters(f))
    }

    if (!res) {
      results.value = []
      total.value   = 0
      return
    }

    const data    = res.data
    results.value = data.proteins ?? data.items ?? data.results ?? []
    total.value   = data.total    ?? data.total_hits ?? 0

    // TODO: move to server-side when API supports ?sort=mlo_count
    results.value = [...results.value].sort(
      (a, b) => (b.mlo_count ?? 0) - (a.mlo_count ?? 0)
    )

  } catch (e) {
    console.error('[fetchResults error]', e)
    error.value   = e?.response?.data?.message ?? e?.message ?? 'Error fetching results'
    results.value = []
    total.value   = 0
  } finally {
    loading.value = false
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
        :facets="null"
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
        @page-change="onPageChange"
        @remove-filter="onRemoveFilter"
      />
    </div>

  </div>
</template>
