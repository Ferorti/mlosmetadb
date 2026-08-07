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
  if (props.hoveredId === feature.id) return 'bg-slate-100'
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
            <span class="text-[#484E59] font-medium text-[10px]">{{ group.label }}</span>
          </div>
        </td>
      </tr>

      <!-- Domains: Accession | Range(s) | Name.
           A Pfam accession that repeats is one row listing every instance. -->
      <template v-if="group.type === 'Domain'">
        <tr
          v-for="item in group.items"
          :key="item.id"
          class="border-t border-slate-100 cursor-pointer transition-colors"
          :class="rowClass(item)"
          @mouseenter="emit('hover', item.id)"
          @mouseleave="emit('hover', null)"
          @click="emit('select', item.id)"
        >
          <td class="py-1 px-2 font-mono text-[#484E59] text-[10px]">{{ item.accession }}</td>
          <td colspan="2" class="py-1 px-2 font-mono text-gray-700 tabular-nums text-right whitespace-nowrap">
            {{ formatRanges(item.ranges) }}
          </td>
          <td class="py-1 px-2 text-gray-700">{{ item.label }}</td>
        </tr>
      </template>

      <!-- Everything else is always a single range: Type | Start | End | Source -->
      <template v-else>
        <tr
          v-for="item in group.items"
          :key="item.id"
          class="border-t border-slate-100 cursor-pointer transition-colors"
          :class="rowClass(item)"
          @mouseenter="emit('hover', item.id)"
          @mouseleave="emit('hover', null)"
          @click="emit('select', item.id)"
        >
          <td class="py-1 px-2 text-[#484E59]">{{ item.label }}</td>
          <td class="py-1 px-2 w-14 font-mono text-gray-700 tabular-nums text-right">{{ item.ranges[0].start }}</td>
          <td class="py-1 px-2 w-14 font-mono text-gray-700 tabular-nums text-right">{{ item.ranges[0].end }}</td>
          <td class="py-1 px-2 text-[#484E59]">
            {{ group.type === 'LCD' ? '' : formatSource(item.source) }}
          </td>
        </tr>
      </template>
    </template>
  </table>
</template>
