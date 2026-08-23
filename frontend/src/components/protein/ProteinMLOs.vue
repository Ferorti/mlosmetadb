<script setup>
import { computed } from 'vue'
import { formatMlo } from '@/utils/format.js'
import RoleBadge from '@/components/ui/RoleBadge.vue'

const props = defineProps({
  mloAnnotations: { type: Array, required: true },
  uniprotId:      { type: String, required: true },
})

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

/**
 * One badge per organelle, from every annotation this protein has for it.
 *
 * - `driver` if any source says so: it is the strongest claim in the set, and one
 *   resource measuring phase separation is not weakened by another only
 *   recording presence.
 * - `regulator` only when **every** annotation for this organelle is a regulator
 *   call. DrLLPS says those proteins modulate the organelle rather than live in
 *   it, so the badge would be wrong the moment another resource reports the
 *   protein as a component — and CD-CODE reporting membership is exactly that.
 *   Regulator rows reached the frontend for the first time on 2026-08-12
 *   (R1-ACT-14); `unified_role` is NULL on them, so `source_role` is the only
 *   field that identifies them.
 * - no badge otherwise, unchanged: a mixed or role-less group makes no claim
 *   this table can state in one word.
 */
function groupRole(anns) {
  if (anns.some(a => a.unified_role === 'driver')) return 'driver'
  if (anns.every(a => a.source_role === 'Regulator')) return 'regulator'
  return null
}

const MATRIX_SOURCES = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

const matrixRows = computed(() => {
  if (!dedupedAnnotations.value.length) return []

  const groups = {}
  for (const ann of dedupedAnnotations.value) {
    const key = ann.unified_mlo
    if (!groups[key]) groups[key] = []
    groups[key].push(ann)
  }

  const sortedEntries = Object.entries(groups).sort(([, annsA], [, annsB]) => {
    const aIsDriver = annsA.some(a => a.unified_role === 'driver') ? 0 : 1
    const bIsDriver = annsB.some(b => b.unified_role === 'driver') ? 0 : 1
    if (aIsDriver !== bIsDriver) return aIsDriver - bIsDriver
    return annsB.length - annsA.length
  })

  return sortedEntries.map(([unified_mlo, anns]) => ({
    unified_mlo,
    displayRole: groupRole(anns),
    cells: MATRIX_SOURCES.map(src => {
      const matches = anns.filter(a => a.source_db === src)
      return {
        source: src,
        on: matches.length > 0,
        title: matches.length ? `${src}: ${matches.map(a => a.source_mlo).join('; ')}` : `${src}: not annotated`,
      }
    }),
  }))
})

const totalAnnotations = computed(() => dedupedAnnotations.value.length)
const groupCount = computed(() => new Set(dedupedAnnotations.value.map(a => a.unified_mlo)).size)
</script>

<template>
  <div>
    <!-- Section header -->
    <div class="mb-4">
      <span class="text-lg font-semibold text-gray-800">MLOs</span>
      <span v-if="totalAnnotations" class="text-sm text-ink3 ml-2 font-normal">
        {{ totalAnnotations }} record{{ totalAnnotations !== 1 ? 's' : '' }} across
        {{ groupCount }} organelle{{ groupCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <div v-if="!dedupedAnnotations.length" class="text-sm text-ink3">
      No MLO annotations found for this protein.
    </div>

    <template v-else>
      <p class="text-[13.5px] text-ink3 max-w-[62ch] mb-6">
        A mark shows the organelle is annotated for this protein in that
        database. Hover a mark for the name the source itself uses.
      </p>

      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ORGANELLE</th>
            <th v-for="src in MATRIX_SOURCES" :key="src" class="text-center px-2 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 w-[78px]">{{ src }}</th>
            <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ROLE</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matrixRows" :key="row.unified_mlo" class="border-b border-border-soft">
            <td class="py-[11px] pr-3 text-[13.5px]">
              <RouterLink :to="`/mlo/${row.unified_mlo}`" class="text-ink hover:text-brand">{{ formatMlo(row.unified_mlo) }}</RouterLink>
            </td>
            <td v-for="cell in row.cells" :key="cell.source" :title="cell.title" class="py-[11px] px-2 text-center">
              <span v-if="cell.on" class="inline-block w-[7px] h-[7px] rounded-full bg-ink"></span>
              <span v-else class="inline-block w-[7px] h-px bg-border-strong"></span>
            </td>
            <td class="py-[11px] pl-3 text-right">
              <RoleBadge v-if="row.displayRole" :role="row.displayRole" />
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
