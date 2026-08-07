<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { searchBasic } from '@/api/search'

/**
 * One input, one corpus: UniProt accession, gene name and protein name at
 * once. No field select and no target tabs.
 *
 * The select was removed because narrowing to one column is what broke the
 * search — "kinase" matches 50 proteins by protein_name and none by gene_name.
 * The MLO tab that briefly replaced it was removed for a different reason:
 * both of its tabs searched proteins, so the split named the wrong thing.
 * Organelles are now browsed, not searched — the filterable card grid on the
 * home page and /mlos, which land on ?mlo=<slug>.
 */

const props = defineProps({
  initialQuery:      { type: String,  default: '' },
  compact:           { type: Boolean, default: false },
  showSearchOptions: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])
const router = useRouter()

const searchQuery = ref(props.initialQuery)
const driversOnly = ref(false)
const exactMatch  = ref(false)

const showDropdown     = ref(false)
const dropdownProteins = ref([])
const activeIndex      = ref(-1)

let debounceTimer = null

watch(() => props.initialQuery, v => { searchQuery.value = v })

watch(searchQuery, val => {
  if (!props.showSearchOptions) return
  clearTimeout(debounceTimer)
  activeIndex.value = -1

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

function selectProtein(protein) {
  showDropdown.value = false
  router.push(`/protein/${protein.uniprot_id}`)
}

function handleKeydown(e) {
  if (e.key === 'Enter') {
    if (showDropdown.value && activeIndex.value >= 0) {
      selectProtein(dropdownProteins.value[activeIndex.value])
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
    activeIndex.value = Math.min(activeIndex.value + 1, dropdownProteins.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, -1)
  }
}

function handleSearch() {
  const q = searchQuery.value.trim()
  const payload = { q }
  if (driversOnly.value) payload.role = 'driver'
  if (exactMatch.value)  payload.mode = 'exact'
  emit('search', payload)
}

const chipClass = (on) => on
  ? 'border border-[#185FA5] bg-[#185FA5] rounded-full px-2.5 py-1 text-[11px] text-white flex items-center gap-1.5 cursor-pointer transition-colors whitespace-nowrap'
  : 'border border-gray-200 rounded-full px-2.5 py-1 text-[11px] text-gray-400 flex items-center gap-1.5 cursor-pointer hover:border-gray-300 hover:text-gray-500 transition-colors whitespace-nowrap bg-white'
</script>

<template>
  <div :class="['relative', compact ? 'w-full' : 'max-w-3xl mx-auto w-full']">

    <!-- Search input row -->
    <div class="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
      <div class="flex items-stretch">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search by UniProt accession, gene or protein name"
          class="flex-1 px-4 py-3 text-sm text-gray-800 placeholder:text-xs placeholder-gray-400 focus:outline-none min-w-0"
          @keydown="handleKeydown"
          @blur="closeDropdown"
        />

        <!-- Search option chips — home page only -->
        <template v-if="showSearchOptions">
          <div class="flex items-center gap-1.5 px-2 border-l border-gray-100 flex-shrink-0">
            <button
              :class="chipClass(driversOnly)"
              title="Restrict search to LLPS driver proteins"
              @click="driversOnly = !driversOnly"
            >
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="driversOnly ? 'bg-white' : 'bg-gray-300'"></span>
              Drivers only
            </button>
            <button
              :class="chipClass(exactMatch)"
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

    <!-- Protein suggestions -->
    <div
      v-if="showDropdown && showSearchOptions && dropdownProteins.length"
      class="absolute left-0 right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-80 overflow-y-auto"
    >
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
    </div>

  </div>
</template>
