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
  const r = props.stats.mlo_annotations.by_role
  return [
    {
      role: 'driver',
      count: r.driver,
      label: 'Drivers',
      description: 'Directly drives MLO formation or stability through LLPS.',
      countClass: 'text-brand-blue',
    },
    {
      role: 'client',
      count: r.client,
      label: 'Clients',
      description: 'Recruited to MLOs without actively driving phase separation.',
      countClass: 'text-brand-green',
    },
    {
      role: 'unknown',
      count: r.unknown,
      label: 'Unknown / unassigned',
      description: 'No structured role data in the source database.',
      countClass: 'text-gray-400',
    },
  ]
})

function navigate(role) {
  if (role === 'unknown') return
  router.push({ path: '/results', query: { role } })
}
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <template v-if="stats">
      <button
        v-for="card in cards"
        :key="card.role"
        :class="[
          'text-left bg-white border border-gray-200 rounded-lg p-5 overflow-hidden transition-all hover:border-gray-300 hover:shadow-sm focus:outline-none',
          card.role !== 'unknown' ? 'cursor-pointer' : 'cursor-default opacity-80'
        ]"
        @click="navigate(card.role)"
      >
        <div :class="[
          'h-[3px] -mx-5 -mt-5 mb-4',
          card.role === 'driver' ? 'bg-brand-blue' :
          card.role === 'client' ? 'bg-brand-green' : 'bg-gray-300'
        ]"></div>
        <div :class="['text-3xl font-bold tabular-nums', card.countClass]">
          {{ formatCount(card.count) }}
        </div>
        <div class="text-sm font-semibold text-gray-700 mt-1">{{ card.label }}</div>
        <div class="text-xs text-gray-400 mt-2 leading-relaxed">{{ card.description }}</div>
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
