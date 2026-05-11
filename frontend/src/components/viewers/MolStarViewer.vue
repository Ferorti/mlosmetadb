<script setup>
defineProps({
  uniprotId: { type: String, required: true },
})
</script>

<template>
  <div class="w-full h-full flex flex-col items-center justify-center bg-slate-50 text-center p-4">
    <div class="text-3xl mb-2">🔬</div>
    <div class="text-xs font-medium text-[#484E59]">3D Structure Viewer</div>
    <div class="text-[10px] text-gray-400 mt-1">MolStar — not yet configured</div>
  </div>
</template>
