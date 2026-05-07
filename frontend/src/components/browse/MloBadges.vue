<script setup>
import { useRouter } from 'vue-router'
import { formatMlo, formatCount } from '@/utils/format'
import { PLACEHOLDER_MLOS } from '@/data/mlos.js'

const props = defineProps({
  mlos: { type: Array, default: () => PLACEHOLDER_MLOS }
})

const router = useRouter()

function categoryColor(category) {
  const map = {
    cytoplasmic_rnp: 'bg-amber-400',
    cytoplasmic_membraneless: 'bg-amber-300',
    nuclear_body: 'bg-blue-500',
    nuclear_rnp: 'bg-blue-400',
    in_vitro: 'bg-gray-300',
    unclassified: 'bg-gray-200',
  }
  return map[category] ?? 'bg-gray-200'
}

function compartmentLabel(category) {
  const map = {
    cytoplasmic_rnp: 'Cytoplasmic',
    cytoplasmic_membraneless: 'Cytoplasmic',
    nuclear_body: 'Nuclear',
    nuclear_rnp: 'Nuclear',
    in_vitro: 'In vitro',
    unclassified: 'Other',
  }
  return map[category] ?? 'Other'
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
          class="flex flex-col justify-between px-3 py-2.5 rounded-lg border border-gray-200 bg-white hover:border-[#2B7CD8] hover:shadow-sm cursor-pointer transition-all min-h-[90px]"
        >
          <div>
            <div class="flex items-center gap-1 mb-1">
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="categoryColor(mlo.category)"></span>
              <span class="text-[9px] uppercase tracking-wide text-gray-400 font-medium">
                {{ compartmentLabel(mlo.category) }}
              </span>
            </div>
            <span class="text-xs font-medium text-gray-700 leading-tight">
              {{ formatMlo(mlo.unified_mlo) }}
            </span>
          </div>
          <div class="flex items-center gap-2 mt-2">
            <span class="text-[10px] text-gray-400">
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
