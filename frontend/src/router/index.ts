import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/practice',
      name: 'practice',
      component: () => import('@/views/PracticeView.vue'),
    },
    {
      path: '/dictionary',
      name: 'dictionary',
      component: () => import('@/views/DictionaryView.vue'),
    },
    {
      path: '/progress',
      name: 'progress',
      component: () => import('@/views/ProgressView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
    },
  ],
});
