import { createRouter, createWebHistory } from 'vue-router'

import Layout from './views/Layout.vue'
import Login from './views/Login.vue'
import Accounts from './views/Accounts.vue'
import WechatMpCallback from './views/WechatMpCallback.vue'
import Tasks from './views/Tasks.vue'
import Contents from './views/Contents.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/accounts',
      children: [
        { path: 'accounts', name: 'accounts', component: Accounts },
        { path: 'accounts/wechat-mp/callback', name: 'wechat-mp-callback', component: WechatMpCallback },
        { path: 'contents', name: 'contents', component: Contents },
        // 旧地址：发布改成在内容管理里选好分类后新建
        { path: 'publish', redirect: { name: 'contents' } },
        { path: 'publish-article', redirect: { name: 'contents' } },
        { path: 'review', redirect: { name: 'contents' } },
        { path: 'tasks', name: 'tasks', component: Tasks },
      ],
    },
  ],
})

router.beforeEach((to) => {
  if (to.name !== 'login' && !localStorage.getItem('matrix_token')) {
    return { name: 'login' }
  }
})

export default router
