import { createRouter, createWebHistory } from 'vue-router'

import Layout from './views/Layout.vue'
import Login from './views/Login.vue'
import Accounts from './views/Accounts.vue'
import WechatMpCallback from './views/WechatMpCallback.vue'
import Categories from './views/Categories.vue'
import Contents from './views/Contents.vue'
import Dashboard from './views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    {
      path: '/',
      component: Layout,
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: Dashboard, meta: { title: '工作台' } },
        { path: 'accounts', name: 'accounts', component: Accounts, meta: { title: '账号管理' } },
        { path: 'accounts/wechat-mp/callback', name: 'wechat-mp-callback', component: WechatMpCallback },
        { path: 'contents', name: 'contents', component: Contents, meta: { title: '内容管理' } },
        { path: 'categories', name: 'categories', component: Categories, meta: { title: '分类与绑定' } },
        // 旧地址：发布改成在内容管理里选好分类后新建
        { path: 'publish', redirect: { name: 'contents' } },
        { path: 'publish-article', redirect: { name: 'contents' } },
        { path: 'review', redirect: { name: 'contents' } },
        // 发布记录并进了内容详情
        { path: 'tasks', redirect: { name: 'contents' } },
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
