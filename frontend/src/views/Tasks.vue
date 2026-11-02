<template>
  <div>
    <div class="toolbar">
      <span class="tip">进行中的任务每 5 秒自动刷新</span>
      <el-button type="primary" @click="$router.push({ name: 'publish' })">发布视频</el-button>
    </div>
    <el-table :data="tasks" empty-text="还没有发布任务">
      <el-table-column prop="title" label="标题" show-overflow-tooltip />
      <el-table-column label="账号" width="200">
        <template #default="{ row }">{{ PLATFORMS[row.platform] }} · {{ row.account_name }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status].type">{{ STATUS[row.status].label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="200">
        <template #default="{ row }">
          <div v-if="row.status === 'scheduled'">定时：{{ formatTime(row.scheduled_at) }}</div>
          <div v-else-if="row.finished_at">完成：{{ formatTime(row.finished_at) }}</div>
          <div v-else>提交：{{ formatTime(row.created_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="失败原因" show-overflow-tooltip>
        <template #default="{ row }">{{ row.error || '' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button v-if="row.has_screenshot" link type="primary" @click="showScreenshot(row)">截图</el-button>
          <el-button v-if="row.status === 'failed'" link type="primary" @click="retry(row)">重试</el-button>
        </template>
      </el-table-column>
    </el-table>

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
</style>
