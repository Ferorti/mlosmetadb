<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { formatCount } from '@/utils/format'

const props = defineProps({
  stats: { type: Object, default: null }
})

const router = useRouter()

const cards = computed(() => {
  if (!props.stats) return []
  // Mutually-exclusive protein-level split: driver (has_driver=1), regulator
  // (no driver, but a curator-assigned regulator claim), component (neither).
  // mlo_annotations.by_role (annotation-row based) is NOT used here: a protein
  // with both a driver-role row and a client-role row would count in both
  // buckets there, so driver + component could exceed proteins.total.
  // driver + component + regulator always sums to proteins.total.
  const r = props.stats.proteins.by_component_role
  return [
    {
      role: 'driver',
      count: r.driver ?? 0,
      label: 'LLPS Drivers',
      description: 'Proteins with direct experimental evidence of driving liquid-liquid phase separation and/or MLO formation. Annotated as driver or scaffold in at least one source database.',
      countClass: 'text-brand',
    },
    {
      role: 'component',
      count: r.component ?? 0,
      label: 'MLO Components',
      description: 'Proteins associated with membraneless organelles without direct evidence of driving phase separation. Includes clients and proteins whose role no source determined.',
      // A very faint green, not the gray used for "component" everywhere
      // else -- specific to this card, deliberately understated so it
      // doesn't compete with the driver/regulator cards' stronger colors.
      countClass: 'text-[#65A397]',
    },
    {
      role: 'regulator',
      count: r.regulator ?? 0,
      label: 'MLO Regulators',
      description: 'Proteins a curator annotated as regulating an organelle rather than driving or residing in it. Curator-assigned in at least one source database.',
      countClass: 'text-regulator',
    },
  ]
})

function navigate(role) {
  router.push({ path: '/results', query: { role } })
}
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 items-stretch">
    <template v-if="stats">
      <button
        v-for="card in cards"
        :key="card.role"
        class="h-full flex flex-col text-left bg-white border border-gray-200 rounded-lg p-5 overflow-hidden transition-all hover:border-gray-300 hover:shadow-sm focus:outline-none cursor-pointer"
        @click="navigate(card.role)"
      >
        <div :class="[
          'h-[3px] -mx-5 -mt-5 mb-4',
          card.role === 'driver' ? 'bg-brand' :
          card.role === 'component' ? 'bg-[#D1E3E0]' : 'bg-regulator'
        ]"></div>
        <div :class="['text-3xl font-bold tabular-nums', card.countClass]">
          {{ formatCount(card.count) }}
        </div>
        <div class="text-sm font-semibold text-gray-700 mt-1">{{ card.label }}</div>
        <div class="text-xs text-gray-600 mt-2 leading-relaxed flex-1">{{ card.description }}</div>
      </button>
    </template>

    <template v-else>
      <div
        v-for="i in 3"
        :key="i"
        class="h-full border border-gray-200 rounded-lg p-5 space-y-2 overflow-hidden"
      >
        <div class="h-[3px] -mx-5 -mt-5 mb-4 bg-gray-100"></div>
        <div class="h-9 w-24 bg-gray-200 rounded animate-pulse"></div>
        <div class="h-4 w-28 bg-gray-200 rounded animate-pulse"></div>
        <div class="h-3 w-full bg-gray-100 rounded animate-pulse"></div>
      </div>
    </template>
  </div>
</template>
