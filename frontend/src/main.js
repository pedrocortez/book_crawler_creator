import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import CrawlView from './views/CrawlView.vue'
import JobView from './views/JobView.vue'
import LibraryView from './views/LibraryView.vue'

import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/crawl' },
    { path: '/crawl', component: CrawlView, meta: { title: 'Crawl' } },
    { path: '/jobs', component: JobView, meta: { title: 'Jobs' } },
    { path: '/jobs/:id', component: JobView, meta: { title: 'Job' } },
    { path: '/library', component: LibraryView, meta: { title: 'Biblioteca' } },
  ],
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')
