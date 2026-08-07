<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { searchBasic } from '@/api/search'
import { getMlos } from '@/api/mlos'
import { formatMlo } from '@/utils/format'

/**
 * Two targets instead of a field <select>.
 *
 * The select let you narrow a text search to one column, and narrowing is
 * exactly what broke it: "kinase" matches 50 proteins by protein_name and zero
 * by gene_name, so any narrowing turned a good search into an empty one. The
 * Protein target therefore always searches accession + gene name + protein
 * name together, with no sub-options.
 *
 * The MLO target is not a text search at all. The vocabulary is a closed list
 * of ~170 entries the API hands over whole, so picking from it is exact by
 * construction — no slug/space normalization, no guessing whether a typed
 * string "is" an organelle name.
 */

const props = defineProps({
  initialQuery:      { type: String,  default: '' },
  initialTarget:     { type: String,  default: 'protein' },   // 'protein' | 'mlo'
  compact:           { type: Boolean, default: false },
  showSearchOptions: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])
const router = useRouter()

const searchQuery = ref(props.initialQuery)
const target      = ref(props.initialTarget)
const driversOnly = ref(false)
const exactMatch  = ref(false)

const showDropdown     = ref(false)
const dropdownProteins = ref([])
const activeIndex      = ref(-1)

// Full MLO vocabulary, fetched once the MLO tab is first opened.
const mloVocabulary = ref([])
const mlosLoaded    = ref(false)

let debounceTimer = null

watch(() => props.initialQuery,  v => { searchQuery.value = v })
watch(() => props.initialTarget, v => { target.value = v })

const isMlo = computed(() => target.value === 'mlo')

// ─── MLO target: filter the known list, never a free-text query ──────────────
async function loadMlos() {
  if (mlosLoaded.value) return
  mlosLoaded.value = true
  try {
    const res = await getMlos()
    mloVocabulary.value = res.data?.mlos ?? res.data?.items ?? res.data ?? []
  } catch {
    mloVocabulary.value = []
    mlosLoaded.value = false   // let a later attempt retry
  }
}

const filteredMlos = computed(() => {
  if (!isMlo.value) return []
  const q = searchQuery.value.trim().toLowerCase()
  const list = mloVocabulary.value
  if (!q) return list.slice(0, 12)
  const matches = list.filter(m =>
    m.unified_mlo.toLowerCase().includes(q) ||
    formatMlo(m.unified_mlo).toLowerCase().includes(q) ||
    m.unified_mlo.replace(/_/g, ' ').toLowerCase().includes(q)
  )
  return matches.slice(0, 12)
})

async function selectTarget(next) {
  if (target.value === next) return
  target.value = next
  activeIndex.value = -1
  dropdownProteins.value = []
  if (next === 'mlo') {
    exactMatch.value = false      // meaningless when picking from a list
    await loadMlos()
    showDropdown.value = true
  } else {
    showDropdown.value = false
  }
}

// ─── Flat list used for keyboard navigation ─────────────────────────────────
const allItems = computed(() =>
  isMlo.value
    ? filteredMlos.value.map(m => ({ type: 'mlo', data: m }))
    : dropdownProteins.value.map(p => ({ type: 'protein', data: p }))
)

watch(searchQuery, val => {
  activeIndex.value = -1

  if (isMlo.value) {
    showDropdown.value = true    // filtering is local, no debounce needed
    return
  }

  if (!props.showSearchOptions) return
  clearTimeout(debounceTimer)

  const trimmed = val.trim()
  if (trimmed.length < 2) {
    showDropdown.value = false
    dropdownProteins.value = []
    return
  }

  debounceTimer = setTimeout(() => fetchSuggestions(trimmed), 300)
})

async function fetchSuggestions(q) {
  try {
    const res = await searchBasic(q, 'fuzzy')
    dropdownProteins.value = (res.data.proteins ?? []).slice(0, 5)
  } catch {
    dropdownProteins.value = []
  }
  showDropdown.value = dropdownProteins.value.length > 0
}

function closeDropdown() {
  showDropdown.value = false
  activeIndex.value = -1
}

function openDropdown() {
  if (isMlo.value) showDropdown.value = true
}

function selectProtein(protein) {
  showDropdown.value = false
  router.push(`/protein/${protein.uniprot_id}`)
}

function selectMlo(mlo) {
  showDropdown.value = false
  searchQuery.value = formatMlo(mlo.unified_mlo)
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
  if (e.key === 'Escape') { closeDropdown(); return }
  if (!showDropdown.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, allItems.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, -1)
  }
}

const inputPlaceholder = computed(() =>
  isMlo.value
    ? 'Pick an organelle — e.g. stress granule, paraspeckle, nucleolus'
    : 'Search by UniProt accession, gene name, or protein name'
)

function handleSearch() {
  if (isMlo.value) {
    // No free-text MLO search: commit to a real vocabulary entry or do nothing.
    const pick = filteredMlos.value[0]
    if (pick) selectMlo(pick)
    return
  }
  const q = searchQuery.value.trim()
  const payload = { q, target: 'protein' }
  if (driversOnly.value) payload.role = 'driver'
  if (exactMatch.value)  payload.mode = 'exact'
  emit('search', payload)
}

// Arriving already on the MLO tab (e.g. ?mlo=... in the URL) needs the list.
if (props.initialTarget === 'mlo') loadMlos()
</script>

<template>
  <div :class="['relative', compact ? 'w-full' : 'max-w-3xl mx-auto w-full']">

    <!-- Target tabs -->
    <div class="flex items-end gap-1 pl-1">
      <button
        v-for="tab in [{ id: 'protein', label: 'Protein' }, { id: 'mlo', label: 'MLO' }]"
        :key="tab.id"
        :class="[
          'px-4 py-1.5 text-xs font-medium rounded-t-md border border-b-0 transition-colors',
          target === tab.id
            ? 'bg-white text-[#1B3D6F] border-gray-200'
            : 'bg-transparent text-[#484E59] border-transparent hover:text-[#185FA5]'
        ]"
        @click="selectTarget(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Search input row -->
    <div class="bg-white rounded-lg rounded-tl-none shadow-md border border-gray-200 overflow-hidden">
      <div class="flex items-stretch">
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="inputPlaceholder"
          class="flex-1 px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none min-w-0"
          @keydown="handleKeydown"
          @focus="openDropdown"
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
            <!-- Exact match is meaningless when picking from a closed list -->
            <button
              v-if="!isMlo"
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

    <!-- Dropdown: protein suggestions, or the organelle picker -->
    <div
      v-if="showDropdown && (isMlo || showSearchOptions)"
      class="absolute left-0 right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-80 overflow-y-auto"
    >
      <!-- Proteins -->
      <template v-if="!isMlo && dropdownProteins.length">
        <div class="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
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
          <span class="font-mono text-[11px] text-gray-500 flex-shrink-0">{{ protein.uniprot_id }}</span>
          <span class="text-[11px] text-gray-500 italic truncate flex-shrink-0">{{ protein.organism }}</span>
        </div>
      </template>

      <!-- Organelles -->
      <template v-if="isMlo">
        <div class="px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
          Organelles
        </div>
        <div
          v-for="(mlo, i) in filteredMlos"
          :key="mlo.unified_mlo"
          :class="[
            'flex items-baseline gap-2 px-3 py-2 cursor-pointer transition-colors',
            activeIndex === i ? 'bg-[#EBF3FB]' : 'hover:bg-gray-50'
          ]"
          @mousedown.prevent="selectMlo(mlo)"
        >
          <span class="text-sm text-gray-800">{{ formatMlo(mlo.unified_mlo) }}</span>
          <span v-if="mlo.protein_count != null" class="text-[11px] text-gray-500 flex-shrink-0">
            {{ mlo.protein_count.toLocaleString() }} proteins
          </span>
          <span v-if="mlo.category" class="text-[11px] text-gray-400 flex-shrink-0 ml-auto">{{ mlo.category }}</span>
        </div>
        <div v-if="!filteredMlos.length" class="px-3 py-3 text-xs text-[#484E59]">
          {{ mloVocabulary.length ? 'No organelle matches that name.' : 'Loading organelles…' }}
        </div>
      </template>
    </div>

  </div>
</template>
