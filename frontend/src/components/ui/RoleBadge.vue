<script setup>
defineProps({
  role: { type: String, required: true },
})

const styles = {
  driver: 'bg-[#E8F1FB] text-[#185FA5] border-[#BFD7F0]',
}
const labels = { driver: 'LLPS Driver' }
</script>

<template>
  <span
    class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap shrink-0"
    :class="styles[role] ?? 'bg-gray-100 text-gray-500 border-gray-200'"
  >
    {{ labels[role] ?? role }}
  </span>
</template>
