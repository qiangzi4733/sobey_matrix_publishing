<template>
  <div>
    <div class="toolbar">
      <el-radio-group v-model="platform" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="(label, key) in PLATFORMS" :key="key" :value="key">
          {{ label }}
        </el-radio-button>
      </el-radio-group>
      <el-dropdown @command="addAccount">
        <el-button type="primary">添加账号</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="channels">扫码登录视频号</el-dropdown-item>
            <el-dropdown-item command="wechat_mp" disabled>授权微信公众号（开发中）</el-dropdown-item>
            <el-dropdown-item command="douyin">扫码登录抖音</el-dropdown-item>
            <el-dropdown-item command="kuaishou" disabled>授权快手（权限申请中）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-table :data="accounts" v-loading="loading" empty-text="还没有账号，点击右上角添加">
      <el-table-column label="平台" width="90">
        <template #default="{ row }">{{ PLATFORMS[row.platform] }}</template>
      </el-table-column>
      <el-table-column label="名称" min-width="160">
        <template #default="{ row }">
          <div class="name">
            <!-- 微信头像有防盗链，需要不带 Referer -->
            <img v-if="row.avatar_url" :src="row.avatar_url" referrerpolicy="no-referrer" class="avatar" alt="" />
            <span>{{ row.display_name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="external_id" label="平台账号 ID" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status].type">{{ STATUS[row.status].label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上次检测" width="170">
        <template #default="{ row }">{{ formatTime(row.last_checked_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <template v-if="QR_LOGIN_PLATFORMS.includes(row.platform)">
            <el-button v-if="row.status !== 'active'" link type="warning" @click="addAccount(row.platform)">
              重新扫码
            </el-button>
            <el-button v-else link type="primary" :loading="checking === row.id" @click="check(row)">
              检测
            </el-button>
          </template>
          <el-button link type="primary" @click="rename(row)">改名</el-button>
          <el-button link type="danger" @click="remove(row)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <QrLoginDialog
      v-model:visible="loginVisible"
      :platform="loginPlatform"
      :title="`扫码登录${PLATFORMS[loginPlatform]}`"
      @success="load"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import QrLoginDialog from '../components/QrLoginDialog.vue'
import { PLATFORMS, QR_LOGIN_PLATFORMS, formatTime } from '../platforms'

const STATUS = {
  active: { label: '正常', type: 'success' },
  expired: { label: '需重新登录', type: 'warning' },
  error: { label: '异常', type: 'danger' },
}

const accounts = ref([])
const platform = ref('')
const loading = ref(false)
const checking = ref(null)
const loginVisible = ref(false)
const loginPlatform = ref('channels')

async function load() {
  loading.value = true
  try {
    const params = platform.value ? { platform: platform.value } : {}
    accounts.value = (await api.get('/accounts', { params })).data
  } finally {
    loading.value = false
  }
}

function addAccount(command) {
  loginPlatform.value = command
  loginVisible.value = true
}

async function check(row) {
  checking.value = row.id
  try {
    const { data } = await api.post(`/accounts/${row.id}/check`)
    if (data.status === 'active') ElMessage.success('登录状态正常')
    else ElMessage.warning('登录已失效，请重新扫码')
    await load()
  } finally {
    checking.value = null
  }
}

async function rename(row) {
  const { value } = await ElMessageBox.prompt('新的名称', '改名', { inputValue: row.display_name })
  await api.patch(`/accounts/${row.id}`, { display_name: value })
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定移除「${row.display_name}」？移除后需要重新授权才能使用。`, '移除账号', {
    type: 'warning',
  })
  await api.delete(`/accounts/${row.id}`)
  await load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}
.name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
}
</style>
