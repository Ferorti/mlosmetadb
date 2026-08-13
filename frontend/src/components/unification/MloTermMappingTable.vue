<script setup>
import { ref, computed, onMounted } from 'vue'
import * as d3 from 'd3'
import client from '@/api/client'
import { mloTermMappingExportUrl } from '@/api/unification'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const PER_PAGE = 50
const DEFINITION_TRUNCATE = 120

const rows = ref([])
const loading = ref(true)
const error = ref(false)
const page = ref(1)
const sortKey = ref('unified_mlo')
const sortAsc = ref(true)
const expandedRows = ref(new Set())

onMounted(async () => {
  try {
    const { data } = await client.get('/unification/mlo-term-mapping/export', { responseType: 'text' })
    rows.value = d3.csvParse(data).map((r, idx) => ({ ...r, _idx: idx }))
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

function rowKey(row) {
  return `${row.unified_mlo}-${row.source_db}-${row._idx}`
}

function toggleExpand(key) {
  if (expandedRows.value.has(key)) expandedRows.value.delete(key)
  else expandedRows.value.add(key)
}

function definitionDisplay(row, key) {
  const def = row.definition || ''
  if (!def || def.length <= DEFINITION_TRUNCATE || expandedRows.value.has(key)) return def
  return def.slice(0, DEFINITION_TRUNCATE) + '…'
}
</script>

<template>
  <section id="mlo-term-mapping">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-lg font-semibold text-gray-800">MLO term mapping</h2>
      <a
        :href="mloTermMappingExportUrl()"
        download
        class="inline-flex items-center px-3 py-1.5 rounded bg-[#185FA5] text-white text-xs font-medium hover:bg-[#0F4A87] transition-colors"
      >
        Download CSV
      </a>
    </div>
    <p class="text-sm text-gray-600 mb-3">
      The full source-name-to-unified-term mapping, auditable entry by entry.
    </p>

    <LoadingSpinner v-if="loading" />
    <p v-else-if="error" class="text-sm text-gray-500">Could not load this table.</p>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm border border-gray-200 rounded-lg">
        <thead>
          <tr class="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wide">
            <th class="px-3 py-2 cursor-pointer select-none" @click="toggleSort('unified_mlo')">
              Unified MLO <span v-if="sortKey === 'unified_mlo'">{{ sortAsc ? '▲' : '▼' }}</span>
            </th>
            <th class="px-3 py-2 cursor-pointer select-none" @click="toggleSort('source_db')">
              Source DB <span v-if="sortKey === 'source_db'">{{ sortAsc ? '▲' : '▼' }}</span>
            </th>
            <th class="px-3 py-2">Source name</th>
            <th class="px-3 py-2 text-right">Annotations</th>
            <th class="px-3 py-2 text-right">Proteins</th>
            <th class="px-3 py-2">Definition</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in pageRows" :key="rowKey(row)" class="border-t border-gray-100 align-top">
            <td class="px-3 py-2">{{ row.unified_mlo.replace(/_/g, ' ') }}</td>
            <td class="px-3 py-2">{{ row.source_db }}</td>
            <td class="px-3 py-2">{{ row.source_mlo }}</td>
            <td class="px-3 py-2 text-right">{{ Number(row.annotations).toLocaleString() }}</td>
            <td class="px-3 py-2 text-right">{{ Number(row.proteins).toLocaleString() }}</td>
            <td class="px-3 py-2 text-xs text-gray-600">
              {{ definitionDisplay(row, rowKey(row)) }}
              <button
                v-if="row.definition && row.definition.length > DEFINITION_TRUNCATE"
                @click="toggleExpand(rowKey(row))"
                class="text-[#185FA5] hover:underline ml-1"
              >
                {{ expandedRows.has(rowKey(row)) ? 'show less' : 'show more' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="flex items-center justify-between mt-3 text-sm text-gray-600">
        <button :disabled="page === 1" @click="page--" class="px-2 py-1 rounded border border-gray-200 disabled:opacity-40">Previous</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button :disabled="page === totalPages" @click="page++" class="px-2 py-1 rounded border border-gray-200 disabled:opacity-40">Next</button>
      </div>
    </div>
  </section>
</template>
