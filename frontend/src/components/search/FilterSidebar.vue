<script setup>
import { ref, computed } from 'vue'
import { formatMlo } from '@/utils/format'
import { PLACEHOLDER_MLOS } from '@/data/mlos.js'
import statsData from '@/data/stats.json'

const props = defineProps({
  filters: { type: Object, default: () => ({}) },
  facets:  { type: Object, default: null },
})

// TODO: facets require API extension — GET /search/facets endpoint
// with same params as /search/advanced, returning per-value counts.
// Until then, facets prop is null and counts are not shown.

const emit = defineEmits(['update:filters', 'reset-filters'])

const open = ref({ role: true, organelle: true, organism: true, source: true, features: false })

// Local state only for Pfam domain text input (applied on Enter)
const pfamInput = ref(props.filters.feature_accession ?? '')

// ---- Facets-ready option lists ----

const mloOptions = computed(() => {
  if (props.facets?.by_mlo) {
    return Object.entries(props.facets.by_mlo)
      .sort((a, b) => b[1] - a[1])
      .map(([value, count]) => ({ value, label: formatMlo(value), count }))
  }
  return PLACEHOLDER_MLOS.map(m => ({
    value: m.unified_mlo,
    label: formatMlo(m.unified_mlo),
    count: null,
  }))
})

const allOrganisms = Object.entries(statsData.proteins.by_organism)
  .sort((a, b) => b[1] - a[1])
  .map(([name]) => name)
const totalOrganisms = statsData.proteins.total_organisms

const organismOptions = computed(() => {
  if (props.facets?.by_organism) {
    return Object.entries(props.facets.by_organism)
      .sort((a, b) => b[1] - a[1])
      .map(([value, count]) => ({ value, label: value, count }))
  }
  return allOrganisms.map(name => ({ value: name, label: name, count: null }))
})

const SOURCE_DBS = [
  { label: 'PhaseDB',  value: 'PhaseDB'  },
  { label: 'DrLLPS',   value: 'DrLLPS'   },
  { label: 'PhasePro', value: 'PhasePro' },
  { label: 'LLPSDB',   value: 'LLPSDB'   },
  { label: 'CD-CODE',  value: 'CDCODE'   },
]

const sourceDbOptions = computed(() => {
  return SOURCE_DBS.map(db => ({
    ...db,
    count: props.facets?.by_source_db?.[db.value] ?? null,
  }))
})

const FEATURE_TYPES = [
  { value: 'IDR',           label: 'IDR (disordered region)'   },
  { value: 'LCD',           label: 'LCD (low complexity)'       },
  { value: 'MoRF',          label: 'MoRF (recognition feature)' },
  { value: 'coiled_coil',   label: 'Coiled coil'                },
  { value: 'transmembrane', label: 'Transmembrane'              },
]

// ---- MLO search/expand ----
const mloSearch  = ref('')
const mloShowAll = ref(false)
const filteredMlos = computed(() => {
  const s = mloSearch.value.toLowerCase()
  if (!s) return mloOptions.value
  return mloOptions.value.filter(m =>
    m.value.includes(s) || m.label.toLowerCase().includes(s)
  )
})
const displayedMlos  = computed(() => mloShowAll.value ? filteredMlos.value : filteredMlos.value.slice(0, 8))
const mloHiddenCount = computed(() => Math.max(0, filteredMlos.value.length - 8))

// ---- Organism search/expand ----
const orgSearch  = ref('')
const orgShowAll = ref(false)
const filteredOrgs = computed(() => {
  const s = orgSearch.value.toLowerCase()
  if (!s) return organismOptions.value
  return organismOptions.value.filter(o => o.label.toLowerCase().includes(s))
})
const displayedOrgs  = computed(() => orgShowAll.value ? filteredOrgs.value : filteredOrgs.value.slice(0, 9))
const orgHiddenCount = computed(() => Math.max(0, totalOrganisms - 9))

// ---- Filter state helpers ----
const hasActiveFilters = computed(() => {
  const skip = new Set(['page', 'per_page', 'mode', 'q', 'field'])
  return Object.keys(props.filters).some(k => !skip.has(k) && props.filters[k])
})

function isFilterActive(key) {
  return !!props.filters[key]
}

function applyFilter(key, value) {
  emit('update:filters', { ...props.filters, [key]: value, page: 1 })
}

function removeFilter(key) {
  const updated = { ...props.filters }
  delete updated[key]
  updated.page = 1
  emit('update:filters', updated)
}

function applyPfam() {
  const val = pfamInput.value.trim()
  if (val) {
    applyFilter('feature_accession', val)
  } else {
    removeFilter('feature_accession')
  }
}
</script>

<template>
  <aside class="filter-sidebar w-[220px] flex-shrink-0 border-r border-gray-200 bg-white overflow-y-auto">
    <div class="px-4 py-3 space-y-1">

      <!-- Header + Reset filters -->
      <div class="flex items-center justify-between mb-3">
        <span class="text-sm font-medium text-gray-700">Filter by:</span>
        <button
          v-if="hasActiveFilters"
          @click="$emit('reset-filters')"
          class="text-xs text-[#185FA5] hover:underline"
        >
          Reset filters
        </button>
      </div>

      <!-- LLPS role -->
      <div class="border-b border-gray-100 pb-3">
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.role = !open.role"
        >
          LLPS role
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="open.role ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.role">
          <!-- Active chip — only when filter is set -->
          <div v-if="filters.role" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
              {{ filters.role.charAt(0).toUpperCase() + filters.role.slice(1) }}
              <button @click="removeFilter('role')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.role">
              <div
                v-for="opt in [{ v: 'driver', l: 'Driver' }, { v: 'client', l: 'Client' }, { v: 'unknown', l: 'Unknown' }]"
                :key="opt.v"
                class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-xs text-gray-600"
                @click="applyFilter('role', opt.v)"
              >
                <span>{{ opt.l }}</span>
                <span v-if="facets?.by_role?.[opt.v] != null" class="text-xs text-gray-400">
                  ({{ facets.by_role[opt.v].toLocaleString() }})
                </span>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Organelle (MLO) -->
      <div class="border-b border-gray-100 pb-3">
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.organelle = !open.organelle"
        >
          Organelle
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="open.organelle ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.organelle" class="mt-1">
          <!-- Active chip -->
          <div v-if="filters.mlo" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
              {{ formatMlo(filters.mlo) }}
              <button @click="removeFilter('mlo')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.mlo">
              <input
                v-model="mloSearch"
                type="text"
                placeholder="Filter organelles…"
                class="w-full text-xs border border-gray-200 rounded px-2 py-1 mb-1.5 focus:outline-none focus:border-[#185FA5]"
              />
              <div>
                <div
                  v-for="mlo in displayedMlos"
                  :key="mlo.value"
                  class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-xs text-gray-600"
                  @click="applyFilter('mlo', mlo.value)"
                >
                  <span>{{ mlo.label }}</span>
                  <span v-if="mlo.count != null" class="text-xs text-gray-400">({{ mlo.count.toLocaleString() }})</span>
                </div>
              </div>
              <button
                v-if="!mloShowAll && mloHiddenCount > 0"
                class="text-[10px] text-[#2B6CB0] hover:underline mt-1"
                @click="mloShowAll = true"
              >
                + {{ mloHiddenCount }} more ↓
              </button>
              <button
                v-else-if="mloShowAll"
                class="text-[10px] text-[#2B6CB0] hover:underline mt-1"
                @click="mloShowAll = false"
              >
                ↑ Show less
              </button>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Organism -->
      <div class="border-b border-gray-100 pb-3">
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.organism = !open.organism"
        >
          Organism
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="open.organism ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.organism" class="mt-1">
          <!-- Active chip -->
          <div v-if="filters.organism" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
              <em>{{ filters.organism }}</em>
              <button @click="removeFilter('organism')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.organism">
              <input
                v-model="orgSearch"
                type="text"
                placeholder="Filter organisms…"
                class="w-full text-xs border border-gray-200 rounded px-2 py-1 mb-1.5 focus:outline-none focus:border-[#185FA5]"
              />
              <div>
                <div
                  v-for="org in displayedOrgs"
                  :key="org.value"
                  class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-xs text-gray-600"
                  @click="applyFilter('organism', org.value)"
                >
                  <span class="italic">{{ org.label }}</span>
                  <span v-if="org.count != null" class="text-xs text-gray-400">({{ org.count.toLocaleString() }})</span>
                </div>
              </div>
              <button
                v-if="!orgShowAll && orgHiddenCount > 0"
                class="text-[10px] text-[#2B6CB0] hover:underline mt-1"
                @click="orgShowAll = true"
              >
                + {{ orgHiddenCount }} more ↓
              </button>
              <button
                v-else-if="orgShowAll"
                class="text-[10px] text-[#2B6CB0] hover:underline mt-1"
                @click="orgShowAll = false"
              >
                ↑ Show less
              </button>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Source database -->
      <div class="border-b border-gray-100 pb-3">
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.source = !open.source"
        >
          Source database
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="open.source ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.source">
          <!-- Active chip -->
          <div v-if="filters.source_db" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
              {{ filters.source_db }}
              <button @click="removeFilter('source_db')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.source_db">
              <div
                v-for="db in sourceDbOptions"
                :key="db.value"
                class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-xs text-gray-600"
                @click="applyFilter('source_db', db.value)"
              >
                <span>{{ db.label }}</span>
                <span v-if="db.count != null" class="text-xs text-gray-400">({{ db.count.toLocaleString() }})</span>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Molecular features (collapsed by default) -->
      <div class="border-b border-gray-100 pb-3">
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.features = !open.features"
        >
          Molecular features
          <svg class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="open.features ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.features" class="space-y-0.5 mt-1">
          <!-- Active chip for feature_type -->
          <div v-if="isFilterActive('feature_type')" class="flex items-center gap-1 mb-2">
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5]">
              {{ filters.feature_type }}
              <button @click="removeFilter('feature_type')" class="ml-1 hover:text-[#0C447C] leading-none" aria-label="Remove feature filter">×</button>
            </span>
          </div>
          <div
            v-for="ft in FEATURE_TYPES"
            :key="ft.value"
            class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-xs text-gray-600 transition-opacity"
            :class="{ 'opacity-30 pointer-events-none': isFilterActive('feature_type') }"
            @click="applyFilter('feature_type', ft.value)"
          >
            <span>{{ ft.label }}</span>
          </div>

          <!-- Pfam domain text input -->
          <div class="mt-2">
            <label class="text-[10px] text-gray-500 font-medium block mb-1">Pfam domain</label>
            <div class="flex gap-1">
              <input
                v-model="pfamInput"
                type="text"
                placeholder="e.g. PF00076 or RRM_1"
                class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-[#185FA5]"
                @keyup.enter="applyPfam"
              />
              <button
                v-if="pfamInput"
                class="text-xs text-white bg-[#1B3D6F] rounded px-2 py-1 hover:bg-[#24508F] transition-colors"
                @click="applyPfam"
              >
                Go
              </button>
            </div>
            <div v-if="isFilterActive('feature_accession')" class="flex items-center gap-1 mt-1.5">
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5]">
                {{ filters.feature_accession }}
                <button @click="removeFilter('feature_accession'); pfamInput = ''" class="ml-1 hover:text-[#0C447C] leading-none" aria-label="Remove Pfam filter">×</button>
              </span>
            </div>
          </div>

          <div class="mt-2 opacity-50">
            <label class="text-[10px] text-gray-500 font-medium block mb-1">
              Disorder content (%)
              <span class="text-gray-400 font-normal ml-1" title="Coming soon — requires API update">ⓘ Coming soon</span>
            </label>
            <input type="range" min="0" max="100" disabled class="w-full cursor-not-allowed" />
          </div>
        </div>
      </div>

    </div>
  </aside>
</template>

<style scoped>
.filter-sidebar {
  font-family: 'IBM Plex Sans', sans-serif;
}
.filter-sidebar :deep(.text-xs.font-semibold) {
  font-weight: 500;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
