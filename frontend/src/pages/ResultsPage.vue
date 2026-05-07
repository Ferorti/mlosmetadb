<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchAdvanced } from '@/api/search'
import { getProteins } from '@/api/proteins'
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

function buildAdvancedParams(f) {
  const p = {}
  if (f.q) {
    if (f.field === 'gene_name')  p.gene_name  = f.q
    if (f.field === 'uniprot_id') p.uniprot_id = f.q
  }
  if (f.role)               p.role               = f.role
  if (f.mlo)                p.mlo                = f.mlo
  if (f.organism)           p.organism           = f.organism
  if (f.source_db)          p.source_db          = f.source_db
  if (f.feature_type)       p.feature_type       = f.feature_type
  if (f.feature_accession)  p.feature_accession  = f.feature_accession
  p.page     = Number(f.page     ?? 1)
  p.per_page = Number(f.per_page ?? 20)
  return p
}

async function fetchResults() {
  const f = activeFilters.value
  if (!hasAnyFilter(f)) {
    results.value = null
    total.value   = 0
    error.value   = null
    return
  }
  loading.value = true
  error.value   = null
  try {
    if (f.q) {
      const params = buildAdvancedParams(f)
      if (!f.field || f.field === 'all') {
        params.gene_name = f.q
      } else if (f.field === 'mlo') {
        params.mlo = f.q
      }
      const res    = await searchAdvanced(params)
      results.value = res.data.proteins ?? []
      total.value   = res.data.total ?? results.value.length

    } else {
      const params = buildAdvancedParams(f)
      const res    = await getProteins(params)
      results.value = res.data.proteins ?? []
      total.value   = res.data.total ?? results.value.length
    }
  } catch (err) {
    console.error('[fetchResults]', err?.response?.status, err?.response?.data ?? err?.message)
    error.value   = err?.response?.data?.message ?? err?.message ?? 'Error fetching results'
    results.value = []
    total.value   = 0
  } finally {
    loading.value = false
  }
}

watch(() => route.query, fetchResults, { immediate: true, deep: true })

function onSearch({ q, field, mode, role }) {
  const query = {}
  if (q)                        query.q    = q
  if (field && field !== 'all') query.field = field
  if (mode && mode !== 'fuzzy') query.mode  = mode
  if (role)                     query.role  = role
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
