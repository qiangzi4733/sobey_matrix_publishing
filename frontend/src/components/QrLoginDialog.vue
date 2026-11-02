<template>
  <el-dialog :model-value="visible" :title="title" width="380px" :close-on-click-modal="false" @close="close">
    <div class="body">
      <!-- need_code 时 qr 是平台验证弹窗的截图 -->
      <img v-if="session.qr" :src="session.qr" :class="needCode ? 'verify' : 'qr'" alt="登录二维码" />
      <div v-else-if="!finished" v-loading="true" class="qr placeholder" />
      <div v-if="needCode" class="code">
        <el-input v-model="code" placeholder="短信验证码" maxlength="8" @keyup.enter="submitCode" />
        <el-button type="primary" :loading="submitting" @click="submitCode">提交</el-button>
      </div>
      <el-result
        v-if="session.status === 'success'"
        icon="success"
        :title="session.message"
      />
      <el-result v-else-if="session.status === 'failed'" icon="error" :title="session.message">
        <template #extra>
          <el-button type="primary" @click="start">重新获取二维码</el-button>
        </template>
      </el-result>
      <p v-else class="message">{{ session.message }}</p>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import api from '../api'

const props = defineProps({
  visible: Boolean,
  platform: { type: String, required: true },
  title: { type: String, default: '扫码登录' },
})
const emit = defineEmits(['update:visible', 'success'])

const session = ref({ status: 'starting', message: '正在打开登录页…', qr: null })
const finished = computed(() => ['success', 'failed'].includes(session.value.status))
const needCode = computed(() => session.value.status === 'need_code')
const code = ref('')
const submitting = ref(false)
let loginId = null
let timer = null

function stopPolling() {
  clearTimeout(timer)
  timer = null
}

async function poll() {
  try {
    session.value = (await api.get(`/accounts/login/sessions/${loginId}`)).data
  } catch {
    session.value = { status: 'failed', message: '登录会话已过期', qr: null }
  }
  if (session.value.status === 'success') {
    emit('success', session.value.account_id)
  } else if (!finished.value && props.visible) {
    timer = setTimeout(poll, 2000)
  }
}

async function start() {
  stopPolling()
  session.value = { status: 'starting', message: '正在打开登录页…', qr: null }
  const { data } = await api.post(`/accounts/login/${props.platform}`)
  loginId = data.login_id
  poll()
}

async function submitCode() {
  if (!code.value.trim()) return
  submitting.value = true
  try {
    await api.post(`/accounts/login/sessions/${loginId}/code`, { code: code.value.trim() })
    code.value = ''
    session.value = { ...session.value, status: 'verifying', message: '验证码已提交，正在验证', qr: null }
  } finally {
    submitting.value = false
  }
}

function close() {
  stopPolling()
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (visible) => (visible ? start() : stopPolling()),
)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.qr {
  /* 有的平台推的是整块扫码区域，不一定是正方形 */
  max-width: 260px;
  min-height: 220px;
  object-fit: contain;
}
.verify {
  max-width: 100%;
  border: 1px solid var(--el-border-color);
}
.code {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  width: 100%;
}
.placeholder {
  background: var(--el-fill-color-light);
}
.message {
  color: var(--el-text-color-secondary);
}
</style>
