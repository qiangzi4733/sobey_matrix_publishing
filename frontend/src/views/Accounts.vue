<template>
  <div>
    <PageHeader title="账号管理" description="抖音和视频号每 6 小时自动检测一次登录状态" />

    <section class="adds" aria-label="添加账号">
      <button
        v-for="item in ADD_OPTIONS"
        :key="item.platform"
        type="button"
        class="add"
        :disabled="item.disabled"
        @click="addAccount(item.platform)"
      >
        <PlatformIcon :platform="item.platform" :size="32" />
        <span class="add-text">
          <span class="add-title">添加{{ PLATFORMS[item.platform] }}</span>
          <span class="tip">{{ item.how }}</span>
        </span>
      </button>
    </section>

    <el-alert
      v-if="invalidCount"
      type="error"
      show-icon
      :closable="false"
      class="invalid-alert"
      :title="`有 ${invalidCount} 个账号登录已失效，发布到这些账号会失败，请重新扫码或授权`"
    />

    <div v-if="accounts.length" class="toolbar">
      <el-radio-group v-model="platform" size="small">
        <el-radio-button value="">全部 {{ accounts.length }}</el-radio-button>
        <el-radio-button v-for="p in platformsWithAccounts" :key="p" :value="p">
          <span class="with-icon"><PlatformIcon :platform="p" :size="14" />{{ PLATFORMS[p] }} {{ countOf(p) }}</span>
        </el-radio-button>
      </el-radio-group>
    </div>

    <div v-loading="loading" class="cards">
      <article v-for="row in shown" :key="row.id" class="card mp-panel" :class="{ expired: row.status !== 'active' }">
        <div class="card-head">
          <span class="avatar-wrap">
            <!-- 微信头像有防盗链，需要不带 Referer -->
            <img v-if="row.avatar_url" :src="row.avatar_url" referrerpolicy="no-referrer" class="avatar" alt="" />
            <span v-else class="avatar initial" aria-hidden="true">{{ row.display_name.slice(0, 1) }}</span>
            <PlatformIcon :platform="row.platform" :size="18" class="avatar-badge" />
          </span>
          <span class="card-title">
            <span class="name">{{ row.display_name }}</span>
            <span class="tip ellipsis" :title="row.external_id">{{ PLATFORMS[row.platform] }} · {{ row.external_id }}</span>
          </span>
          <StatusTag :tone="STATUS[row.status].tone">{{ STATUS[row.status].label }}</StatusTag>
        </div>
        <dl class="facts">
          <div>
            <dt>{{ QR_LOGIN_PLATFORMS.includes(row.platform) ? '上次检测' : '授权时间' }}</dt>
            <dd>{{ formatTime(QR_LOGIN_PLATFORMS.includes(row.platform) ? row.last_checked_at : row.created_at) }}</dd>
          </div>
          <div>
            <dt>绑定分类</dt>
            <dd class="ellipsis" :title="boundNames(row).join('、')">{{ boundNames(row).join('、') || '未绑定' }}</dd>
          </div>
        </dl>
        <p v-if="row.status !== 'active' && impact[row.id]" class="impact">{{ impact[row.id] }}</p>
        <div class="card-actions">
          <template v-if="QR_LOGIN_PLATFORMS.includes(row.platform)">
            <el-button v-if="row.status !== 'active'" type="danger" @click="relogin(row)">重新扫码</el-button>
            <el-button v-else :loading="checking.has(row.id)" @click="check(row)">
              {{ checking.has(row.id) ? '检测中（约 1 分钟）' : '立即检测' }}
            </el-button>
          </template>
          <el-button v-else-if="row.platform === 'wechat_mp' && row.status !== 'active'" type="danger" @click="addAccount('wechat_mp')">
            重新授权
          </el-button>
          <span class="spacer" />
          <el-button text type="danger" @click="remove(row)">移除</el-button>
        </div>
      </article>
      <div v-if="!loading && !accounts.length" class="empty mp-panel">还没有账号，从上面选一个平台添加</div>
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
  { platform: 'douyin', how: '手机扫码登录' },
  { platform: 'channels', how: '微信扫码登录' },
  { platform: 'wechat_mp', how: '管理员扫码授权' },
  { platform: 'kuaishou', how: '权限申请中，暂未开放', disabled: true },
]

const accounts = ref([])
const categories = ref([])
// 失效账号会影响哪些发布，提醒客户尽快处理；key 是账号 id
const impact = reactive({})
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

const platformsWithAccounts = computed(() => Object.keys(PLATFORMS).filter((p) => accounts.value.some((a) => a.platform === p)))
const countOf = (p) => accounts.value.filter((a) => a.platform === p).length
const boundNames = (account) => categories.value.filter((c) => c.account?.id === account.id).map((c) => c.name)

async function load() {
  loading.value = true
  try {
    const [list, cats] = await Promise.all([api.get('/accounts'), api.get('/categories')])
    accounts.value = list.data
    categories.value = cats.data
    badges.expiredAccounts = accounts.value.filter((a) => a.status !== 'active').length
  } finally {
    loading.value = false
  }
  loadImpact()
}

async function loadImpact() {
  for (const key of Object.keys(impact)) delete impact[key]
  const expired = accounts.value.filter((a) => a.status !== 'active')
  const usages = await Promise.all(expired.map((a) => api.get(`/accounts/${a.id}/usage`)))
  expired.forEach((a, i) => {
    const u = usages[i].data
    const parts = []
    if (u.pending_tasks) parts.push(`${u.pending_tasks} 个排队或等待定时的发布`)
    if (u.posts) parts.push(`${u.posts} 条还没发布的内容`)
    if (parts.length) impact[a.id] = `有${parts.join('、')}要发到这个账号，请尽快重新登录。`
  })
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
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.adds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.add {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px dashed #b9bfca;
  border-radius: var(--mp-panel-radius);
  background: #fff;
  font: inherit;
  color: var(--el-text-color-primary);
  text-align: left;
  cursor: pointer;
}
.add:hover:not(:disabled) {
  border-color: var(--el-color-primary);
  background: #f5f8ff;
}
.add:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.add-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.add-title {
  font-weight: 600;
}
.invalid-alert {
  margin-bottom: 16px;
}
.toolbar {
  margin-bottom: 12px;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  min-height: 80px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}
.card.expired {
  border-color: #f8cfcb;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.avatar-wrap {
  position: relative;
  flex: none;
  width: 48px;
  height: 48px;
}
.avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar.initial {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #dde3f0;
  color: var(--mp-nav-active-fg);
  font-size: 18px;
  font-weight: 700;
}
.avatar-badge {
  position: absolute;
  right: -3px;
  bottom: -3px;
  padding: 2px;
  border-radius: 6px;
  background: #fff;
}
.card-title {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.name {
  font-size: 16px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}
.facts div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
dt {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
dd {
  margin: 0;
}
.impact {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef0ef;
  color: #7a1c14;
  font-size: 13px;
  line-height: 1.6;
}
.card-actions {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}
.spacer {
  flex: 1;
}
.empty {
  grid-column: 1 / -1;
  padding: 32px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
</style>
