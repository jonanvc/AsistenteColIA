/**
 * Main entry point for Vue.js application
 * Asistente OSC - Organizaciones de Mujeres Constructoras de Paz
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// Import styles
import './assets/main.css'

// Import views
import HomeView from './views/HomeView.vue'
import AgentChatView from './views/AgentChatView.vue'
import VennView from './views/VennView.vue'
import MapView from './views/MapView.vue'
import OrganizationManagementView from './views/OrganizationManagementView.vue'
import VennVariablesView from './views/VennVariablesView.vue'
import ScrapingLauncherView from './views/ScrapingLauncherView.vue'
import DataResultsView from './views/DataResultsView.vue'
import VennResultsView from './views/VennResultsView.vue'
import TosmanaView from './views/TosmanaView.vue'

// Create router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/chat',
      name: 'agent-chat',
      component: AgentChatView,
      meta: { title: 'Asistente OSC' }
    },
    {
      path: '/venn',
      name: 'venn',
      component: VennView
    },
    {
      path: '/map',
      name: 'map',
      component: MapView
    },
    {
      path: '/organizations',
      name: 'organizations',
      component: OrganizationManagementView
    },
    {
      path: '/venn-variables',
      name: 'venn-variables',
      component: VennVariablesView
    },
    {
      path: '/scraping',
      name: 'scraping',
      component: ScrapingLauncherView
    },
    {
      path: '/data-results',
      name: 'data-results',
      component: DataResultsView
    },
    {
      path: '/venn-results',
      name: 'venn-results',
      component: VennResultsView,
      meta: { title: 'Resultados Venn' }
    },
    {
      path: '/tosmana',
      name: 'tosmana',
      component: TosmanaView,
      meta: { title: 'Análisis QCA / Tosmana' }
    }
  ]
})

// Create app
const app = createApp(App)

// Use plugins
app.use(createPinia())
app.use(router)

// Mount app
app.mount('#app')
