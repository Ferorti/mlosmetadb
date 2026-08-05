<script setup>
import { computed } from 'vue'

const props = defineProps({
  source: { type: String, required: true },
  href:   { type: String, default: null },
})

const COLOR_MAP = {
  PhaseDB:  { bg: '#EBF3FB', text: '#1B4F8A', border: '#BFDBFE' },
  CDCODE:   { bg: '#FEF3C7', text: '#854F0B', border: '#FAC775' },
  LLPSDB:   { bg: '#D1FAE5', text: '#0F6E56', border: '#6EE7B7' },
  PhasePro: { bg: '#F3E8FF', text: '#6B21A8', border: '#D8B4FE' },
  DrLLPS:   { bg: '#F1F5F9', text: '#484E59', border: '#CBD5E1' },
}

const badgeStyle = computed(() => {
  const colors = COLOR_MAP[props.source] ?? COLOR_MAP.DrLLPS
  return {
    backgroundColor: colors.bg,
    color: colors.text,
    borderColor: colors.border,
    borderStyle: 'solid',
    borderWidth: '1px',
  }
})
</script>

<template>
  <a
    v-if="href"
    :href="href"
    target="_blank"
    rel="noopener"
    :title="`View this protein's entry in ${source}`"
    class="text-xs px-2 py-0.5 rounded font-medium inline-block"
    :style="badgeStyle"
  >{{ source }}</a>
  <span
    v-else
    class="text-xs px-2 py-0.5 rounded font-medium inline-block"
    :style="badgeStyle"
  >{{ source }}</span>
</template>
