import { createRouter, createWebHistory } from 'vue-router'

import Layout from './views/Layout.vue'
import Login from './views/Login.vue'
import Accounts from './views/Accounts.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/accounts',
      children: [{ path: 'accounts', name: 'accounts', component: Accounts }],
    },
  ],
})

router.beforeEach((to) => {
  if (to.name !== 'login' && !localStorage.getItem('matrix_token')) {
    return { name: 'login' }
  }
})

export default router
