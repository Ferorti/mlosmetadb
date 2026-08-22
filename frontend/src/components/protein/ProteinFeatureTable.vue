<script setup>
import { formatSource, formatRanges } from '@/composables/useProteinFeatures.js'

const props = defineProps({
  groups:    { type: Array,  required: true },   // from useProteinFeatures().groups
  hoveredId: { type: String, default: null },
  pinnedId:  { type: String, default: null },
})

const emit = defineEmits(['hover', 'select'])

function rowClass(feature) {
  if (props.pinnedId === feature.id)  return 'bg-[#E8F1FB]'
  if (props.hoveredId === feature.id) return 'bg-page'
  return ''
}
</script>

<template>
  <table class="w-full text-xs border-collapse">
    <template v-for="group in groups" :key="group.type">
      <!-- Group header -->
      <tr>
        <td colspan="4" class="pt-3 pb-1 px-2 bg-slate-50">
          <div class="flex items-center gap-2">
            <span
              class="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
              :style="{ backgroundColor: group.color }"
            ></span>
            <span class="font-mono text-[10.5px] text-ink2 tracking-[0.07em]">{{ group.label }}</span>
          </div>
        </td>
      </tr>

      <!-- Domains: Accession | Range(s) | Name.
           A Pfam accession that repeats is one row listing every instance. -->
      <template v-if="group.type === 'Domain'">
        <tr
          v-for="item in group.items"
          :key="item.id"
          class="border-t border-border-soft cursor-pointer transition-colors"
          :class="rowClass(item)"
          @mouseenter="emit('hover', item.id)"
          @mouseleave="emit('hover', null)"
          @click="emit('select', item.id)"
        >
          <td class="py-1 px-2 font-mono text-ink3 text-[10px]">{{ item.accession }}</td>
          <td colspan="2" class="py-1 px-2 font-mono text-ink2 tabular-nums text-right whitespace-nowrap">
            {{ formatRanges(item.ranges) }}
          </td>
          <td class="py-1 px-2 text-ink2">{{ item.label }}</td>
        </tr>
      </template>

      <!-- Everything else is always a single range: Type | Start | End | Source -->
      <template v-else>
        <tr
          v-for="item in group.items"
          :key="item.id"
          class="border-t border-border-soft cursor-pointer transition-colors"
          :class="rowClass(item)"
          @mouseenter="emit('hover', item.id)"
          @mouseleave="emit('hover', null)"
          @click="emit('select', item.id)"
        >
          <td class="py-1 px-2 text-ink3">{{ item.label }}</td>
          <td class="py-1 px-2 w-14 font-mono text-ink2 tabular-nums text-right">{{ item.ranges[0].start }}</td>
          <td class="py-1 px-2 w-14 font-mono text-ink2 tabular-nums text-right">{{ item.ranges[0].end }}</td>
          <td class="py-1 px-2 text-ink3">
            {{ group.type === 'LCD' ? '' : formatSource(item.source) }}
          </td>
        </tr>
      </template>
    </template>
  </table>
</template>
