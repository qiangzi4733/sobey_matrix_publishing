<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">矩阵分发平台</div>
      <el-menu router :default-active="$route.path">
        <el-menu-item index="/publish">发布视频</el-menu-item>
        <el-menu-item index="/publish-article">发布图文</el-menu-item>
        <el-menu-item index="/tasks">发布记录</el-menu-item>
        <el-menu-item index="/accounts">账号管理</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>{{ me?.tenant_name }}</span>
        <span>
          {{ me?.name }}
          <el-button link type="primary" @click="logout">退出</el-button>
        </span>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import api, { clearToken } from '../api'

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
  height: 100%;
}
.aside {
  border-right: 1px solid var(--el-border-color);
}
.logo {
  padding: 18px 20px;
  font-weight: 600;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
}
</style>
