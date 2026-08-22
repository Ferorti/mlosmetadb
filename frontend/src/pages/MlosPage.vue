<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-ink">Membraneless Organelles</h1>
      <p class="text-sm text-ink3 mt-1">Browse all MLOs curated in the database</p>
    </div>

    <!-- Filter bar -->
    <div class="bg-surface border border-border px-4 py-3 mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
      <!-- Text search -->
      <div class="flex items-center gap-2 min-w-[180px]">
        <i class="ti ti-search text-gray-400 text-sm"></i>
        <input
          v-model="textFilter"
          type="text"
          placeholder="Search organelles…"
          class="text-sm text-gray-800 placeholder-gray-400 border-none outline-none w-full"
        />
      </div>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- One dropdown per classification axis. They conjoin, which is the point
           of splitting `category` into four: "nuclear AND stress-induced" was not
           a question the single column could ask. -->
      <select
        v-for="axis in AXIS_FILTERS"
        :key="axis.key"
        v-model="axisFilters[axis.key]"
        :title="`Filter by ${axis.label.toLowerCase()}`"
        class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:border-brand"
      >
        <option value="">{{ axis.allLabel }}</option>
        <option v-for="v in axisOptions[axis.key]" :key="v" :value="v">{{ axis.format(v) }}</option>
      </select>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Source DB toggle chips -->
      <div class="flex items-center gap-1.5 flex-wrap">
        <span class="text-xs text-gray-500">Source:</span>
        <button
          v-for="db in SOURCE_DBS"
          :key="db"
          @click="toggleSourceDb(db)"
          :class="[
            'text-xs px-2 py-0.5 rounded-full border transition-colors',
            selectedSources.includes(db)
              ? 'bg-brand text-white border-brand'
              : 'bg-white text-gray-600 border-gray-300 hover:border-brand hover:text-brand',
          ]"
        >
          {{ db }}
        </button>
      </div>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Organism placeholder -->
      <select
        disabled
        class="text-sm text-gray-400 border border-gray-200 rounded px-2 py-1 bg-gray-50 cursor-not-allowed"
      >
        <option>Organism — coming soon</option>
      </select>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Sort control -->
      <select
        v-model="sortBy"
        class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:border-brand"
      >
        <option value="drivers">Most drivers</option>
        <option value="alphabetical">Alphabetical</option>
        <option value="protein_count">Most proteins</option>
      </select>

      <!-- Count display -->
      <div class="ml-auto text-xs text-gray-500 whitespace-nowrap">
        Showing
        <span class="font-medium text-gray-700">{{ filtered.length }}</span>
        of
        <span class="font-medium text-gray-700">{{ totalCount }}</span>
        MLOs
      </div>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Error -->
    <div v-else-if="error" class="text-center py-16 text-sm text-red-500">
      Failed to load MLOs. Please try again.
    </div>

    <!-- Empty state -->
    <div v-else-if="filtered.length === 0" class="text-center py-16 text-sm text-gray-500">
      No organelles match your filters. Try removing some filters.
    </div>

    <!-- MLO list -->
    <div v-else class="bg-surface border border-border overflow-hidden">
      <div
        v-for="mlo in filtered"
        :key="mlo.unified_mlo"
        class="px-5 py-4 border-b border-border-soft last:border-b-0 hover:bg-page cursor-pointer transition-colors"
        :title="expandedRows.has(mlo.unified_mlo) ? 'Click to collapse' : 'Click to expand'"
        @click="toggleExpand(mlo.unified_mlo)"
      >
        <!-- Line 1: name + axis badges -->
        <div class="flex items-start justify-between gap-4">
          <span class="text-[16px] font-medium text-gray-800">
            {{ formatMlo(mlo.unified_mlo) }}
            <!-- Only when the hit came from a name the title does not show,
                 otherwise the row looks like a mismatch. -->
            <span
              v-if="mlo.matchedNames?.length"
              class="text-xs text-gray-500 font-normal ml-1"
            >{{ mlo.matchedNames.slice(0, 3).join(' · ')
              }}<template v-if="mlo.matchedNames.length > 3"> +{{ mlo.matchedNames.length - 3 }}</template></span>
          </span>
          <!-- Line 1 badges: the axes that are always populated. Location carries
               a dashed border when its value is the audit's hand assignment
               rather than a derivation, so a provisional value never reads as
               settled (R3-OWN-spatial-56). -->
          <div class="shrink-0 flex items-center gap-1.5 flex-wrap justify-end">
            <span
              v-if="mlo.spatial_location"
              :title="spatialLocationNote(mlo) || `Location: ${spatialLocationLabel(mlo.spatial_location)}`"
              class="text-xs px-2 py-0.5 rounded-full bg-page text-ink3 border flex items-center gap-1"
              :class="isSpatialLocationProvisional(mlo) ? 'border-border-strong border-dashed' : 'border-border'"
            >
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="spatialLocationColor(mlo.spatial_location)"></span>
              {{ spatialLocationLabel(mlo.spatial_location) }}
              <span v-if="isSpatialLocationProvisional(mlo)" class="text-muted">·&nbsp;provisional</span>
            </span>
            <span
              v-if="mlo.physiological_state && mlo.physiological_state !== 'constitutive'"
              class="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-[#854F0B] border border-amber-200"
            >
              {{ physiologicalStateLabel(mlo.physiological_state) }}
            </span>
            <span
              v-if="mlo.cell_type_context"
              class="text-xs px-2 py-0.5 rounded-full bg-teal-50 text-[#0F6E56] border border-teal-200"
            >
              {{ cellTypeContextLabel(mlo.cell_type_context) }}
            </span>
          </div>
        </div>

        <!-- Line 2: protein · driver counts · taxonomic scope -->
        <div class="mt-1 text-sm text-gray-600 flex items-baseline flex-wrap gap-x-1.5">
          <span>
            {{ formatCount(mlo.protein_count) }} proteins ·
            <span class="text-brand">{{ formatCount(mlo.driver_count) }} drivers</span>
          </span>
          <!-- The taxonomic axis is derived from the organisms of the annotated
               proteins, so it describes the dataset and not the organelle. The
               support count travels with it, and a thin one is marked: the audit
               asked for exactly this (63 of 177 terms rest on <=2 proteins). -->
          <span v-if="mlo.taxonomic_scope" class="text-gray-600" :title="taxonomicScopeNote(mlo)">
            · {{ taxonomicScopeLabel(mlo.taxonomic_scope) }}
            <span :class="isTaxonomicScopeThin(mlo) ? 'text-regulator' : 'text-gray-500'" class="text-xs">
              ({{ mlo.taxonomic_support_n }}
              protein{{ mlo.taxonomic_support_n === 1 ? '' : 's' }}<template v-if="isTaxonomicScopeThin(mlo)">, thin</template>)
            </span>
          </span>
        </div>

        <!-- Line 3: source DBs -->
        <div v-if="mlo.sources && mlo.sources.length" class="mt-0.5 text-xs text-gray-400">
          {{ mlo.sources.join(' · ') }}
        </div>

        <!-- Line 4: truncated definition + expand toggle -->
        <div class="mt-1.5 flex items-start justify-between gap-3">
          <p
            v-if="!expandedRows.has(mlo.unified_mlo) && firstDefinition(mlo)"
            class="text-sm text-gray-600 flex-1 leading-snug"
          >
            {{ truncate(firstDefinition(mlo), 120) }}
          </p>
          <div v-else-if="!expandedRows.has(mlo.unified_mlo)" class="flex-1"></div>

          <button
            @click.stop="navigateToMlo(mlo.unified_mlo)"
            class="shrink-0 flex items-center gap-0.5 text-xs text-brand hover:text-blue-700 mt-0.5"
          >
            <i class="ti ti-arrow-right"></i>
            Explore {{ formatMlo(mlo.unified_mlo) }} proteins
          </button>
        </div>

        <!-- Expanded definitions -->
        <div
          v-if="expandedRows.has(mlo.unified_mlo)"
          class="mt-3 pt-3 border-t border-gray-100 space-y-3"
          @click.stop
        >
          <div v-for="def in mlo.definitions" :key="def.source_db">
            <div class="flex items-baseline gap-2 mb-0.5">
              <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{{ def.source_db }}</span>
              <span v-if="def.source_name" class="text-xs text-gray-500 italic">{{ def.source_name }}</span>
            </div>
            <p v-if="def.definition" class="text-sm text-gray-700 leading-snug">{{ def.definition }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getMlos } from '@/api/mlos.js'
import { formatMlo, formatCount } from '@/utils/format.js'
import { filterMlosByQuery } from '@/utils/mloMatch.js'
import {
  AXIS_FILTERS,
  axisValues,
  cellTypeContextLabel,
  isSpatialLocationProvisional,
  isTaxonomicScopeThin,
  physiologicalStateLabel,
  spatialLocationColor,
  spatialLocationLabel,
  spatialLocationNote,
  taxonomicScopeLabel,
  taxonomicScopeNote,
} from '@/utils/mloAxes.js'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const router = useRouter()

const SOURCE_DBS = ['PhaSepDB', 'DrLLPS', 'PhasePro', 'LLPSDB', 'CDCODE']

function firstDefinition(mlo) {
  return mlo.definitions?.[0]?.definition ?? ''
}

function truncate(str, n) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n).trimEnd() + '…' : str
}

const mlos = ref([])
const loading = ref(true)
const error = ref(false)
const textFilter = ref('')
// One selection per axis, all '' by default. Filtering client-side (the whole
// vocabulary is 176 rows and already in memory) rather than re-querying /mlos per
// axis, which is what the API's axis params are for when a caller does not have
// the list — see api/mlos.js.
const axisFilters = reactive(Object.fromEntries(AXIS_FILTERS.map(a => [a.key, ''])))
const selectedSources = ref([])
const sortBy = ref('drivers')
const expandedRows = ref(new Set())

function toggleSourceDb(db) {
  const idx = selectedSources.value.indexOf(db)
  if (idx >= 0) {
    selectedSources.value.splice(idx, 1)
  } else {
    selectedSources.value.push(db)
  }
}

function toggleExpand(mloId) {
  const next = new Set(expandedRows.value)
  if (next.has(mloId)) {
    next.delete(mloId)
  } else {
    next.add(mloId)
  }
  expandedRows.value = next
}

function navigateToMlo(unifiedMlo) {
  router.push({ path: '/results', query: { mlo: unifiedMlo } })
}

// Options come from the data, so an axis value added upstream shows up in the
// dropdown without a frontend change — and an axis nobody uses yet renders as a
// lone "Any …" option instead of a broken control.
const axisOptions = computed(() =>
  Object.fromEntries(AXIS_FILTERS.map(a => [a.key, axisValues(mlos.value, a.key)]))
)

const totalCount = computed(() => mlos.value.length)

const filtered = computed(() => {
  let result = mlos.value

  // Same matcher as the home grid: reads the unified name and every name the
  // source databases use, so "GW-body" finds P body here too. The old test
  // compared against the raw slug, so even "stress granule" with a space
  // missed stress_granule.
  result = filterMlosByQuery(result, textFilter.value)

  for (const axis of AXIS_FILTERS) {
    const value = axisFilters[axis.key]
    if (value) result = result.filter(m => m[axis.key] === value)
  }

  if (selectedSources.value.length) {
    result = result.filter(m =>
      selectedSources.value.some(db =>
        m.sources && m.sources.some(s => s.toLowerCase() === db.toLowerCase())
      )
    )
  }

  if (sortBy.value === 'alphabetical') {
    return [...result].sort((a, b) => formatMlo(a.unified_mlo).localeCompare(formatMlo(b.unified_mlo)))
  }

  const countKey = sortBy.value === 'protein_count' ? 'protein_count' : 'driver_count'
  return [...result].sort((a, b) => {
    const diff = (b[countKey] ?? 0) - (a[countKey] ?? 0)
    if (diff !== 0) return diff
    return formatMlo(a.unified_mlo).localeCompare(formatMlo(b.unified_mlo))
  })
})

onMounted(async () => {
  try {
    const res = await getMlos()
    mlos.value = res.data.mlos ?? []
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>
