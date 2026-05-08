<script setup>
import { formatCount } from '@/utils/format'
import { useRouter } from 'vue-router'

const router = useRouter()

// TODO: replace with real API data when GET /organisms endpoint is available
// driver_count per organism also requires API support
const PLACEHOLDER_ORGANISMS = [
  { key: 'homo_sapiens',             name: 'Homo sapiens',             protein_count: 8432, driver_count: 412 },
  { key: 'arabidopsis_thaliana',     name: 'Arabidopsis thaliana',     protein_count: 1203, driver_count: 89  },
  { key: 'mus_musculus',             name: 'Mus musculus',             protein_count: 2341, driver_count: 198 },
  { key: 'saccharomyces_cerevisiae', name: 'Saccharomyces cerevisiae', protein_count: 891,  driver_count: 74  },
  { key: 'caenorhabditis_elegans',   name: 'Caenorhabditis elegans',   protein_count: 534,  driver_count: 41  },
  { key: 'bos_taurus',               name: 'Bos taurus',               protein_count: 312,  driver_count: 22  },
  { key: 'drosophila_melanogaster',  name: 'Drosophila melanogaster',  protein_count: 298,  driver_count: 28  },
  { key: 'rattus_norvegicus',        name: 'Rattus norvegicus',        protein_count: 287,  driver_count: 19  },
  { key: 'xenopus_laevis',           name: 'Xenopus laevis',           protein_count: 201,  driver_count: 14  },
]

defineProps({
  stats: { type: Object, default: null }
})
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-3">
      <button
        v-for="org in PLACEHOLDER_ORGANISMS"
        :key="org.key"
        class="flex flex-col items-center gap-1 p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors text-center"
        @click="router.push({ path: '/results', query: { organism: org.name } })"
      >
        <img
          :src="`/src/assets/organisms/${org.key}.svg`"
          :alt="org.name"
          class="w-9 h-9 object-contain opacity-70"
          style="filter: invert(20%) sepia(80%) saturate(600%) hue-rotate(195deg) brightness(80%);"
        />
        <span class="text-xs italic text-gray-600 leading-tight mt-1">{{ org.name }}</span>
        <span class="text-[10px] text-gray-400">{{ formatCount(org.protein_count) }} proteins</span>
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
