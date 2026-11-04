<template>
  <div class="layout">
    <nav class="aside" aria-label="主导航">
      <div class="brand">
        <span class="logo" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round">
            <circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="18" r="2.5" />
            <path d="M8.5 6h7M6 8.5v7M18 8.5v7M8.5 18h7" />
          </svg>
        </span>
        <span class="brand-text">
          <span class="brand-name">矩阵分发</span>
          <span class="tenant">{{ me?.tenant_name }}</span>
        </span>
      </div>

      <template v-for="group in NAV" :key="group.label">
        <span class="group">{{ group.label }}</span>
        <router-link v-for="item in group.items" :key="item.to" :to="item.to" class="item" active-class="active">
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          {{ item.label }}
        </router-link>
      </template>

      <div class="me">
        <span class="avatar" aria-hidden="true">{{ me?.name?.slice(0, 1) }}</span>
        <span class="me-name">{{ me?.name }}</span>
        <el-button link @click="logout">退出</el-button>
      </div>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, Document, FolderOpened, User } from '@element-plus/icons-vue'

import api, { clearToken } from '../api'

const NAV = [
  {
    label: '内容',
    items: [
      { to: '/contents', label: '内容管理', icon: Document },
      { to: '/tasks', label: '发布记录', icon: Clock },
    ],
  },
  {
    label: '设置',
    items: [
      { to: '/accounts', label: '账号管理', icon: User },
      { to: '/categories', label: '分类与绑定', icon: FolderOpened },
    ],
  },
]

const router = useRouter()
const me = ref(null)

onMounted(async () => {
  me.value = (await api.get('/auth/me')).data
})

function logout() {
  clearToken()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100%;
}
.aside {
  flex: 0 0 220px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 20px 12px 12px;
  background: #fff;
  border-right: 1px solid var(--mp-panel-border);
  /* 内容长了滚动时导航保持在原位 */
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px 16px;
}
.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--el-color-primary);
}
.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.brand-name {
  font-weight: 700;
  font-size: 15px;
}
.tenant {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.group {
  padding: 14px 12px 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: var(--el-text-color-regular);
  text-decoration: none;
}
.item:hover {
  background: var(--el-fill-color-light);
}
.item.active {
  background: var(--mp-nav-active-bg);
  color: var(--mp-nav-active-fg);
  font-weight: 600;
}
.me {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 8px 4px;
  border-top: 1px solid var(--mp-panel-border);
}
.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #dde3f0;
  color: var(--mp-nav-active-fg);
  font-weight: 600;
}
.me-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.main {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  padding: 24px 28px 40px;
}
</style>
