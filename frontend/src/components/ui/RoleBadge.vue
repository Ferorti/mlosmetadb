<script setup>
defineProps({
  role: { type: String, required: true },
})

const styles = {
  driver:  'bg-[#E8F1FB] text-[#185FA5] border-[#BFD7F0]',
  client:  'bg-[#EAF7F0] text-[#1A7A4A] border-[#B8E6CC]',
  unknown: 'bg-gray-100 text-gray-500 border-gray-200',
}
const labels = { driver: 'Driver', client: 'Client', unknown: 'Unknown' }
</script>

<template>
  <span
    class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border"
    :class="styles[role] ?? styles.unknown"
  >
    {{ labels[role] ?? role }}
  </span>
</template>
