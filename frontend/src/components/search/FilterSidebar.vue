<script setup>
import { ref, computed } from 'vue'
import { formatMlo, formatCount, formatOrganism } from '@/utils/format'
import { PLACEHOLDER_MLOS } from '@/data/mlos.js'
import statsData from '@/data/stats.json'
import { searchOrganisms } from '@/api/proteins'

const props = defineProps({
  filters:    { type: Object,  default: () => ({}) },
  facets:     { type: Object,  default: null },
  mobileOpen: { type: Boolean, default: false },
})

// TODO: facets require API extension — GET /search/facets endpoint
// with same params as /search/advanced, returning per-value counts.
// Until then, facets prop is null and counts are not shown.

const emit = defineEmits(['update:filters', 'reset-filters', 'close'])

const open = ref({ role: true, organelle: true, organism: true, features: false })

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

const roleOptions = computed(() => {
  const all = [{ v: 'driver', l: 'Driver' }, { v: 'component', l: 'MLO component' }]
  if (!props.facets?.by_role) return all
  return all.filter(opt => props.facets.by_role[opt.v] != null)
})

const featureTypeOptions = [
  { value: 'IDR',         label: 'Intrinsically disordered region' },
  { value: 'LCD',         label: 'Low complexity domain'           },
  { value: 'domain',      label: 'PFAM domain'                     },
  { value: 'coiled_coil', label: 'Coiled coil'                     },
  { value: 'MoRF',        label: 'Molecular recognition feature'   },
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
const orgSearchResults = ref([])

const displayedOrgs = computed(() => {
  if (props.facets?.by_organism) {
    return Object.entries(props.facets.by_organism)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([name, count]) => ({ value: name, label: formatOrganism(name), count }))
  }
  return allOrganisms.slice(0, 12).map(name => ({ value: name, label: formatOrganism(name), count: null }))
})

async function onOrganismSearch() {
  if (orgSearch.value.length < 3) {
    orgSearchResults.value = []
    return
  }
  try {
    const res = await searchOrganisms(orgSearch.value)
    orgSearchResults.value = res.data.results ?? []
  } catch {
    orgSearchResults.value = []
  }
}

// ---- Molecular features multi-select ----
const activeFeatureTypes = computed(() => {
  const val = props.filters.feature_type
  if (!val) return []
  return Array.isArray(val) ? val : val.split(',')
})

function toggleFeatureType(value) {
  const current = activeFeatureTypes.value
  const updated = current.includes(value)
    ? current.filter(v => v !== value)
    : [...current, value]
  const newFilters = { ...props.filters }
  if (updated.length === 0) {
    delete newFilters.feature_type
  } else {
    // TODO: API needs to support feature_type as array for multi-select
    newFilters.feature_type = updated.join(',')
  }
  emit('update:filters', { ...newFilters, page: 1 })
}

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
  <!-- Mobile backdrop, dismisses the drawer -->
  <div
    v-if="mobileOpen"
    class="fixed inset-0 bg-black/40 z-40 md:hidden"
    @click="$emit('close')"
  ></div>

  <aside
    class="filter-sidebar bg-white overflow-y-auto border-gray-200 md:static md:z-auto md:block md:w-[220px] md:max-w-none md:flex-shrink-0 md:border-r md:shadow-none"
    :class="mobileOpen
      ? 'fixed inset-y-0 left-0 z-50 w-[85%] max-w-xs border-r shadow-xl'
      : 'hidden'"
  >
    <div class="px-4 py-3 space-y-1">

      <!-- Mobile drawer header -->
      <div class="flex items-center justify-between mb-2 md:hidden">
        <span class="text-sm font-semibold text-gray-800">Filters</span>
        <button
          @click="$emit('close')"
          class="text-gray-400 hover:text-gray-600 p-1 -mr-1"
          aria-label="Close filters"
        >✕</button>
      </div>

      <!-- Header + Reset filters -->
      <div class="flex items-center justify-between mb-3">
        <span class="text-sm font-medium text-gray-700">Filter by:</span>
        <button
          v-if="hasActiveFilters"
          @click="$emit('reset-filters')"
          class="text-xs text-brand hover:underline"
        >
          Reset filters
        </button>
      </div>

      <!-- LLPS role -->
      <div class="border-b border-border-soft pb-3">
        <button
          class="flex items-center justify-between w-full font-mono text-[10.5px] text-ink3 tracking-[0.07em] py-2 border-b border-border pb-[9px]"
          @click="open.role = !open.role"
        >
          LLPS ROLE
          <svg class="w-3.5 h-3.5 text-gray-500 transition-transform" :class="open.role ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.role">
          <!-- Active chip — only when filter is set -->
          <div v-if="filters.role" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E8F1FB] border border-[#BFD7F0] text-brand font-medium">
              {{ filters.role === 'component' ? 'MLO component' : filters.role.charAt(0).toUpperCase() + filters.role.slice(1) }}
              <button @click="removeFilter('role')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.role">
              <label
                v-for="opt in roleOptions"
                :key="opt.v"
                class="flex items-center gap-2 py-1 cursor-pointer text-[13px] text-ink3 hover:text-ink"
              >
                <input type="checkbox" :checked="false" @change="applyFilter('role', opt.v)"
                       class="accent-brand w-[13px] h-[13px] m-0 flex-shrink-0" />
                <span class="flex-1">{{ opt.l }}</span>
                <span v-if="facets?.by_role?.[opt.v] != null" class="font-mono text-[11px] text-muted">{{ facets.by_role[opt.v].toLocaleString() }}</span>
              </label>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Organelle (MLO) -->
      <div class="border-b border-border-soft pb-3">
        <button
          class="flex items-center justify-between w-full font-mono text-[10.5px] text-ink3 tracking-[0.07em] py-2 border-b border-border pb-[9px]"
          @click="open.organelle = !open.organelle"
        >
          ORGANELLE
          <svg class="w-3.5 h-3.5 text-gray-500 transition-transform" :class="open.organelle ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.organelle" class="mt-1">
          <!-- Active chip -->
          <div v-if="filters.mlo" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E8F1FB] border border-[#BFD7F0] text-brand font-medium">
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
                class="w-full text-xs border border-border rounded px-2 py-1 mb-1.5 focus:outline-none focus:border-brand"
              />
              <div>
                <label
                  v-for="mlo in displayedMlos"
                  :key="mlo.value"
                  class="flex items-center gap-2 py-1 cursor-pointer text-[13px] text-ink3 hover:text-ink"
                >
                  <input type="checkbox" :checked="false" @change="applyFilter('mlo', mlo.value)"
                         class="accent-brand w-[13px] h-[13px] m-0 flex-shrink-0" />
                  <span class="flex-1">{{ mlo.label }}</span>
                  <span v-if="mlo.count != null" class="font-mono text-[11px] text-muted">{{ mlo.count.toLocaleString() }}</span>
                </label>
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
      <div class="border-b border-border-soft pb-3">
        <button
          class="flex items-center justify-between w-full font-mono text-[10.5px] text-ink3 tracking-[0.07em] py-2 border-b border-border pb-[9px]"
          @click="open.organism = !open.organism"
        >
          ORGANISM
          <svg class="w-3.5 h-3.5 text-gray-500 transition-transform" :class="open.organism ? '' : 'rotate-180'" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
          </svg>
        </button>
        <div v-if="open.organism" class="mt-1">
          <!-- Active chip -->
          <div v-if="filters.organism" class="mb-1">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E8F1FB] border border-[#BFD7F0] text-brand font-medium">
              <em>{{ formatOrganism(filters.organism) }}</em>
              <button @click="removeFilter('organism')" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove filter">×</button>
            </span>
          </div>
          <!-- Options — fully hidden when filter active -->
          <Transition name="fade">
            <div v-if="!filters.organism">
              <input
                v-model="orgSearch"
                type="text"
                placeholder="Search organisms..."
                class="w-full text-xs border border-border rounded px-2 py-1 mb-1.5 focus:outline-none focus:border-brand"
                @input="onOrganismSearch"
              />
              <!-- API results when query >= 3 chars -->
              <div v-if="orgSearch.length >= 3">
                <label
                  v-for="result in orgSearchResults"
                  :key="result.organism"
                  class="flex items-center gap-2 py-1 cursor-pointer text-[13px] text-ink3 hover:text-ink"
                >
                  <input type="checkbox" :checked="false" @change="applyFilter('organism', result.organism)"
                         class="accent-brand w-[13px] h-[13px] m-0 flex-shrink-0" />
                  <span class="flex-1">{{ result.organism }}</span>
                  <span class="font-mono text-[11px] text-muted">{{ formatCount(result.protein_count) }}</span>
                </label>
                <div v-if="orgSearchResults.length === 0" class="text-[11px] text-gray-500 py-1">
                  No organisms found.
                </div>
              </div>
              <!-- Static top-9 when query is empty or < 3 chars -->
              <div v-else>
                <label
                  v-for="org in displayedOrgs"
                  :key="org.value"
                  class="flex items-center gap-2 py-1 cursor-pointer text-[13px] text-ink3 hover:text-ink"
                >
                  <input type="checkbox" :checked="false" @change="applyFilter('organism', org.value)"
                         class="accent-brand w-[13px] h-[13px] m-0 flex-shrink-0" />
                  <span class="flex-1">{{ org.label }}</span>
                  <span v-if="org.count != null" class="font-mono text-[11px] text-muted">{{ org.count.toLocaleString() }}</span>
                </label>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Molecular features -- hidden 2026-08-24 at the user's request: checking
           two or more feature-type checkboxes at once silently returns zero
           results, because the API only matches feature_type as a single exact
           string (see search_queries.py's `LOWER(sf.feature_type) = LOWER(?)`)
           while this UI joins multiple selections with a comma. The Pfam text
           input (feature_accession) works fine on its own, but the whole
           section is hidden together rather than shipping the broken checkboxes
           next to a still-working field. Script-side logic (featureTypeOptions,
           toggleFeatureType, pfamInput, applyPfam) is left in place for when
           the API is fixed to accept multiple feature_type values -- don't
           delete it as dead code. -->

    </div>
  </aside>
</template>

<style scoped>
.filter-sidebar {
  font-family: 'IBM Plex Sans', sans-serif;
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
