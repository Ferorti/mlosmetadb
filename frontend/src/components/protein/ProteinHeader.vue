<script setup>
import { computed } from 'vue'
import RoleBadge from '@/components/ui/RoleBadge.vue'
import SourceDbBadge from '@/components/ui/SourceDbBadge.vue'

const props = defineProps({
  protein: { type: Object, required: true },
})

const titleLeft  = computed(() => props.protein.gene_name || props.protein.uniprot_id)
const titleRight = computed(() => props.protein.protein_name || null)

const displayRole = computed(() => {
  const annotations = props.protein.mlo_annotations ?? []
  return annotations.some(a => a.unified_role === 'driver') ? 'driver' : null
})

const SOURCE_ORDER = ['PhaseDB', 'CDCODE', 'LLPSDB', 'PhasePro', 'DrLLPS']

const SOURCE_URLS = {
  PhaseDB:  (id) => `https://db.phasep.pro/uniprot/${id}`,
  PhasePro: (id) => `https://phasepro.elte.hu/entry/${id}`,
  CDCODE:   (id) => `https://cd-code.org/search?q=${id}&p=proteins`,
  LLPSDB:   (id) => `http://bio-comp.org.cn/llpsdbv2/search.php?keyword=UniprotID&words=${id}&pmid=&species=ALL&pro_struc_type=ALL&pro_type=ALL&pro_seq_len=ALL&main_comp_type=ALL&post_trans_mod=ALL&main_comp_num=ALL&mut_type=ALL&mutst=&mutend=&phase=None`,
  DrLLPS:   () => `https://llps.biocuckoo.cn/`,
}

const sourceDbs = computed(() => {
  const annotations = props.protein.mlo_annotations ?? []
  const present = new Set(annotations.map(a => a.source_db).filter(Boolean))
  return SOURCE_ORDER.filter(s => present.has(s))
})

function sourceHref(source) {
  return SOURCE_URLS[source]?.(props.protein.uniprot_id) ?? null
}
</script>

<template>
  <div class="bg-white py-6 border-b border-slate-200 mb-0">
    <!-- Title row -->
    <h1 class="text-xl text-gray-800 mb-1">
      <span class="font-semibold">{{ titleLeft }}</span>
      <template v-if="titleRight">
        <span class="text-gray-400"> · </span>
        <span class="font-normal text-gray-600">{{ titleRight }}</span>
      </template>
    </h1>

    <!-- Metadata line -->
    <div class="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-[#484E59]">
      <span class="font-mono text-gray-800">{{ protein.uniprot_id }}</span>
      <span v-if="protein.gene_name">{{ protein.gene_name }}</span>
      <span v-if="protein.organism" class="italic">{{ protein.organism }}</span>
      <span v-if="protein.sequence_length">{{ protein.sequence_length }} aa</span>
      <span v-if="protein.disorder_mobidb_lite_dc != null">
        MobiDB-lite disorder: {{ (protein.disorder_mobidb_lite_dc * 100).toFixed(1) }}%
      </span>
    </div>

    <!-- Source badges row: role badge + source DB links -->
    <div v-if="sourceDbs.length" class="flex flex-wrap gap-2 mt-3 items-center">
      <!-- Role badge with right-border divider -->
      <div v-if="displayRole" class="flex items-center border-r border-slate-200 pr-3 mr-1">
        <RoleBadge :role="displayRole" />
      </div>

      <SourceDbBadge
        v-for="src in sourceDbs"
        :key="src"
        :source="src"
        :href="sourceHref(src)"
      />
    </div>
  </div>
</template>
