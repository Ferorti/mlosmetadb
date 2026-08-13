<script setup>
import { ref, computed, onMounted } from 'vue'
import * as d3 from 'd3'
import client from '@/api/client'
import { discrepantPairsExportUrl } from '@/api/unification'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const PER_PAGE = 50
const COLUMNS = [
  { key: 'uniprot_id', label: 'UniProt ID' },
  { key: 'gene_name', label: 'Gene' },
  { key: 'unified_mlo', label: 'MLO' },
  { key: 'sources', label: 'Sources' },
  { key: 'categories', label: 'Categories' },
  { key: 'source_roles', label: 'Source roles' },
  { key: 'evidence_types', label: 'Evidence types' },
]

const rows = ref([])
const loading = ref(true)
const error = ref(false)
const page = ref(1)
const sortKey = ref('uniprot_id')
const sortAsc = ref(true)

onMounted(async () => {
  try {
    const { data } = await client.get('/unification/discrepant-pairs/export', { responseType: 'text' })
    rows.value = d3.csvParse(data)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})

const sortedRows = computed(() => {
  const list = [...rows.value]
  list.sort((a, b) => {
    const av = a[sortKey.value] ?? ''
    const bv = b[sortKey.value] ?? ''
    return sortAsc.value ? av.localeCompare(bv) : bv.localeCompare(av)
  })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedRows.value.length / PER_PAGE)))
const pageRows = computed(() => {
  const start = (page.value - 1) * PER_PAGE
  return sortedRows.value.slice(start, start + PER_PAGE)
})

function toggleSort(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
  page.value = 1
}
</script>

<template>
  <section id="discrepant-pairs">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-lg font-semibold text-gray-800">Discrepant pairs</h2>
      <a
        :href="discrepantPairsExportUrl()"
        download
        class="inline-flex items-center px-3 py-1.5 rounded bg-[#185FA5] text-white text-xs font-medium hover:bg-[#0F4A87] transition-colors"
      >
        Download CSV
      </a>
    </div>
    <p class="text-sm text-gray-600 mb-3">
      {{ rows.length.toLocaleString() }} protein–MLO pairs where sources assign different categories.
    </p>

    <LoadingSpinner v-if="loading" />
    <p v-else-if="error" class="text-sm text-gray-500">Could not load this table.</p>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm border border-gray-200 rounded-lg">
        <thead>
          <tr class="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wide">
            <th v-for="col in COLUMNS" :key="col.key" class="px-3 py-2 cursor-pointer select-none" @click="toggleSort(col.key)">
              {{ col.label }}
              <span v-if="sortKey === col.key">{{ sortAsc ? '▲' : '▼' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in pageRows" :key="`${row.uniprot_id}-${row.unified_mlo}`" class="border-t border-gray-100">
            <td class="px-3 py-2">
              <RouterLink :to="`/protein/${row.uniprot_id}`" class="text-[#185FA5] hover:underline font-mono text-xs">
                {{ row.uniprot_id }}
              </RouterLink>
            </td>
            <td class="px-3 py-2">{{ row.gene_name }}</td>
            <td class="px-3 py-2">{{ row.unified_mlo.replace(/_/g, ' ') }}</td>
            <td class="px-3 py-2 text-xs">{{ row.sources }}</td>
            <td class="px-3 py-2 text-xs">{{ row.categories }}</td>
            <td class="px-3 py-2 text-xs">{{ row.source_roles }}</td>
            <td class="px-3 py-2 text-xs">{{ row.evidence_types }}</td>
          </tr>
        </tbody>
      </table>

      <div class="flex items-center justify-between mt-3 text-sm text-gray-600">
        <button
          :disabled="page === 1"
          @click="page--"
          class="px-2 py-1 rounded border border-gray-200 disabled:opacity-40"
        >Previous</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button
          :disabled="page === totalPages"
          @click="page++"
          class="px-2 py-1 rounded border border-gray-200 disabled:opacity-40"
        >Next</button>
      </div>
    </div>
  </section>
</template>
