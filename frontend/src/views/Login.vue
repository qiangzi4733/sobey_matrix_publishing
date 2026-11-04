<template>
  <div class="page">
    <section class="intro">
      <div class="brand">
        <span class="logo" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round">
            <circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="18" r="2.5" />
            <path d="M8.5 6h7M6 8.5v7M18 8.5v7M8.5 18h7" />
          </svg>
        </span>
        <span class="brand-name">矩阵分发</span>
      </div>
      <div class="pitch">
        <h1>一个后台，管好所有新媒体账号</h1>
        <p>抖音、视频号扫码登录，公众号授权发布。内容先审核再发布，定时、失败重试都在一处。</p>
      </div>
      <ul class="platforms">
        <li v-for="p in PLATFORM_LIST" :key="p.key">
          <span class="platform-icon"><PlatformIcon :platform="p.key" :size="20" /></span>
          <span class="platform-name">{{ PLATFORMS[p.key] }}</span>
          <span class="platform-how">{{ p.how }}</span>
        </li>
      </ul>
    </section>

    <section class="form-side">
      <el-form class="form" :model="form" label-position="top" @submit.prevent="submit">
        <div class="switch" role="tablist" aria-label="登录或注册">
          <button type="button" role="tab" :aria-selected="mode === 'login'" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
          <button type="button" role="tab" :aria-selected="mode === 'register'" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册公司</button>
        </div>
        <div class="heading">
          <h2>{{ mode === 'login' ? '欢迎回来' : '注册公司账号' }}</h2>
          <span class="tip">{{ mode === 'login' ? '用注册时的邮箱登录' : '注册后你就是这家公司的第一个用户' }}</span>
        </div>
        <template v-if="mode === 'register'">
          <el-form-item label="公司名称">
            <el-input v-model="form.company_name" size="large" autocomplete="organization" />
          </el-form-item>
          <el-form-item label="你的姓名">
            <el-input v-model="form.name" size="large" autocomplete="name" />
          </el-form-item>
        </template>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" type="email" size="large" placeholder="name@company.com" autocomplete="email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            show-password
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" size="large" :loading="loading" class="submit">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
        <p class="tip center">
          <template v-if="mode === 'login'">还没有账号？<el-button link type="primary" @click="mode = 'register'">注册公司</el-button></template>
          <template v-else>已经有账号？<el-button link type="primary" @click="mode = 'login'">去登录</el-button></template>
        </p>
      </el-form>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import api, { setToken } from '../api'
import PlatformIcon from '../components/PlatformIcon.vue'
import { PLATFORMS } from '../platforms'

const PLATFORM_LIST = [
  { key: 'douyin', how: '扫码登录' },
  { key: 'channels', how: '扫码登录' },
  { key: 'wechat_mp', how: '授权发布' },
  { key: 'kuaishou', how: '即将开放' },
]

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
  display: flex;
  flex-wrap: wrap;
  min-height: 100%;
  background: #fff;
}
.intro {
  flex: 1 1 440px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 40px;
  padding: 48px 64px;
  background: #14213d;
  color: #fff;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--el-color-primary);
}
.brand-name {
  font-size: 17px;
  font-weight: 700;
}
.pitch {
  margin-top: auto;
  max-width: 460px;
}
h1 {
  margin: 0 0 16px;
  font-size: 34px;
  line-height: 1.3;
  text-wrap: balance;
}
.pitch p {
  margin: 0;
  font-size: 16px;
  line-height: 1.7;
  color: #c9d2e6;
}
.platforms {
  list-style: none;
  margin: 0 0 auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 360px;
}
.platforms li {
  display: flex;
  align-items: center;
  gap: 12px;
}
.platform-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #fff;
}
.platform-name {
  flex: 1;
}
.platform-how {
  font-size: 13px;
  color: #c9d2e6;
}
.form-side {
  flex: 1 1 440px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}
.form {
  width: 100%;
  max-width: 380px;
}
.switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 4px;
  margin-bottom: 24px;
  border-radius: 10px;
  background: #f0f1f3;
}
.switch button {
  height: 38px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  color: var(--el-text-color-secondary);
  cursor: pointer;
}
.switch button.active {
  background: #fff;
  color: var(--el-text-color-primary);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(26, 29, 35, 0.12);
}
.heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 20px;
}
h2 {
  margin: 0;
  font-size: 24px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.submit {
  width: 100%;
  margin-top: 4px;
}
.center {
  margin: 16px 0 0;
  text-align: center;
}
/* 手机上介绍区收成一条，表单在前面一屏就能看到 */
@media (max-width: 768px) {
  .intro {
    flex-basis: 100%;
    gap: 16px;
    padding: 24px;
  }
  .pitch {
    margin-top: 0;
  }
  h1 {
    font-size: 22px;
    margin-bottom: 8px;
  }
  .pitch p {
    font-size: 14px;
  }
  .platforms {
    display: none;
  }
  .form-side {
    padding: 24px 16px 40px;
  }
}
</style>
