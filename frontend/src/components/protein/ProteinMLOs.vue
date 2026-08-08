<script setup>
import { computed } from 'vue'
import { formatMlo } from '@/utils/format.js'
import RoleBadge from '@/components/ui/RoleBadge.vue'

const props = defineProps({
  mloAnnotations: { type: Array, required: true },
  uniprotId:      { type: String, required: true },
})

const SOURCE_ORDER = ['PhaSepDB', 'CDCODE', 'LLPSDB', 'PhasePro', 'DrLLPS']

const SOURCE_COLORS = {
  PhaSepDB: '#1B4F8A',
  CDCODE:   '#854F0B',
  LLPSDB:   '#0F6E56',
  PhasePro: '#6B21A8',
  DrLLPS:   '#484E59',
}

function sourceColor(source) {
  return SOURCE_COLORS[source] ?? SOURCE_COLORS.DrLLPS
}

// Deduplicate by (unified_mlo, source_db, source_mlo)
const dedupedAnnotations = computed(() => {
  const seen = new Set()
  const deduped = (props.mloAnnotations ?? []).filter(a => {
    const key = `${a.unified_mlo}||${a.source_db}||${a.source_mlo}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  // 'NotInformed' ("No MLO associated") only adds information when it's the
  // only MLO this protein has — drop it once a real MLO is present. See
  // filterMlos() in utils/format.js and BIOLOGY.md's "NotInformed" section.
  const hasRealMlo = deduped.some(a => a.unified_mlo !== 'NotInformed')
  return hasRealMlo ? deduped.filter(a => a.unified_mlo !== 'NotInformed') : deduped
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

  // Sort groups: driver annotations first, then by number of source DBs desc
  const sortedEntries = Object.entries(groups).sort(([, annsA], [, annsB]) => {
    const aIsDriver = annsA.some(a => a.unified_role === 'driver') ? 0 : 1
    const bIsDriver = annsB.some(b => b.unified_role === 'driver') ? 0 : 1
    if (aIsDriver !== bIsDriver) return aIsDriver - bIsDriver
    return annsB.length - annsA.length
  })

  const rows = []
  let groupIndex = 0
  for (const [, anns] of sortedEntries) {
    const isDriver = anns.some(a => a.unified_role === 'driver')
    anns.forEach((ann, i) => {
      rows.push({
        isFirstInGroup: i === 0,
        groupIndex,
        unified_mlo:  ann.unified_mlo,
        displayRole:  i === 0 && isDriver ? 'driver' : null,
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
      <span class="text-lg font-semibold text-gray-800">MLOs</span>
      <span v-if="totalAnnotations" class="text-sm text-[#484E59] ml-2 font-normal">
        {{ totalAnnotations }} record{{ totalAnnotations !== 1 ? 's' : '' }} across
        {{ groupCount }} organelle{{ groupCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <div v-if="!dedupedAnnotations.length" class="text-sm text-[#484E59]">
      No MLO annotations found for this protein.
    </div>

    <template v-else>
      <p class="text-xs text-gray-500 mb-2">
        Table of annotations in source databases (unified name, role, database name, source MLO name)
      </p>

      <table class="w-full text-sm">
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
            <td class="w-44 align-top py-0.5 pr-3">
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
            <td class="w-28 align-top py-0.5 pr-3">
              <RoleBadge v-if="row.isFirstInGroup && row.displayRole" :role="row.displayRole" />
            </td>

            <!-- Source db text -->
            <td class="w-36 align-top py-0.5 pr-4">
              <span class="text-xs font-medium" :style="{ color: sourceColor(row.source_db) }">{{ row.source_db }}</span>
            </td>

            <!-- Source name -->
            <td class="align-top py-0.5 text-[#484E59] italic">
              {{ row.source_mlo }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
