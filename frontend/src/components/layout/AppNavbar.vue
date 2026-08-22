<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

const mobileOpen = ref(false)
const BASE_URL = import.meta.env.BASE_URL

function closeMobileMenu() {
  mobileOpen.value = false
}
</script>

<template>
  <nav class="sticky top-0 z-50 bg-navy">
    <div class="h-14 flex items-center">
      <div class="max-w-5xl mx-auto px-6 flex items-center justify-between w-full">

        <RouterLink to="/" class="flex items-center leading-none no-underline" @click="closeMobileMenu">
          <span class="flex items-center gap-1">

            <img :src="`${BASE_URL}loguito_horizontal.svg`" alt="MLOsMetaDB" class="h-[18px] w-auto relative -top-[2px]">
          </span>
          <span class="text-white font-semibold text-lg ml-2">MLOsMetaDB</span>
          <span class="text-[#7F93A8] text-xs ml-1">v2</span>
        </RouterLink>

        <!-- Desktop links -->
        <div class="hidden md:flex items-center gap-6">
          <RouterLink to="/results"  active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">Search</RouterLink>
          <RouterLink to="/mlos"     active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">MLOs</RouterLink>
          <RouterLink to="/api"      active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">API</RouterLink>
          <RouterLink to="/data"     active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">Data</RouterLink>
          <RouterLink to="/about"    active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">About</RouterLink>
        </div>

        <!-- Mobile menu toggle -->
        <button
          class="md:hidden text-white p-1 -mr-1"
          @click="mobileOpen = !mobileOpen"
          :aria-expanded="mobileOpen"
          aria-label="Toggle navigation menu"
        >
          <svg v-if="!mobileOpen" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

      </div>
    </div>

    <!-- Mobile dropdown menu -->
    <div v-if="mobileOpen" class="md:hidden bg-navy border-t border-white/10 px-6 py-3 flex flex-col gap-3">
      <RouterLink to="/"        @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">Home</RouterLink>
      <RouterLink to="/results" @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">Search</RouterLink>
      <RouterLink to="/mlos"    @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">MLOs</RouterLink>
      <RouterLink to="/api"     @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">API</RouterLink>
      <RouterLink to="/data"    @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">Data</RouterLink>
      <RouterLink to="/about"   @click="closeMobileMenu" active-class="text-[#EEF2F7] font-medium" class="text-[#A6B6C6] hover:text-[#EEF2F7] text-sm transition-colors">About</RouterLink>
    </div>
  </nav>
</template>
