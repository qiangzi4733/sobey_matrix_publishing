import { createRouter, createWebHistory } from 'vue-router'

import Layout from './views/Layout.vue'
import Login from './views/Login.vue'
import Accounts from './views/Accounts.vue'
import WechatMpCallback from './views/WechatMpCallback.vue'
import Categories from './views/Categories.vue'
import Contents from './views/Contents.vue'
import Dashboard from './views/Dashboard.vue'
import Portal from './views/Portal.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    // 登录后先到智媒平台门户，矩阵分发是门户里的一个模块
    { path: '/portal', name: 'portal', component: Portal },
    {
      path: '/',
      component: Layout,
      redirect: '/portal',
      children: [
        { path: 'dashboard', name: 'dashboard', component: Dashboard },
        { path: 'accounts', name: 'accounts', component: Accounts },
        { path: 'accounts/wechat-mp/callback', name: 'wechat-mp-callback', component: WechatMpCallback },
        { path: 'contents', name: 'contents', component: Contents },
        { path: 'categories', name: 'categories', component: Categories },
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
