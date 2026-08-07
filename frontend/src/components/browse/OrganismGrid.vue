<script setup>
import { computed } from 'vue'
import { formatCount, formatOrganism } from '@/utils/format'
import { useRouter } from 'vue-router'

const router = useRouter()

// key -> icon slug only. Counts come live from props.stats (GET /stats), never hardcoded --
// by_organism keys can carry a "(strain ...)" suffix (e.g. S. cerevisiae), so lookups match
// through formatOrganism() rather than an exact string.
const ORGANISM_META = [
  { key: 'homo_sapiens',             name: 'Homo sapiens' },
  { key: 'mus_musculus',             name: 'Mus musculus' },
  { key: 'arabidopsis_thaliana',     name: 'Arabidopsis thaliana' },
  { key: 'caenorhabditis_elegans',   name: 'Caenorhabditis elegans' },
  { key: 'saccharomyces_cerevisiae', name: 'Saccharomyces cerevisiae' },
  { key: 'xenopus_laevis',           name: 'Xenopus laevis' },
  { key: 'bos_taurus',               name: 'Bos taurus' },
  { key: 'drosophila_melanogaster',  name: 'Drosophila melanogaster' },
  { key: 'rattus_norvegicus',        name: 'Rattus norvegicus' },
]

const props = defineProps({
  stats: { type: Object, default: null }
})

function lookup(dict, name) {
  if (!dict) return null
  if (dict[name] != null) return dict[name]
  const match = Object.keys(dict).find(k => formatOrganism(k) === name)
  return match ? dict[match] : null
}

const organisms = computed(() => {
  const byOrganism = props.stats?.proteins?.by_organism ?? null
  const byDrivers  = props.stats?.proteins?.by_organism_drivers ?? null
  return ORGANISM_META.map(org => ({
    ...org,
    protein_count: lookup(byOrganism, org.name),
    driver_count:  lookup(byDrivers, org.name),
  }))
})
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-3">
      <button
        v-for="org in organisms"
        :key="org.key"
        class="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors text-center"
        :title="`Click to browse ${org.name} proteins in database`"
        @click="router.push({ path: '/results', query: { organism: org.name } })"
      >
        <img
          :src="`/organisms/${org.key}.svg`"
          :alt="org.name"
          class="w-9 h-9 object-contain opacity-70"
          style="filter: invert(20%) sepia(80%) saturate(600%) hue-rotate(195deg) brightness(80%);"
        />
        <span class="text-xs italic text-gray-600 leading-tight mt-1">{{ org.name }}</span>
        <span class="text-[10px] text-gray-500">{{ formatCount(org.protein_count) }} proteins</span>
        <span class="text-[10px] text-[#185FA5]">{{ formatCount(org.driver_count) }} drivers</span>
      </button>
    </div>

    <RouterLink to="/results" class="text-[#2B6CB0] text-xs hover:underline block">
      <template v-if="stats?.proteins?.total_organisms">
        View all {{ formatCount(stats.proteins.total_organisms) }} organisms →
      </template>
      <template v-else>View all organisms →</template>
    </RouterLink>
  </div>
</template>
