<script setup>
import { computed } from 'vue'
import { formatCount } from '@/utils/format'

const props = defineProps({
  stats: { type: Object, default: null }
})

const metrics = computed(() => {
  if (!props.stats) return null
  return [
    { value: formatCount(props.stats.proteins.total), label: 'proteins' },
    // "Entries" = one protein-in-MLO-with-role-per-source-database record --
    // exactly what mlo_annotations.total already counts (one active row per
    // such combination), just relabeled for a clearer, less overloaded name
    // than "annotations".
    { value: formatCount(props.stats.mlo_annotations.total), label: 'entries' },
    { value: formatCount(props.stats.mlo_annotations.unique_mlos), label: 'MLOs' },
    { value: formatCount(Object.keys(props.stats.mlo_annotations.unique_proteins_by_source ?? {}).length), label: 'source LLPS databases' },
  ]
})
</script>

<template>
  <div class="bg-[#EBF3FB] border border-[#C8DFF2] rounded-lg">
    <template v-if="metrics">
      <div class="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-[#C8DFF2]">
        <div
          v-for="(m, i) in metrics"
          :key="i"
          class="flex flex-col items-center justify-center py-4 px-2"
        >
          <span class="text-xl font-bold text-[#1B3D6F] tabular-nums">{{ m.value }}</span>
          <span class="text-xs text-[#4A7BA7] uppercase tracking-wide mt-0.5 text-center">{{ m.label }}</span>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-[#C8DFF2]">
        <div
          v-for="i in 4"
          :key="i"
          class="flex flex-col items-center justify-center py-4 px-2 gap-2"
        >
          <div class="h-6 w-16 bg-[#C8DFF2] rounded animate-pulse"></div>
          <div class="h-3 w-14 bg-[#C8DFF2] rounded animate-pulse"></div>
        </div>
      </div>
    </template>
  </div>
</template>
