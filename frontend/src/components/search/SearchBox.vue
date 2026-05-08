<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { searchBasic } from '@/api/search'
import { PLACEHOLDER_MLOS } from '@/data/mlos'
import { formatMlo } from '@/utils/format'

const props = defineProps({
  initialQuery:      { type: String,  default: '' },
  initialField:      { type: String,  default: 'all' },
  compact:           { type: Boolean, default: false },
  showSearchOptions: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])
const router = useRouter()

const searchQuery = ref(props.initialQuery)
const searchField = ref(props.initialField)
const driversOnly = ref(false)
const exactMatch  = ref(false)

const showDropdown     = ref(false)
const dropdownProteins = ref([])
const dropdownMlos     = ref([])
const activeIndex      = ref(-1)

let debounceTimer = null

watch(() => props.initialQuery, v => { searchQuery.value = v })
watch(() => props.initialField, v => { searchField.value = v })

// Flat ordered list used for keyboard navigation
const allItems = computed(() => [
  ...dropdownProteins.value.map(p => ({ type: 'protein', data: p })),
  ...dropdownMlos.value.map(m => ({ type: 'mlo', data: m })),
])

watch(searchQuery, val => {
  if (!props.showSearchOptions) return
  clearTimeout(debounceTimer)
  activeIndex.value = -1

  const trimmed = val.trim()
  if (trimmed.length < 2) {
    showDropdown.value = false
    dropdownProteins.value = []
    dropdownMlos.value = []
    return
  }

  debounceTimer = setTimeout(() => fetchSuggestions(trimmed), 300)
})

async function fetchSuggestions(q) {
  const lower = q.toLowerCase()

  dropdownMlos.value = PLACEHOLDER_MLOS.filter(mlo =>
    formatMlo(mlo.unified_mlo).toLowerCase().includes(lower) ||
    mlo.unified_mlo.toLowerCase().includes(lower)
  )

  try {
    const res = await searchBasic(q, 'fuzzy')
    dropdownProteins.value = (res.data.results ?? []).slice(0, 5)
  } catch {
    dropdownProteins.value = []
  }

  showDropdown.value = dropdownProteins.value.length > 0 || dropdownMlos.value.length > 0
}

function closeDropdown() {
  showDropdown.value = false
  activeIndex.value = -1
}

function selectProtein(protein) {
  showDropdown.value = false
  router.push(`/protein/${protein.uniprot_id}`)
}

function selectMlo(mlo) {
  showDropdown.value = false
  router.push({ path: '/results', query: { mlo: mlo.unified_mlo } })
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    if (showDropdown.value && activeIndex.value >= 0) {
      const item = allItems.value[activeIndex.value]
      if (item.type === 'protein') selectProtein(item.data)
      else selectMlo(item.data)
    } else {
      showDropdown.value = false
      handleSearch()
    }
    return
  }
  if (e.key === 'Escape') {
    closeDropdown()
    return
  }
  if (!showDropdown.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, allItems.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, -1)
  }
}

const inputPlaceholder = computed(() => {
  if (searchField.value === 'uniprot_id') return 'e.g. P35637, Q9NR30'
  if (searchField.value === 'gene_name')  return 'e.g. FUS, TDP43, hnRNPA1'
  if (searchField.value === 'mlo')        return 'e.g. stress granule, paraspeckle'
  return 'Search by UniProt accession, gene name, or organelle'
})

function handleSearch() {
  const q = searchQuery.value.trim()
  const payload = { q, field: searchField.value }
  if (driversOnly.value) payload.role = 'driver'
  if (exactMatch.value)  payload.mode = 'exact'
  emit('search', payload)
}
</script>

<template>
  <div :class="['relative', compact ? 'w-full' : 'max-w-3xl mx-auto w-full']">

    <!-- Search input row -->
    <div class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
      <div class="flex items-stretch">
        <select
          v-model="searchField"
          class="bg-gray-50 border-r border-gray-200 text-gray-600 text-sm px-3 py-3 focus:outline-none flex-shrink-0"
        >
          <option value="all">All fields</option>
          <option value="uniprot_id">UniProt Acc</option>
          <option value="gene_name">Gene name</option>
          <option value="mlo">MLO</option>
        </select>

        <input
          v-model="searchQuery"
          type="text"
          :placeholder="inputPlaceholder"
          class="flex-1 px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none min-w-0"
          @keydown="handleKeydown"
          @blur="closeDropdown"
        />

        <!-- Search option chips — home page only -->
        <template v-if="showSearchOptions">
          <div class="flex items-center gap-1.5 px-2 border-l border-gray-100 flex-shrink-0">
            <button
              :class="driversOnly
                ? 'border border-[#185FA5] bg-[#185FA5] rounded-full px-2.5 py-1 text-[11px] text-white flex items-center gap-1.5 cursor-pointer transition-colors whitespace-nowrap'
                : 'border border-gray-200 rounded-full px-2.5 py-1 text-[11px] text-gray-400 flex items-center gap-1.5 cursor-pointer hover:border-gray-300 hover:text-gray-500 transition-colors whitespace-nowrap bg-white'"
              title="Restrict search to LLPS driver proteins"
              @click="driversOnly = !driversOnly"
            >
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="driversOnly ? 'bg-white' : 'bg-gray-300'"></span>
              Drivers only
            </button>
            <button
              :class="exactMatch
                ? 'border border-[#185FA5] bg-[#185FA5] rounded-full px-2.5 py-1 text-[11px] text-white flex items-center gap-1.5 cursor-pointer transition-colors whitespace-nowrap'
                : 'border border-gray-200 rounded-full px-2.5 py-1 text-[11px] text-gray-400 flex items-center gap-1.5 cursor-pointer hover:border-gray-300 hover:text-gray-500 transition-colors whitespace-nowrap bg-white'"
              title="Search for exact term only (e.g. FUS but not FUSED)"
              @click="exactMatch = !exactMatch"
            >
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="exactMatch ? 'bg-white' : 'bg-gray-300'"></span>
              Exact match
            </button>
          </div>
          <div class="border-l border-gray-200 self-stretch"></div>
        </template>

        <button
          class="bg-[#1B3D6F] hover:bg-[#24508F] text-white text-sm font-medium px-5 transition-colors flex-shrink-0"
          @click="handleSearch"
        >
          Search
        </button>
      </div>
    </div>

    <!-- Autocomplete dropdown -->
    <div
      v-if="showDropdown && showSearchOptions"
      class="absolute left-0 right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-80 overflow-y-auto"
    >
      <!-- Proteins group -->
      <template v-if="dropdownProteins.length">
        <div class="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          Proteins
        </div>
        <div
          v-for="(protein, i) in dropdownProteins"
          :key="protein.uniprot_id"
          :class="[
            'flex items-baseline gap-2 px-3 py-2 cursor-pointer transition-colors',
            activeIndex === i ? 'bg-[#EBF3FB]' : 'hover:bg-gray-50'
          ]"
          @mousedown.prevent="selectProtein(protein)"
        >
          <span class="text-sm font-medium text-[#185FA5] truncate">
            {{ protein.protein_name || protein.gene_name || protein.uniprot_id }}
          </span>
          <span class="font-mono text-[11px] text-gray-400 flex-shrink-0">{{ protein.uniprot_id }}</span>
          <span class="text-[11px] text-gray-400 italic truncate flex-shrink-0">{{ protein.organism }}</span>
        </div>
      </template>

      <!-- Organelles group -->
      <template v-if="dropdownMlos.length">
        <div
          :class="[
            'px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider',
            dropdownProteins.length ? 'border-t border-gray-100 mt-1' : ''
          ]"
        >
          Organelles
        </div>
        <div
          v-for="(mlo, i) in dropdownMlos"
          :key="mlo.unified_mlo"
          :class="[
            'flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors',
            activeIndex === dropdownProteins.length + i ? 'bg-[#EBF3FB]' : 'hover:bg-gray-50'
          ]"
          @mousedown.prevent="selectMlo(mlo)"
        >
          <span class="text-sm text-gray-700">{{ formatMlo(mlo.unified_mlo) }}</span>
          <span class="text-[11px] text-gray-400">{{ mlo.protein_count.toLocaleString() }} proteins</span>
        </div>
      </template>
    </div>

  </div>
</template>
