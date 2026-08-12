<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMlos } from '@/api/mlos'
import { formatMlo, formatCount } from '@/utils/format'
import { filterMlosByQuery } from '@/utils/mloMatch'
import {
  spatialLocationColor,
  spatialLocationLabel,
  spatialLocationNote,
} from '@/utils/mloAxes.js'
import { PLACEHOLDER_MLOS } from '@/data/mlos.js'

const DISPLAY_LIMIT = 20        // the unfiltered grid: top organelles by drivers
const FILTERED_LIMIT = 30       // a filter can legitimately match many

const allMlos = ref(null)
const filter  = ref('')
const router = useRouter()

onMounted(async () => {
  try {
    const res = await getMlos()
    allMlos.value = res.data.mlos ?? []
  } catch {
    allMlos.value = PLACEHOLDER_MLOS
  }
})

const byDrivers = computed(() =>
  [...(allMlos.value ?? [])].sort((a, b) => (b.driver_count ?? 0) - (a.driver_count ?? 0))
)

// Filtering searches all organelles, not just the ones the grid happens to be
// showing: 88% of the vocabulary sits outside the top 20.
const matches = computed(() => filterMlosByQuery(byDrivers.value, filter.value))

const mlos = computed(() =>
  matches.value.slice(0, filter.value.trim() ? FILTERED_LIMIT : DISPLAY_LIMIT)
)

const totalCount = computed(() => allMlos.value?.length ?? 0)
const hiddenCount = computed(() => Math.max(0, matches.value.length - mlos.value.length))

// The compartment line reads `spatial_location` directly (see utils/mloAxes.js).
// It used to map the DB's Spanish `category` here, which forced every lineage,
// cell-type and process value — Germinal, Neuronal, Autofagia — into "Cytoplasmic"
// or "Other". The axis says where the organelle is and nothing else, so no
// guessing is left to do at this layer.

function browseMlo(unified_mlo) {
  router.push({ path: '/results', query: { mlo: unified_mlo } })
}
</script>

<template>
  <div class="space-y-4">

    <!-- Filter. Matches the unified name and every name the source databases
         use for it, so "GW-body" finds P body. -->
    <div class="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 bg-white max-w-md">
      <i class="ti ti-search text-gray-400 text-sm"></i>
      <input
        v-model="filter"
        type="text"
        placeholder="Filter organelles — try GW-body, foci, nucleolus"
        class="text-sm text-gray-800 placeholder-gray-400 border-none outline-none w-full bg-transparent"
      />
      <button
        v-if="filter"
        class="text-gray-400 hover:text-gray-600 text-xs flex-shrink-0"
        title="Clear filter"
        @click="filter = ''"
      >✕</button>
    </div>

    <template v-if="mlos && mlos.length">
      <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(148px, 1fr))">
        <div
          v-for="mlo in mlos"
          :key="mlo.unified_mlo"
          @click="browseMlo(mlo.unified_mlo)"
          :title="`Click to browse ${formatMlo(mlo.unified_mlo)} proteins in database`"
          class="flex flex-col justify-between px-3 py-2.5 rounded-lg border border-gray-200 bg-white hover:border-[#2B7CD8] hover:shadow-sm cursor-pointer transition-all min-h-[90px]"
        >
          <div>
            <div class="flex items-center gap-1 mb-1" :title="spatialLocationNote(mlo)">
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="spatialLocationColor(mlo.spatial_location)"></span>
              <span class="text-[9px] uppercase tracking-wide text-gray-500 font-medium">
                {{ spatialLocationLabel(mlo.spatial_location) }}
              </span>
            </div>
            <span class="text-xs font-medium text-gray-700 leading-tight">
              {{ formatMlo(mlo.unified_mlo) }}
            </span>
            <!-- Only the aliases that produced this hit. Without them, a card
                 lighting up for a name it does not display reads as a bug. -->
            <div
              v-if="mlo.matchedNames?.length"
              class="text-[10px] text-gray-500 leading-tight mt-0.5"
            >
              {{ mlo.matchedNames.slice(0, 2).join(' · ') }}<span
                v-if="mlo.matchedNames.length > 2"
              > +{{ mlo.matchedNames.length - 2 }}</span>
            </div>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <span class="text-[10px] text-gray-500">
              {{ formatCount(mlo.protein_count) }} proteins
            </span>
            <span v-if="mlo.driver_count != null" class="text-[10px] text-[#185FA5]">
              {{ formatCount(mlo.driver_count) }} drivers
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- A filter that matches nothing is a result, not a loading state -->
    <template v-else-if="allMlos && filter.trim()">
      <div class="text-sm text-[#484E59] py-6">
        No organelle matches “{{ filter }}”.
      </div>
    </template>

    <template v-else>
      <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(148px, 1fr))">
        <div v-for="i in 8" :key="i" class="min-h-[90px] bg-gray-100 rounded-lg animate-pulse"></div>
      </div>
    </template>

    <div class="pt-1 flex items-center gap-3">
      <RouterLink to="/mlos" class="text-[#2B6CB0] text-xs hover:underline">
        View all{{ totalCount ? ` ${totalCount}` : '' }} MLOs →
      </RouterLink>
      <span v-if="hiddenCount" class="text-xs text-[#484E59]">
        {{ hiddenCount }} more match{{ hiddenCount === 1 ? 'es' : '' }} — refine or view all
      </span>
    </div>
  </div>
</template>
