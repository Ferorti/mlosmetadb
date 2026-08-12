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
  // Mutually-exclusive protein-level split (has_driver=1 -> driver, else -> component).
  // mlo_annotations.by_role (annotation-row based) is NOT used here: a protein with both
  // a driver-role row and a client-role row would count in both buckets there, so
  // driver + component could exceed proteins.total.
  //
  // This two-card split is deliberately NOT the same vocabulary as
  // /mlo/{id}'s stats.by_role, which grew a third `regulator` bucket on
  // 2026-08-12 (R1-ACT-14). Here a regulator-only protein lands in "components",
  // because /stats reports has_driver and nothing finer — so the card's copy has
  // to say so rather than let the reader assume residency was established.
  const r = props.stats.proteins.by_component_role
  const componentCount = r.component ?? 0
  return [
    {
      role: 'driver',
      count: r.driver ?? 0,
      label: 'LLPS Drivers',
      description: 'Proteins with direct experimental evidence of driving liquid-liquid phase separation and/or MLO formation. Annotated as driver or scaffold in at least one source database.',
      countClass: 'text-brand-blue',
    },
    {
      role: 'component',
      count: componentCount,
      label: 'MLO Components',
      description: 'Proteins associated with membraneless organelles without direct evidence of driving phase separation. Includes clients, proteins whose role no source determined, and proteins a curator annotated as regulators of an organelle rather than residents of it.',
      countClass: 'text-gray-500',
    },
    {
      role: 'all',
      count: props.stats.proteins.total,
      label: 'MLO-associated proteins',
      description: 'All proteins annotated in at least one MLO across source databases. Includes drivers, components, regulators, and proteins with undetermined role assignments. The full dataset.',
      countClass: 'text-amber-500 opacity-80',
    },
  ]
})

function navigate(role) {
  if (role === 'all') {
    router.push({ path: '/results' })
  } else {
    router.push({ path: '/results', query: { role } })
  }
}
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <template v-if="stats">
      <button
        v-for="card in cards"
        :key="card.role"
        class="text-left bg-white border border-gray-200 rounded-lg p-5 overflow-hidden transition-all hover:border-gray-300 hover:shadow-sm focus:outline-none cursor-pointer"
        @click="navigate(card.role)"
      >
        <div :class="[
          'h-[3px] -mx-5 -mt-5 mb-4',
          card.role === 'driver' ? 'bg-brand-blue' :
          card.role === 'component' ? 'bg-gray-300' : 'bg-amber-400 opacity-60'
        ]"></div>
        <div :class="['text-3xl font-bold tabular-nums', card.countClass]">
          {{ formatCount(card.count) }}
        </div>
        <div class="text-sm font-semibold text-gray-700 mt-1">{{ card.label }}</div>
        <div class="text-xs text-gray-600 mt-2 leading-relaxed">{{ card.description }}</div>
      </button>
    </template>

    <template v-else>
      <div
        v-for="i in 3"
        :key="i"
        class="border border-gray-200 rounded-lg p-5 space-y-2 overflow-hidden"
      >
        <div class="h-[3px] -mx-5 -mt-5 mb-4 bg-gray-100"></div>
        <div class="h-9 w-24 bg-gray-200 rounded animate-pulse"></div>
        <div class="h-4 w-28 bg-gray-200 rounded animate-pulse"></div>
        <div class="h-3 w-full bg-gray-100 rounded animate-pulse"></div>
      </div>
    </template>
  </div>
</template>
