<template>
  <div>
    <PageHeader title="账号管理" description="抖音和视频号每 6 小时自动检测一次登录状态">
      <el-dropdown @command="addAccount">
        <el-button type="primary">添加账号</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="item in ADD_OPTIONS" :key="item.platform" :command="item.platform" :disabled="item.disabled">
              <span class="with-icon"><PlatformIcon :platform="item.platform" />{{ item.label }}</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </PageHeader>

    <el-alert
      v-if="invalidCount"
      type="warning"
      show-icon
      :closable="false"
      class="invalid-alert"
      :title="`有 ${invalidCount} 个账号登录已失效，发布到这些账号会失败，请重新扫码或授权`"
    />

    <div class="mp-panel table-panel">
    <div class="toolbar">
      <el-radio-group v-model="platform">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="(label, key) in PLATFORMS" :key="key" :value="key">
          <span class="with-icon"><PlatformIcon :platform="key" />{{ label }}</span>
        </el-radio-button>
      </el-radio-group>
    </div>
    <el-table :data="shown" v-loading="loading" empty-text="还没有账号，点击右上角添加">
      <el-table-column label="平台" width="130">
        <template #default="{ row }">
          <span class="with-icon"><PlatformIcon :platform="row.platform" :size="18" />{{ PLATFORMS[row.platform] }}</span>
        </template>
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
          <StatusTag :tone="STATUS[row.status].tone">{{ STATUS[row.status].label }}</StatusTag>
        </template>
      </el-table-column>
      <el-table-column label="上次检测" width="170">
        <template #default="{ row }">{{ formatTime(row.last_checked_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <template v-if="QR_LOGIN_PLATFORMS.includes(row.platform)">
            <el-button v-if="row.status !== 'active'" link type="warning" @click="relogin(row)">
              重新扫码
            </el-button>
            <el-button v-else link type="primary" :loading="checking.has(row.id)" @click="check(row)">
              {{ checking.has(row.id) ? '检测中' : '检测' }}
            </el-button>
          </template>
          <el-button
            v-if="row.platform === 'wechat_mp' && row.status !== 'active'"
            link
            type="warning"
            @click="addAccount('wechat_mp')"
          >
            重新授权
          </el-button>
          <el-button link type="danger" @click="remove(row)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <QrLoginDialog
      v-model:visible="loginVisible"
      :platform="loginPlatform"
      :account-id="loginAccountId"
      :title="loginTitle"
      @success="load"
    />
  </div>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { badges } from '../badges'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import StatusTag from '../components/StatusTag.vue'
import QrLoginDialog from '../components/QrLoginDialog.vue'
import { PLATFORMS, QR_LOGIN_PLATFORMS, formatTime } from '../platforms'

const STATUS = {
  active: { label: '正常', tone: 'green' },
  expired: { label: '需重新登录', tone: 'red' },
  error: { label: '异常', tone: 'red' },
}

const ADD_OPTIONS = [
  { platform: 'channels', label: '扫码登录视频号' },
  { platform: 'wechat_mp', label: '授权微信公众号' },
  { platform: 'douyin', label: '扫码登录抖音' },
  { platform: 'kuaishou', label: '授权快手（权限申请中）', disabled: true },
]

const accounts = ref([])
const platform = ref('')
const loading = ref(false)
// 检测要等服务器浏览器打开平台，约 1 分钟，允许同时检测多个
const checking = reactive(new Set())
const loginVisible = ref(false)
const loginPlatform = ref('channels')
const loginAccountId = ref(null)
const loginTitle = ref('')

// 一次取全部账号，平台筛选在前端做，失效提醒才能统计到所有平台
const invalidCount = computed(() => accounts.value.filter((a) => a.status !== 'active').length)
// 失效的排在前面，方便处理
const shown = computed(() =>
  accounts.value
    .filter((a) => !platform.value || a.platform === platform.value)
    .sort((a, b) => (a.status === 'active') - (b.status === 'active') || a.id - b.id),
)

async function load() {
  loading.value = true
  try {
    accounts.value = (await api.get('/accounts')).data
    badges.expiredAccounts = accounts.value.filter((a) => a.status !== 'active').length
  } finally {
    loading.value = false
  }
}

async function addAccount(command) {
  if (command === 'wechat_mp') {
    // 跳到微信授权页，客户确认后跳回 /accounts/wechat-mp/callback
    const { data } = await api.post('/wechat-mp/authorize')
    window.location.href = data.url
    return
  }
  openLogin(command, null, `扫码登录${PLATFORMS[command]}`)
}

function relogin(row) {
  openLogin(row.platform, row.id, `重新登录「${row.display_name}」`)
}

function openLogin(platformKey, accountId, title) {
  loginPlatform.value = platformKey
  loginAccountId.value = accountId
  loginTitle.value = title
  loginVisible.value = true
}

async function check(row) {
  checking.add(row.id)
  ElMessage.info(`正在检测「${row.display_name}」，约需 1 分钟，可以先做别的`)
  try {
    const { data } = await api.post(`/accounts/${row.id}/check`)
    if (data.status === 'active') ElMessage.success(`「${row.display_name}」登录状态正常`)
    else ElMessage.warning(`「${row.display_name}」登录已失效，请重新扫码`)
    await load()
  } finally {
    checking.delete(row.id)
  }
}

async function remove(row) {
  const { data: usage } = await api.get(`/accounts/${row.id}/usage`)
  if (usage.running_tasks) {
    ElMessageBox.alert(`「${row.display_name}」正在发布内容，请等发布结束后再移除。`, '暂时不能移除', {
      type: 'warning',
    })
    return
  }
  const effects = []
  if (usage.posts) effects.push(`${usage.posts} 条还没发布的内容要发到这个账号，移除后需要修改内容、重新选择账号`)
  if (usage.pending_tasks) effects.push(`${usage.pending_tasks} 个排队或等待定时的发布任务会取消`)
  if (usage.categories) effects.push(`${usage.categories} 个分类绑定了这个账号，移除后这些分类要重新绑定账号才能新建内容`)
  // 名称来自平台昵称，用 VNode 而不是 HTML 字符串拼
  const message = h('div', [
    h('p', `确定移除「${row.display_name}」？移除后需要重新授权才能使用。`),
    ...effects.map((text) => h('p', `· ${text}`)),
  ])
  await ElMessageBox.confirm(message, '移除账号', { type: 'warning', confirmButtonText: '移除' })
  await api.delete(`/accounts/${row.id}`)
  ElMessage.success('已移除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.table-panel {
  padding: 12px 16px;
}
.toolbar {
  margin-bottom: 8px;
}
.invalid-alert {
  margin-bottom: 12px;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
