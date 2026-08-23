<script setup>
import { computed } from 'vue'
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

const SOURCE_ORDER = ['PhaSepDB', 'CDCODE', 'LLPSDB', 'PhasePro', 'DrLLPS']

const SOURCE_URLS = {
  PhaSepDB: (id) => `https://db.phasep.pro/uniprot/${id}`,
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
  <div class="pt-5 pb-3 mb-0">
    <!-- Title row -->
    <div class="flex items-baseline gap-3.5 flex-wrap">
      <h1 class="font-display font-bold text-[42px] leading-none tracking-[-0.035em] text-ink">{{ titleLeft }}</h1>
      <span v-if="titleRight" class="text-[19px] text-ink2 tracking-[-0.01em]">{{ titleRight }}</span>
    </div>

    <!-- Metadata line -->
    <div class="flex flex-wrap gap-x-4 gap-y-1 mt-1 font-mono text-[12.5px] text-ink3">
      <span class="text-ink">{{ protein.uniprot_id }}</span>
      <span v-if="protein.organism" class="italic">{{ protein.organism }}</span>
      <span v-if="protein.sequence_length">{{ protein.sequence_length }} aa</span>
      <span v-if="protein.disorder_mobidb_lite_dc != null">
        Disorder: {{ (protein.disorder_mobidb_lite_dc * 100).toFixed(1) }}%
      </span>
    </div>

    <!-- Source badges row: role pill + source DB links -->
    <div v-if="sourceDbs.length" class="flex flex-wrap gap-2 mt-3 items-center">
      <div v-if="displayRole" class="inline-flex items-center gap-1.5 border border-brand text-brand rounded-[2px] px-2.5 py-1 text-xs font-medium">
        <span class="w-1.5 h-1.5 bg-brand rounded-full"></span>LLPS Driver
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
