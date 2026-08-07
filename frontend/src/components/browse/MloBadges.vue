<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMlos } from '@/api/mlos'
import { formatMlo, formatCount } from '@/utils/format'
import { PLACEHOLDER_MLOS } from '@/data/mlos.js'

const DISPLAY_LIMIT = 20

const mlos = ref(null)
const router = useRouter()

onMounted(async () => {
  try {
    const res = await getMlos()
    const all = res.data.mlos ?? []
    // Sort by protein_count desc, keep top N for the landing page grid
    mlos.value = [...all]
      .sort((a, b) => (b.driver_count ?? 0) - (a.driver_count ?? 0))
      .slice(0, DISPLAY_LIMIT)
  } catch {
    mlos.value = PLACEHOLDER_MLOS
  }
})

// The DB stores categories in Spanish. Map to display color.
function categoryColor(category) {
  const c = (category ?? '').toLowerCase()
  if (c === 'nuclear')                        return 'bg-blue-500'
  if (c === 'citoplasmático' || c === 'citoplasma') return 'bg-amber-400'
  if (c === 'germinal')                       return 'bg-amber-400'
  if (c === 'neuronal')                       return 'bg-amber-300'
  if (c === 'in vitro')                       return 'bg-gray-300'
  // nuclear subtypes
  if (c.includes('nuclear'))                  return 'bg-blue-400'
  // cytoplasmic subtypes
  if (c.includes('cito'))                     return 'bg-amber-300'
  return 'bg-gray-200'
}

function compartmentLabel(category) {
  const c = (category ?? '').toLowerCase()
  if (c === 'nuclear' || c.includes('nuclear')) return 'Nuclear'
  if (c === 'citoplasmático' || c === 'citoplasma' || c === 'germinal' || c === 'neuronal') return 'Cytoplasmic'
  if (c.includes('cito'))                       return 'Cytoplasmic'
  if (c === 'in vitro')                         return 'In vitro'
  return 'Other'
}

function browseMlo(unified_mlo) {
  router.push({ path: '/results', query: { mlo: unified_mlo } })
}
</script>

<template>
  <div class="space-y-4">
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
            <div class="flex items-center gap-1 mb-1">
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="categoryColor(mlo.category)"></span>
              <span class="text-[9px] uppercase tracking-wide text-gray-500 font-medium">
                {{ compartmentLabel(mlo.category) }}
              </span>
            </div>
            <span class="text-xs font-medium text-gray-700 leading-tight">
              {{ formatMlo(mlo.unified_mlo) }}
            </span>
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

    <template v-else>
      <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(148px, 1fr))">
        <div v-for="i in 8" :key="i" class="min-h-[90px] bg-gray-100 rounded-lg animate-pulse"></div>
      </div>
    </template>

    <div class="pt-1">
      <RouterLink to="/mlos" class="text-[#2B6CB0] text-xs hover:underline mt-3 block">
        View all 164 MLOs →
      </RouterLink>
    </div>
  </div>
</template>
