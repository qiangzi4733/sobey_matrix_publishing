<template>
  <div>
    <div class="toolbar">
      <span class="tip">进行中的任务每 5 秒自动刷新</span>
      <!-- 新建要先选分类（分类决定发到哪个账号），所以去内容管理 -->
      <el-button type="primary" @click="$router.push({ name: 'contents' })">去发布</el-button>
    </div>
    <el-table :data="tasks" empty-text="还没有发布任务">
      <el-table-column prop="title" label="标题" show-overflow-tooltip />
      <el-table-column label="账号" width="200">
        <template #default="{ row }">{{ PLATFORMS[row.platform] }} · {{ row.account_name }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <!-- 平台自带定时：提交成功只代表平台已接收，到点由平台发布 -->
          <el-tag v-if="row.status === 'success' && row.draft" type="success">已存草稿</el-tag>
          <el-tag v-else-if="row.status === 'success' && row.scheduled_at" type="success">已提交定时</el-tag>
          <el-tag v-else :type="STATUS[row.status].type">{{ STATUS[row.status].label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="200">
        <template #default="{ row }">
          <div v-if="row.scheduled_at">定时：{{ formatTime(row.scheduled_at) }}</div>
          <div v-else-if="row.finished_at">完成：{{ formatTime(row.finished_at) }}</div>
          <div v-else>提交：{{ formatTime(row.created_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="失败原因" show-overflow-tooltip>
        <template #default="{ row }">{{ row.error || '' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-link v-if="row.url" :href="row.url" target="_blank" type="primary" class="op">查看文章</el-link>
          <el-button v-if="row.needs_code" link type="warning" @click="openVerify(row)">输入验证码</el-button>
          <el-button v-if="row.has_screenshot" link type="primary" @click="showScreenshot(row)">截图</el-button>
          <el-button v-if="row.can_retry" link type="primary" @click="retry(row)">重试</el-button>
          <!-- 内容在失败后修改过，要重新审核、发布，旧记录不能再重试 -->
          <span v-else-if="row.status === 'failed'" class="tip">内容已修改</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="verifyVisible" title="平台要求短信验证" width="420px">
      <p class="tip">{{ verify.message }}</p>
      <img v-if="verify.image" :src="verify.image" class="screenshot" alt="验证弹窗" />
      <div class="code">
        <el-input v-model="code" placeholder="短信验证码" maxlength="8" @keyup.enter="submitCode" />
        <el-button type="primary" :loading="submitting" @click="submitCode">提交</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="screenshotVisible" title="失败现场截图" width="80%" @closed="clearScreenshot">
      <img :src="screenshotUrl" class="screenshot" alt="失败截图" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import api from '../api'
import { PLATFORMS, formatTime } from '../platforms'

const STATUS = {
  scheduled: { label: '定时中', type: 'info' },
  queued: { label: '排队中', type: 'info' },
  running: { label: '发布中', type: 'primary' },
  success: { label: '已发布', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

const tasks = ref([])
const screenshotVisible = ref(false)
const screenshotUrl = ref('')
const verifyVisible = ref(false)
const verify = ref({ message: '', image: null, taskId: null })
const code = ref('')
const submitting = ref(false)
let timer = null

async function load() {
  tasks.value = (await api.get('/publish-tasks')).data
  clearTimeout(timer)
  if (tasks.value.some((t) => ['queued', 'running'].includes(t.status))) {
    timer = setTimeout(load, 5000)
  }
}

async function retry(row) {
  await api.post(`/publish-tasks/${row.id}/retry`)
  await load()
}

async function openVerify(row) {
  const { data } = await api.get(`/publish-tasks/${row.id}/verification`)
  verify.value = { ...data, taskId: row.id }
  code.value = ''
  verifyVisible.value = true
}

async function submitCode() {
  if (!code.value.trim()) return
  submitting.value = true
  try {
    await api.post(`/publish-tasks/${verify.value.taskId}/code`, { code: code.value.trim() })
    verifyVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function showScreenshot(row) {
  // 截图接口需要登录令牌，用 blob 方式取
  const { data } = await api.get(`/publish-tasks/${row.id}/screenshot`, { responseType: 'blob' })
  screenshotUrl.value = URL.createObjectURL(data)
  screenshotVisible.value = true
}

function clearScreenshot() {
  URL.revokeObjectURL(screenshotUrl.value)
  screenshotUrl.value = ''
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.screenshot {
  width: 100%;
}
.op {
  margin-right: 12px;
}
.code {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
