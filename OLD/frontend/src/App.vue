<script setup>
import AppNavbar from '@/components/layout/AppNavbar.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import AnnouncementBanner from '@/components/layout/AnnouncementBanner.vue'
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <AnnouncementBanner />
    <AppNavbar />
    <main class="flex-1">
      <RouterView />
    </main>
    <AppFooter />
  </div>
</template>
