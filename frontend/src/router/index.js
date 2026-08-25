import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'

const routes = [
  { path: '/',            component: HomePage },
  { path: '/results',     component: () => import('@/pages/ResultsPage.vue') },
  { path: '/protein/:id', component: () => import('@/pages/ProteinPage.vue') },
  { path: '/mlo/:mlo',    component: () => import('@/pages/MloDetailPage.vue') },
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
  // Without this, a forward navigation (e.g. an MLO link on Home to
  // /results?mlo=X) can still visually land at the top: the target page
  // briefly renders its loading skeleton, which is much shorter than the
  // page being left, and the browser clamps the current scroll position to
  // that shorter height before the real content grows back in. Returning
  // `false` here tells the router to never force a scroll on its own, and
  // `savedPosition` restores the exact spot on browser back/forward.
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash }
    return false
  },
})
