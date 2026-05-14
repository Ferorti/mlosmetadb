<script setup>
import { computed } from 'vue'
import { formatMlo } from '@/utils/format.js'
import RoleBadge from '@/components/ui/RoleBadge.vue'
import SourceDbBadge from '@/components/ui/SourceDbBadge.vue'

const props = defineProps({
  mloAnnotations: { type: Array, required: true },
  uniprotId:      { type: String, required: true },
})

const SOURCE_ORDER = ['PhaseDB', 'CDCODE', 'LLPSDB', 'PhasePro', 'DrLLPS']

const SOURCE_URLS = {
  PhaseDB:  (id) => `https://db.phasep.pro/uniprot/${id}`,
  PhasePro: (id) => `https://phasepro.elte.hu/entry/${id}`,
  CDCODE:   (id) => `https://cd-code.org/search?q=${id}&p=proteins`,
  LLPSDB:   (id) => `http://bio-comp.org.cn/llpsdbv2/search.php?keyword=UniprotID&words=${id}&pmid=&species=ALL&pro_struc_type=ALL&pro_type=ALL&pro_seq_len=ALL&main_comp_type=ALL&post_trans_mod=ALL&main_comp_num=ALL&mut_type=ALL&mutst=&mutend=&phase=None`,
  DrLLPS:   () => `https://llps.biocuckoo.cn/`,
}

function sourceHref(source) {
  return SOURCE_URLS[source]?.(props.uniprotId) ?? null
}

// Deduplicate by (unified_mlo, source_db, source_mlo)
const dedupedAnnotations = computed(() => {
  const seen = new Set()
  return (props.mloAnnotations ?? []).filter(a => {
    const key = `${a.unified_mlo}||${a.source_db}||${a.source_mlo}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

const groupedRows = computed(() => {
  if (!dedupedAnnotations.value.length) return []

  const groups = {}
  for (const ann of dedupedAnnotations.value) {
    const key = ann.unified_mlo
    if (!groups[key]) groups[key] = []
    groups[key].push(ann)
  }

  for (const mlo of Object.keys(groups)) {
    groups[mlo].sort((a, b) => {
      const ai = SOURCE_ORDER.indexOf(a.source_db)
      const bi = SOURCE_ORDER.indexOf(b.source_db)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }

  const rows = []
  let groupIndex = 0
  for (const [, anns] of Object.entries(groups)) {
    // Prioritize: if any source says 'driver', use driver
    const roles = anns.map(a => a.unified_role).filter(Boolean)
    const displayRole = roles.includes('driver') ? 'driver' : (roles[0] ?? null)
    anns.forEach((ann, i) => {
      rows.push({
        isFirstInGroup: i === 0,
        groupIndex,
        unified_mlo:  ann.unified_mlo,
        displayRole:  i === 0 ? displayRole : null,
        source_db:    ann.source_db,
        source_mlo:   ann.source_mlo,
      })
    })
    groupIndex++
  }
  return rows
})

const totalAnnotations = computed(() => dedupedAnnotations.value.length)
const groupCount = computed(() => new Set(dedupedAnnotations.value.map(a => a.unified_mlo)).size)
</script>

<template>
  <div>
    <!-- Section header -->
    <div class="mb-4">
      <span class="text-lg font-semibold text-gray-800">MLO Annotations</span>
      <span v-if="totalAnnotations" class="text-sm text-[#484E59] ml-2 font-normal">
        {{ totalAnnotations }} record{{ totalAnnotations !== 1 ? 's' : '' }} across
        {{ groupCount }} organelle{{ groupCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <div v-if="!dedupedAnnotations.length" class="text-sm text-[#484E59]">
      No MLO annotations found for this protein.
    </div>

    <table v-else class="w-full text-sm">
      <tbody>
        <tr
          v-for="(row, idx) in groupedRows"
          :key="idx"
          :class="[
            row.groupIndex % 2 === 0 ? 'bg-white' : 'bg-slate-50',
            row.isFirstInGroup && row.groupIndex > 0 ? 'border-t border-slate-200' : '',
          ]"
        >
          <!-- Organelle name -->
          <td class="w-44 align-top py-2 pr-3">
            <template v-if="row.isFirstInGroup">
              <RouterLink
                :to="`/mlo/${row.unified_mlo}`"
                class="text-[#185FA5] font-medium hover:underline"
              >
                {{ formatMlo(row.unified_mlo) }}
              </RouterLink>
            </template>
          </td>

          <!-- Role badge column -->
          <td class="w-20 align-top py-2 pr-3">
            <RoleBadge v-if="row.isFirstInGroup && row.displayRole" :role="row.displayRole" />
          </td>

          <!-- Source badge as link -->
          <td class="w-36 align-top py-2 pr-4">
            <SourceDbBadge :source="row.source_db" :href="sourceHref(row.source_db)" />
          </td>

          <!-- Source name -->
          <td class="align-top py-2 text-[#484E59] italic">
            {{ row.source_mlo }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
