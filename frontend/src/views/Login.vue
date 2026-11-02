<template>
  <div class="page">
    <el-card class="card">
      <h2>矩阵分发平台</h2>
      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form :model="form" label-position="top" @submit.prevent="submit">
        <template v-if="mode === 'register'">
          <el-form-item label="公司名称">
            <el-input v-model="form.company_name" />
          </el-form-item>
          <el-form-item label="你的姓名">
            <el-input v-model="form.name" />
          </el-form-item>
        </template>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import api, { setToken } from '../api'

const router = useRouter()
const mode = ref('login')
const loading = ref(false)
const form = reactive({ company_name: '', name: '', email: '', password: '' })

async function submit() {
  loading.value = true
  try {
    const { data } =
      mode.value === 'login'
        ? await api.post('/auth/login', { email: form.email, password: form.password })
        : await api.post('/auth/register', form)
    setToken(data.access_token)
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
.card {
  width: 380px;
}
h2 {
  margin: 0 0 8px;
  text-align: center;
}
</style>
