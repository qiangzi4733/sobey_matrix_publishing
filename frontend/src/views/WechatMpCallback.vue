<template>
  <el-result :icon="result.icon" :title="result.title" :sub-title="result.message">
    <template #extra>
      <el-button type="primary" @click="$router.replace({ name: 'accounts' })">返回账号管理</el-button>
    </template>
  </el-result>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import api from '../api'

// 微信授权页确认后跳回这里，地址里带 state（发起授权时生成）和 auth_code
const route = useRoute()
const router = useRouter()
const result = ref({ icon: 'info', title: '正在完成授权', message: '请稍候' })

onMounted(async () => {
  const { state, auth_code: authCode } = route.query
  if (!state || !authCode) {
    result.value = { icon: 'error', title: '授权未完成', message: '没有收到授权结果，请重新发起授权' }
    return
  }
  try {
    const { data } = await api.post('/wechat-mp/callback', { state, auth_code: authCode })
    result.value = { icon: 'success', title: '授权成功', message: `已添加公众号「${data.display_name}」` }
    setTimeout(() => router.replace({ name: 'accounts' }), 1500)
  } catch (error) {
    const detail = error.response?.data?.detail
    result.value = { icon: 'error', title: '授权失败', message: typeof detail === 'string' ? detail : '请重新发起授权' }
  }
})
</script>
