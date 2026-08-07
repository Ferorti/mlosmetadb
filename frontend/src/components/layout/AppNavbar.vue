<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <nav class="sticky top-0 z-50 bg-gradient-to-r from-[#1B4F8A] to-[#2B7CD8] h-14 flex items-center">
    <div class="max-w-5xl mx-auto px-6 flex items-center justify-between w-full">

      <RouterLink to="/" class="flex items-center leading-none no-underline">
        <span class="flex items-center gap-1">

          <img src="/loguito_horizontal.svg" alt="MLOsMetaDB" class="h-[18px] w-auto relative -top-[2px]">
        </span>
        <span class="text-white font-semibold text-lg ml-2">MLOsMetaDB</span>
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
