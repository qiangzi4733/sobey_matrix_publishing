<template>
  <div>
    <PageHeader title="工作台" :description="summary">
      <el-button type="primary" :icon="Plus" @click="router.push({ name: 'contents' })">新建内容</el-button>
    </PageHeader>

    <!-- 账号失效最影响发布，放最上面 -->
    <div v-for="a in expiredAccounts" :key="a.id" class="alert" role="alert">
      <el-icon :size="20" class="alert-icon"><WarningFilled /></el-icon>
      <span class="alert-text">
        {{ PLATFORMS[a.platform] }}「{{ a.display_name }}」登录已失效{{
          boundNames(a).length ? `，绑定它的分类「${boundNames(a).join('、')}」暂时发布不了` : ''
        }}。
      </span>
      <el-button type="danger" @click="router.push({ name: 'accounts' })">
        {{ a.platform === 'wechat_mp' ? '重新授权' : '重新扫码' }}
      </el-button>
    </div>

    <section class="todos" aria-label="待办">
      <router-link v-for="t in todos" :key="t.status" :to="{ name: 'contents', query: { status: t.status } }" class="todo mp-panel">
        <span class="todo-head">
          <span>{{ t.label }}</span>
          <span class="dot" :class="t.tone" aria-hidden="true" />
        </span>
        <span class="todo-count">{{ counts[t.status] ?? 0 }}</span>
        <span class="tip">{{ t.hint }}</span>
      </router-link>
    </section>

    <div class="columns">
      <section class="mp-panel block schedule">
        <div class="block-head">
          <h2>接下来要发布</h2>
          <router-link :to="{ name: 'contents', query: { status: 'scheduled' } }">查看已定时</router-link>
        </div>
        <p v-if="!upcoming.length" class="tip empty">没有定时发布的内容</p>
        <ul v-else class="list">
          <li v-for="p in upcoming" :key="p.id">
            <span class="when">
              <span class="tip">{{ dayLabel(p.scheduled_at) }}</span>
              <strong>{{ formatTime(p.scheduled_at).slice(11) }}</strong>
            </span>
            <span class="list-main">
              <span class="ellipsis">{{ p.title }}</span>
              <span v-if="p.account" class="tip with-icon">
                <PlatformIcon :platform="p.account.platform" :size="14" />{{ p.account.display_name }}
              </span>
            </span>
            <StatusTag tone="purple">已定时</StatusTag>
          </li>
        </ul>
      </section>

      <section class="mp-panel block">
        <div class="block-head">
          <h2>账号状态</h2>
          <router-link :to="{ name: 'accounts' }">管理账号</router-link>
        </div>
        <p v-if="!accounts.length" class="tip empty">还没有账号，<router-link :to="{ name: 'accounts' }">去添加</router-link></p>
        <ul v-else class="list">
          <li v-for="a in sortedAccounts" :key="a.id">
            <PlatformIcon :platform="a.platform" :size="28" />
            <span class="list-main">
              <span class="ellipsis">{{ a.display_name }}</span>
              <span class="tip">{{ PLATFORMS[a.platform] }} · 绑定 {{ boundNames(a).length }} 个分类</span>
            </span>
            <StatusTag :tone="a.status === 'active' ? 'green' : 'red'">{{ a.status === 'active' ? '正常' : '需重新登录' }}</StatusTag>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, WarningFilled } from '@element-plus/icons-vue'

import api from '../api'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import StatusTag from '../components/StatusTag.vue'
import { PLATFORMS, formatTime } from '../platforms'

// 「要我处理」的几类，点进去就是内容管理对应的页签。草稿只有自己看得到，所以就是我的草稿
const todos = [
  { status: 'pending', label: '待审核', hint: '先看内容再通过或退回', tone: 'amber' },
  { status: 'to_publish', label: '待发布', hint: '已通过审核，等你点「发布」', tone: 'blue' },
  { status: 'failed', label: '发布失败', hint: '看原因，重试或修改', tone: 'red' },
  { status: 'draft', label: '我的草稿', hint: '只有你自己看得到', tone: 'gray' },
]
const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const router = useRouter()
const counts = ref({})
const scheduled = ref([])
const accounts = ref([])
const categories = ref([])

const todoTotal = computed(() => (counts.value.pending ?? 0) + (counts.value.to_publish ?? 0) + (counts.value.failed ?? 0))
// 日期按北京时间（formatTime 已经是北京时间）
const today = () => formatTime(new Date()).slice(0, 10)
const summary = computed(() => {
  const [, m, d] = today().split('-').map(Number)
  const weekday = WEEKDAYS[new Date(`${today()}T12:00:00+08:00`).getUTCDay()]
  return `${m} 月 ${d} 日 周${weekday} · ${todoTotal.value ? `有 ${todoTotal.value} 条内容等人处理` : '没有待处理的内容'}`
})
const upcoming = computed(() =>
  [...scheduled.value].sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at)).slice(0, 6),
)
const expiredAccounts = computed(() => accounts.value.filter((a) => a.status !== 'active'))
const sortedAccounts = computed(() => [...accounts.value].sort((a, b) => (a.status === 'active') - (b.status === 'active')))
const boundNames = (account) => categories.value.filter((c) => c.account?.id === account.id).map((c) => c.name)

function dayLabel(value) {
  const day = formatTime(value).slice(0, 10)
  const tomorrow = formatTime(new Date(Date.now() + 86400000)).slice(0, 10)
  if (day === today()) return '今天'
  if (day === tomorrow) return '明天'
  return day.slice(5)
}

onMounted(async () => {
  const [c, s, a, cats] = await Promise.all([
    api.get('/posts/counts'),
    api.get('/posts', { params: { status: 'scheduled' } }),
    api.get('/accounts'),
    api.get('/categories'),
  ])
  counts.value = c.data
  scheduled.value = s.data
  accounts.value = a.data
  categories.value = cats.data
})
</script>

<style scoped>
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.alert {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 10px;
  background: #fef0ef;
  border: 1px solid #f8cfcb;
  color: #7a1c14;
}
.alert-icon {
  color: #b42318;
}
.alert-text {
  flex: 1;
  min-width: 220px;
}
.todos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.todo {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px 20px;
  color: var(--el-text-color-primary);
  text-decoration: none;
}
.todo:hover {
  border-color: var(--el-color-primary-light-5);
}
.todo-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 500;
  color: var(--el-text-color-regular);
}
.todo-count {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.amber {
  background: #e08a00;
}
.dot.blue {
  background: var(--el-color-primary);
}
.dot.red {
  background: var(--el-color-danger);
}
.dot.gray {
  background: #8a909c;
}
.columns {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-start;
}
.block {
  flex: 2 1 320px;
  min-width: 0;
  padding: 20px;
}
.block.schedule {
  flex: 3 1 420px;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.block-head a {
  font-size: 13px;
  color: var(--el-color-primary);
  text-decoration: none;
}
h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.empty {
  margin: 12px 0 0;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.list li {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}
.when {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 56px;
  padding: 6px 0;
  border-radius: 8px;
  background: var(--mp-page-bg);
}
.list-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
