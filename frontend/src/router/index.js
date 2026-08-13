import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'

const routes = [
  { path: '/',            component: HomePage },
  { path: '/results',     component: () => import('@/pages/ResultsPage.vue') },
  { path: '/protein/:id', component: () => import('@/pages/ProteinPage.vue') },
  { path: '/mlo/:mlo',    component: () => import('@/pages/MlosPage.vue') },
  { path: '/mlos',        component: () => import('@/pages/MlosPage.vue') },
  { path: '/api',         component: () => import('@/pages/ApiPage.vue') },
  { path: '/data',        component: () => import('@/pages/DataPage.vue') },
  { path: '/about',       component: () => import('@/pages/AboutPage.vue') },
]

export default createRouter({
  // Derived from vite.config.js's `base`, so a build made for /v2/ produces
  // /v2/results rather than /results. '/' in a normal build.
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})
