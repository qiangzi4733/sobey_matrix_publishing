<template>
  <el-dialog :model-value="visible" :title="title" width="380px" :close-on-click-modal="false" @close="close">
    <div class="body">
      <img v-if="session.qr" :src="session.qr" class="qr" alt="登录二维码" />
      <div v-else-if="!finished" v-loading="true" class="qr placeholder" />
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
let timer = null

function stopPolling() {
  clearTimeout(timer)
  timer = null
}

async function poll(loginId) {
  try {
    session.value = (await api.get(`/accounts/login/sessions/${loginId}`)).data
  } catch {
    session.value = { status: 'failed', message: '登录会话已过期', qr: null }
  }
  if (session.value.status === 'success') {
    emit('success', session.value.account_id)
  } else if (!finished.value && props.visible) {
    timer = setTimeout(() => poll(loginId), 2000)
  }
}

async function start() {
  stopPolling()
  session.value = { status: 'starting', message: '正在打开登录页…', qr: null }
  const { data } = await api.post(`/accounts/login/${props.platform}`)
  poll(data.login_id)
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
  width: 220px;
  height: 220px;
}
.placeholder {
  background: var(--el-fill-color-light);
}
.message {
  color: var(--el-text-color-secondary);
}
</style>
