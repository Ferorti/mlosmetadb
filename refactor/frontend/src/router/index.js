import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'

const routes = [
  { path: '/',            component: HomePage },
  { path: '/results',     component: () => import('@/pages/ResultsPage.vue') },
  { path: '/protein/:id', component: () => import('@/pages/ProteinPage.vue') },
  { path: '/mlo/:mlo',    component: () => import('@/pages/MlosPage.vue') },
  { path: '/mlos',        component: () => import('@/pages/MlosPage.vue') },
  { path: '/download',    component: () => import('@/pages/DownloadPage.vue') },
  { path: '/about',       component: () => import('@/pages/AboutPage.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
