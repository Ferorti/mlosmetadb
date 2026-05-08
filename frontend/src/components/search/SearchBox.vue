<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  initialQuery:      { type: String,  default: '' },
  initialField:      { type: String,  default: 'all' },
  compact:           { type: Boolean, default: false },
  showSearchOptions: { type: Boolean, default: false },
})

const emit = defineEmits(['search'])

const searchQuery = ref(props.initialQuery)
const searchField = ref(props.initialField)
const driversOnly = ref(false)
const exactMatch  = ref(false)

watch(() => props.initialQuery, v => { searchQuery.value = v })
watch(() => props.initialField, v => { searchField.value = v })

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
  <div :class="compact ? 'w-full' : 'max-w-3xl mx-auto w-full'">
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
          @keydown.enter="handleSearch"
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
  </div>
</template>
