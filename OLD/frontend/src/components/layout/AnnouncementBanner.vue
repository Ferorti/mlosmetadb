<script setup>
import { ref } from 'vue'
import { BANNER } from '@/config.js'

const dismissed = ref(false)
</script>

<template>
  <div
    v-if="BANNER.enabled && !dismissed"
    class="flex items-center justify-between px-4 py-2 text-xs
           bg-[#FAEEDA] border-b border-[#EF9F27] text-[#633806]"
  >
    <div class="flex items-center gap-2">
      <i class="ti ti-alert-triangle" style="font-size:13px" aria-hidden="true"></i>
      {{ BANNER.message }}
    </div>
    <button
      @click="dismissed = true"
      class="ml-4 opacity-50 hover:opacity-100 transition-opacity"
      aria-label="Dismiss"
    >
      <i class="ti ti-x" style="font-size:11px" aria-hidden="true"></i>
    </button>
  </div>
</template>
