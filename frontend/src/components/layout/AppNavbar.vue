<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <nav class="sticky top-0 z-50 bg-gradient-to-r from-[#1B4F8A] to-[#2B7CD8] h-14 flex items-center">
    <div class="max-w-5xl mx-auto px-6 flex items-center justify-between w-full">

      <RouterLink to="/" class="flex items-center no-underline">
        <span class="flex items-end gap-1">
          <span class="w-3 h-3 rounded-full bg-[#7EC8F0]"></span>
          <span class="w-4 h-4 rounded-full bg-[#5BBF8E]"></span>
          <span class="w-2.5 h-2.5 rounded-full bg-[#A8D4F5]"></span>
        </span>
        <span class="text-white font-semibold text-base ml-2">MLOsMetaDB</span>
        <span class="text-blue-200 text-xs ml-1">v2</span>
      </RouterLink>

      <div class="flex items-center gap-6">
        <RouterLink to="/results"  active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">Search</RouterLink>
        <RouterLink to="/mlos"     active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">MLOs</RouterLink>
        <RouterLink to="/api"      active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">API</RouterLink>
        <RouterLink to="/download" active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">Download</RouterLink>
        <RouterLink to="/about"    active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">About</RouterLink>
      </div>

    </div>
  </nav>
</template>
