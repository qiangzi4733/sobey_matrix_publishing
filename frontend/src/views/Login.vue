<template>
  <div class="page">
    <div class="scene" aria-hidden="true">
      <span class="slab slab-1" />
      <span class="slab slab-2" />
      <span class="slab slab-3" />
      <span class="slab slab-4" />
      <LoginIllustration class="illustration" />
    </div>

    <el-form class="card" :model="form" @submit.prevent="submit">
      <h1 class="title">账号登录</h1>
      <el-input
        v-model="form.email"
        class="field"
        size="large"
        placeholder="用户名"
        :prefix-icon="User"
        autocomplete="username"
        aria-label="用户名"
      />
      <el-input
        v-model="form.password"
        class="field"
        type="password"
        size="large"
        placeholder="密码"
        :prefix-icon="Lock"
        show-password
        autocomplete="current-password"
        aria-label="密码"
      />
      <div class="field captcha-row">
        <el-input
          v-model="form.captcha_code"
          size="large"
          placeholder="验证码"
          :prefix-icon="CircleCheck"
          maxlength="4"
          autocomplete="off"
          aria-label="验证码"
        />
        <button type="button" class="captcha" title="看不清？换一张" aria-label="验证码图片，点击换一张" @click="loadCaptcha">
          <img v-if="captchaSrc" :src="captchaSrc" alt="" />
        </button>
      </div>
      <button type="submit" class="submit" :disabled="loading">{{ loading ? '登录中…' : '登 录' }}</button>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Lock, User } from '@element-plus/icons-vue'

import api, { setToken } from '../api'
import LoginIllustration from '../components/LoginIllustration.vue'

const router = useRouter()
const loading = ref(false)
const captchaSrc = ref('')
const form = reactive({ email: '', password: '', captcha_id: '', captcha_code: '' })

async function loadCaptcha() {
  const { data } = await api.get('/auth/captcha')
  form.captcha_id = data.captcha_id
  form.captcha_code = ''
  captchaSrc.value = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(data.svg)}`
}

onMounted(loadCaptcha)

async function submit() {
  if (!form.email.trim() || !form.password) return ElMessage.warning('请输入用户名和密码')
  if (!form.captcha_code.trim()) return ElMessage.warning('请输入验证码')
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    setToken(data.access_token)
    router.push({ name: 'portal' })
  } catch {
    // 验证码用一次就作废，不管哪种失败都换一张
    loadCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  position: relative;
  display: flex;
  align-items: center;
  min-height: 100vh;
  min-width: 1100px;
  overflow: hidden;
  background:
    radial-gradient(ellipse 60% 70% at 30% 55%, rgba(120, 165, 255, 0.28), transparent 70%),
    radial-gradient(ellipse 50% 50% at 85% 20%, rgba(255, 255, 255, 0.9), transparent 70%),
    linear-gradient(160deg, #eef4ff 0%, #e3ecfd 45%, #edf2fd 100%);
}
/* 背景里斜铺的浅色板块和细线，模仿等距视角的桌面 */
.scene {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(-28deg, transparent 49.85%, rgba(255, 255, 255, 0.85) 50%, transparent 50.15%),
    linear-gradient(-28deg, transparent 49.85%, rgba(255, 255, 255, 0.7) 50%, transparent 50.15%),
    linear-gradient(32deg, transparent 49.85%, rgba(255, 255, 255, 0.6) 50%, transparent 50.15%);
  background-size: 100% 100%, 100% 100%, 100% 100%;
  background-position: 0 -22vh, 0 26vh, 0 8vh;
  background-repeat: no-repeat;
}
.slab {
  position: absolute;
  border-radius: 28px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.75), rgba(226, 235, 252, 0.55));
  box-shadow: 0 30px 60px rgba(88, 120, 190, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  transform: rotate(-28deg) skewX(28deg);
}
.slab-1 { width: 300px; height: 190px; left: 4%; bottom: 6%; }
.slab-2 { width: 260px; height: 160px; left: 58%; top: 30%; opacity: 0.8; }
.slab-3 { width: 380px; height: 220px; left: 46%; bottom: -8%; opacity: 0.7; }
.slab-4 { width: 220px; height: 140px; left: 70%; top: -4%; opacity: 0.6; }
.illustration {
  position: absolute;
  left: 11%;
  top: 50%;
  width: min(40vw, 600px);
  transform: translateY(-48%);
}

.card {
  position: relative;
  box-sizing: border-box;
  width: 412px;
  margin-left: auto;
  margin-right: 15%;
  padding: 44px 44px 52px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(60, 100, 180, 0.16);
}
.title {
  position: relative;
  margin: 0 0 28px;
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  color: #1748d0;
}
.title::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -9px;
  width: 28px;
  height: 3px;
  margin-left: -14px;
  border-radius: 2px;
  background: #2b63f0;
}
.field {
  margin-bottom: 18px;
}
/* 设计稿里的输入框是浅蓝色胶囊，没有边框，靠阴影浮起 */
.card :deep(.el-input__wrapper) {
  height: 44px;
  padding: 0 18px;
  border-radius: 22px;
  background: #eef3fc;
  box-shadow: 0 4px 10px rgba(80, 110, 170, 0.1);
}
.card :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #6d8cf0 inset, 0 4px 10px rgba(80, 110, 170, 0.1);
}
.card :deep(.el-input__prefix) {
  color: #8a93a6;
}
.captcha-row {
  position: relative;
}
.captcha-row :deep(.el-input__wrapper) {
  padding-right: 112px;
}
.captcha {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 100px;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 10px;
  overflow: hidden;
  background: #eef4f8;
  cursor: pointer;
}
.captcha img {
  display: block;
  width: 100%;
  height: 100%;
}
.submit {
  display: block;
  width: 100%;
  height: 44px;
  margin-top: 26px;
  border: 0;
  border-radius: 22px;
  background: linear-gradient(90deg, #0a3fd9 0%, #1677ff 55%, #13c6f5 100%);
  box-shadow: 0 8px 18px rgba(22, 100, 240, 0.28);
  color: #fff;
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
}
.submit:hover {
  filter: brightness(1.06);
}
.submit:disabled {
  opacity: 0.7;
  cursor: default;
}
</style>
