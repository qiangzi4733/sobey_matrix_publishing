<template>
  <div class="detail">
    <header class="head">
      <div class="head-text">
        <div class="head-meta">
          <StatusTag :tone="POST_STATUS[status].tone">{{ postStatusLabel(post) }}</StatusTag>
          <span class="muted">{{ post.kind === 'article' ? '图文' : '视频' }} · {{ categoryPath(categories, post.category_id) || '未分类' }}</span>
        </div>
        <h2>{{ post.title }}</h2>
      </div>
      <el-button text circle :icon="Close" aria-label="关闭" @click="emit('close')" />
    </header>

    <div class="body">
      <ol class="steps" aria-label="进度">
        <li v-for="step in steps" :key="step.label" :class="step.state">
          <span class="bar" />
          <span class="step-label">{{ step.label }}</span>
          <span class="muted small">{{ step.meta }}</span>
        </li>
      </ol>

      <!-- 当前最需要知道的一件事，放在最上面 -->
      <div v-if="post.review_status === 'rejected'" class="notice danger">
        <strong>已退回：{{ post.review_note }}</strong>
        <span>按意见修改后会重新进入待审核。</span>
      </div>
      <div v-else-if="codeTask" class="notice warning">
        <strong>平台要求短信验证码</strong>
        <span>{{ verify?.message || '验证码已发到账号绑定的手机，请尽快输入。' }}</span>
        <img v-if="verify?.image" :src="verify.image" class="shot" alt="平台的验证弹窗" />
        <div class="code">
          <el-input v-model="code" placeholder="短信验证码" maxlength="8" @keyup.enter="submitCode" />
          <el-button type="primary" :loading="submitting" @click="submitCode">提交</el-button>
        </div>
      </div>
      <div v-else-if="status === 'failed' && current" class="notice danger">
        <strong>{{ accountExpired ? `${accountLabel} 登录已失效，这次发布没有成功` : '这次发布没有成功' }}</strong>
        <span v-if="current.error">原因：{{ current.error }}</span>
        <span>{{ accountExpired ? '先重新登录账号，再点「重试」。' : '' }}如果要修改内容，请先到平台后台确认作品没有发出去。</span>
        <div class="notice-actions">
          <el-button v-if="accountExpired" type="danger" @click="router.push({ name: 'accounts' })">去重新登录</el-button>
          <el-button v-if="current.has_screenshot" @click="showScreenshot(current)">查看现场截图</el-button>
        </div>
      </div>
      <div v-else-if="status === 'publishing'" class="notice info">
        <strong>正在提交到平台</strong>
        <span>视频上传需要一两分钟，这里会自动刷新。</span>
      </div>
      <div v-else-if="status === 'scheduled'" class="notice info">
        <strong>将于 {{ formatTime(post.scheduled_at) }} 发布</strong>
        <span>{{ current?.status === 'scheduled' ? '到点由本平台提交。' : '已交给平台定时，到点前在平台上不可见。' }}</span>
      </div>
      <div v-else-if="status === 'published' && current?.url" class="notice success">
        <strong>{{ post.publish_status === 'draft_saved' ? '已存到公众号草稿箱' : '已发表' }}</strong>
        <a :href="current.url" target="_blank" rel="noopener">查看文章</a>
      </div>

      <section class="info">
        <div class="media">
          <video v-if="post.video_url" :src="post.video_url" controls class="video" />
          <img v-else-if="post.cover_url" :src="post.cover_url" class="article-cover" alt="封面" />
        </div>
        <dl>
          <dt>发布账号</dt>
          <dd>
            <template v-if="post.account">
              <span class="with-icon"><PlatformIcon :platform="post.account.platform" />{{ post.account.display_name }}</span>
              <span v-if="accountExpired" class="danger-text">登录已失效</span>
            </template>
            <template v-else-if="post.account_name">{{ post.account_name }}（已移除）</template>
            <template v-else>-</template>
          </dd>
          <dt>发布时间</dt>
          <dd>{{ post.scheduled_at ? `定时 ${formatTime(post.scheduled_at)}` : '点「发布」时立即提交' }}</dd>
          <template v-if="post.kind === 'video'">
            <dt>描述</dt>
            <dd class="pre">{{ post.description || '-' }}</dd>
            <dt>话题</dt>
            <dd>{{ post.tags.map((t) => `#${t}`).join(' ') || '-' }}</dd>
            <dt>竖封面</dt>
            <dd>
              <img v-if="post.cover_url" :src="post.cover_url" class="video-cover" alt="竖封面" />
              <template v-else>平台自动生成</template>
            </dd>
            <!-- 平台专属配置 -->
            <template v-for="(value, key) in post.options" :key="key">
              <dt>{{ VIDEO_OPTION_LABELS[key]?.label ?? key }}</dt>
              <dd>
                <img v-if="VIDEO_OPTION_LABELS[key]?.image" :src="value" class="video-cover landscape" alt="" />
                <template v-else>{{ value }}</template>
              </dd>
            </template>
          </template>
          <template v-else>
            <dt>作者</dt>
            <dd>{{ post.author || '-' }}</dd>
            <dt>摘要</dt>
            <dd>{{ post.description || '-' }}</dd>
            <dt>发布方式</dt>
            <dd>{{ post.draft_only ? '只存到草稿箱' : '直接发表（对外可见）' }}</dd>
            <template v-if="post.source_url">
              <dt>原文链接</dt>
              <dd class="break">{{ post.source_url }}</dd>
            </template>
          </template>
          <dt>提交人</dt>
          <dd>{{ post.creator_name || '-' }} · {{ formatTime(post.created_at) }}</dd>
          <template v-if="post.reviewer_name">
            <dt>审核</dt>
            <dd>{{ post.reviewer_name }} · {{ formatTime(post.reviewed_at) }}</dd>
          </template>
        </dl>
      </section>

      <section v-if="post.kind === 'article'">
        <h3>正文</h3>
        <div class="article" v-html="articleHtml"></div>
      </section>

      <section>
        <h3>发布记录</h3>
        <p v-if="!tasks.length" class="muted">还没有发布过</p>
        <ol v-else class="timeline">
          <li v-for="(task, index) in tasks" :key="task.id">
            <span class="dot" :class="TASK_STATUS[task.status].tone" />
            <div class="event">
              <div class="event-head">
                <StatusTag :tone="TASK_STATUS[task.status].tone">{{ taskLabel(task) }}</StatusTag>
                <span class="muted small">{{ taskTime(task) }}</span>
                <span v-if="index > 0 && task.status === 'failed' && !task.can_retry" class="muted small">（之后内容修改过）</span>
              </div>
              <span class="muted small">第 {{ tasks.length - index }} 次 · {{ PLATFORMS[task.platform] }} · {{ task.account_name }}</span>
              <span v-if="task.error" class="small">{{ task.error }}</span>
              <span class="event-actions">
                <el-button v-if="task.has_screenshot" link type="primary" @click="showScreenshot(task)">现场截图</el-button>
                <el-link v-if="task.url" :href="task.url" target="_blank" type="primary">查看文章</el-link>
              </span>
            </div>
          </li>
        </ol>
      </section>
    </div>

    <footer class="foot">
      <template v-if="post.review_status === 'pending'">
        <el-button type="primary" @click="emit('approve', post)">审核通过</el-button>
        <el-button @click="emit('reject', post)">退回</el-button>
      </template>
      <el-button v-if="status === 'to_publish'" type="primary" @click="emit('publish', post)">发布</el-button>
      <el-button v-if="current?.can_retry" type="primary" :loading="retrying" @click="retry">重试</el-button>
      <el-button v-if="isEditable(post)" @click="emit('edit', post)">修改</el-button>
      <el-button @click="emit('copy', post)">复制到其他分类</el-button>
      <span class="spacer" />
      <el-button v-if="isEditable(post)" text type="danger" @click="emit('remove', post)">删除</el-button>
    </footer>

    <el-dialog v-model="screenshotVisible" title="现场截图" width="80%" append-to-body @closed="clearScreenshot">
      <img :src="screenshotUrl" class="shot" alt="平台页面截图" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close } from '@element-plus/icons-vue'

import api from '../api'
import { categoryPath } from '../categories'
import { cleanHtml } from '../html'
import {
  PLATFORMS,
  POST_STATUS,
  VIDEO_OPTION_LABELS,
  formatTime,
  isEditable,
  postStatus,
  postStatusLabel,
} from '../platforms'
import PlatformIcon from './PlatformIcon.vue'
import StatusTag from './StatusTag.vue'

const props = defineProps({
  post: { type: Object, required: true },
  categories: { type: Array, required: true },
})
// refresh：任务状态变了，内容和列表都要重新取
const emit = defineEmits(['close', 'refresh', 'approve', 'reject', 'publish', 'edit', 'copy', 'remove'])

const TASK_STATUS = {
  scheduled: { label: '等待定时', tone: 'purple' },
  queued: { label: '排队中', tone: 'gray' },
  running: { label: '发布中', tone: 'sky' },
  success: { label: '提交成功', tone: 'green' },
  failed: { label: '失败', tone: 'red' },
}

const router = useRouter()
const tasks = ref([])
const verify = ref(null)
const code = ref('')
const submitting = ref(false)
const retrying = ref(false)
const screenshotVisible = ref(false)
const screenshotUrl = ref('')
let timer = null

const status = computed(() => postStatus(props.post))
// 这一轮的任务是最新的那条；内容修改后 current_task 清空，旧任务只留作记录
const current = computed(() => (props.post.publish_status ? tasks.value[0] : null))
const codeTask = computed(() => tasks.value.find((t) => t.needs_code))
const accountExpired = computed(() => props.post.account && props.post.account.status !== 'active')
const accountLabel = computed(() =>
  props.post.account ? `${PLATFORMS[props.post.account.platform]}「${props.post.account.display_name}」` : '账号',
)
const articleHtml = computed(() => cleanHtml(props.post.content ?? ''))

const steps = computed(() => {
  const p = props.post
  const s = status.value
  const review =
    p.review_status === 'rejected'
      ? { label: '已退回', state: 'error', meta: p.reviewer_name ?? '' }
      : p.review_status === 'approved'
        ? { label: '审核通过', state: 'done', meta: [p.reviewer_name, p.reviewed_at && formatTime(p.reviewed_at)].filter(Boolean).join(' ') }
        : { label: '审核', state: p.review_status === 'pending' ? 'active' : '', meta: p.review_status === 'pending' ? '等待审核' : '' }
  const publish = {
    to_publish: { label: '发布', state: 'active', meta: '等待点「发布」' },
    publishing: { label: '发布中', state: 'active', meta: '正在提交到平台' },
    scheduled: { label: '已定时', state: 'done', meta: formatTime(p.scheduled_at) },
    published: { label: '已提交到平台', state: 'done', meta: formatTime(current.value?.finished_at) },
    failed: { label: '发布失败', state: 'error', meta: formatTime(current.value?.finished_at) },
  }[s] ?? { label: '发布', state: '', meta: '' }
  const finish =
    s === 'published'
      ? { label: p.publish_status === 'draft_saved' ? '已存草稿' : '发布成功', state: 'done', meta: '' }
      : { label: '发布成功', state: '', meta: '' }
  return [
    { label: p.review_status === 'draft' ? '草稿' : '提交审核', state: p.review_status === 'draft' ? 'active' : 'done', meta: p.creator_name ?? '' },
    review,
    publish,
    finish,
  ]
})

function taskLabel(task) {
  if (task.status === 'success' && task.draft) return '已存草稿'
  if (task.status === 'success' && task.scheduled_at) return '已提交定时'
  return TASK_STATUS[task.status].label
}

function taskTime(task) {
  if (task.finished_at) return `完成 ${formatTime(task.finished_at)}`
  if (task.started_at) return `开始 ${formatTime(task.started_at)}`
  return `创建 ${formatTime(task.created_at)}`
}

async function loadTasks() {
  clearTimeout(timer)
  const before = tasks.value.map((t) => `${t.id}:${t.status}`).join()
  tasks.value = (await api.get(`/posts/${props.post.id}/tasks`)).data
  const after = tasks.value.map((t) => `${t.id}:${t.status}`).join()
  if (before && before !== after) emit('refresh')
  if (codeTask.value && verify.value?.taskId !== codeTask.value.id) {
    const { data } = await api.get(`/publish-tasks/${codeTask.value.id}/verification`)
    verify.value = { ...data, taskId: codeTask.value.id }
  }
  // 发布中要盯着进度和验证码，和原来的发布记录页一样每 5 秒刷新
  if (tasks.value.some((t) => ['queued', 'running'].includes(t.status))) timer = setTimeout(loadTasks, 5000)
}

async function submitCode() {
  if (!code.value.trim()) return
  submitting.value = true
  try {
    await api.post(`/publish-tasks/${codeTask.value.id}/code`, { code: code.value.trim() })
    code.value = ''
    verify.value = null
    ElMessage.success('已提交验证码')
    await loadTasks()
  } finally {
    submitting.value = false
  }
}

async function retry() {
  retrying.value = true
  try {
    await api.post(`/publish-tasks/${current.value.id}/retry`)
    ElMessage.success('已重新提交发布')
    emit('refresh')
    await loadTasks()
  } finally {
    retrying.value = false
  }
}

async function showScreenshot(task) {
  // 截图接口需要登录令牌，用 blob 方式取
  const { data } = await api.get(`/publish-tasks/${task.id}/screenshot`, { responseType: 'blob' })
  screenshotUrl.value = URL.createObjectURL(data)
  screenshotVisible.value = true
}

function clearScreenshot() {
  URL.revokeObjectURL(screenshotUrl.value)
  screenshotUrl.value = ''
}

// 打开别的内容、或这条内容被审核/发布后（publish_status 变了）重新取发布记录
watch(
  () => [props.post.id, props.post.publish_status, props.post.review_status],
  ([id], [oldId] = []) => {
    if (id !== oldId) {
      tasks.value = []
      verify.value = null
      code.value = ''
    }
    loadTasks()
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--mp-panel-border);
}
.head-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.head-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.4;
  word-break: break-word;
}
h3 {
  margin: 0 0 10px;
  font-size: 15px;
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.muted {
  color: var(--el-text-color-secondary);
}
.small {
  font-size: 12px;
}
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.steps li {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.bar {
  height: 4px;
  border-radius: 2px;
  background: var(--mp-panel-border);
}
.step-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}
.steps .done .bar {
  background: var(--el-color-primary);
}
.steps .done .step-label {
  color: var(--el-text-color-primary);
}
.steps .active .bar {
  background: var(--el-color-primary-light-5);
}
.steps .active .step-label {
  color: var(--el-color-primary);
}
.steps .error .bar {
  background: var(--el-color-danger);
}
.steps .error .step-label {
  color: #b42318;
}
.notice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid;
  font-size: 13px;
  line-height: 1.6;
}
.notice strong {
  font-size: 14px;
}
.notice.danger {
  background: #fef0ef;
  border-color: #f8cfcb;
  color: #7a1c14;
}
.notice.warning {
  background: #fff8eb;
  border-color: #f6dcb2;
  color: #6b4100;
}
.notice.info {
  background: #f5f8ff;
  border-color: #d5defb;
  color: #2643b8;
}
.notice.success {
  background: #e7f6ec;
  border-color: #b9e3c9;
  color: #146c2e;
}
.notice-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.code {
  display: flex;
  gap: 8px;
  width: 100%;
  max-width: 320px;
}
.shot {
  width: 100%;
}
.info {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.media:empty {
  display: none;
}
.video {
  width: 180px;
  max-height: 320px;
  border-radius: 10px;
  background: #000;
}
.article-cover {
  width: 200px;
  height: 85px;
  object-fit: cover;
  border-radius: 8px;
}
dl {
  flex: 1;
  min-width: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px 12px;
}
dt {
  color: var(--el-text-color-secondary);
}
dd {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.pre {
  white-space: pre-wrap;
}
.break {
  word-break: break-all;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.danger-text {
  color: #b42318;
  font-size: 12px;
}
.video-cover {
  width: 90px;
  height: 120px;
  object-fit: cover;
  border-radius: 6px;
}
.video-cover.landscape {
  width: 160px;
}
.article {
  padding: 12px 16px;
  line-height: 1.7;
  border: 1px solid var(--mp-panel-border);
  border-radius: 8px;
}
.article :deep(img) {
  max-width: 100%;
}
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.timeline li {
  display: flex;
  gap: 12px;
  position: relative;
  padding-bottom: 16px;
}
/* 竖线连起各次发布 */
.timeline li:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 14px;
  bottom: 0;
  width: 2px;
  background: var(--mp-panel-border);
}
.timeline .dot {
  flex: none;
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 50%;
  background: #8a909c;
}
.dot.red {
  background: var(--el-color-danger);
}
.dot.green {
  background: var(--el-color-success);
}
.dot.sky {
  background: #0b5cad;
}
.dot.purple {
  background: #5b33b6;
}
.event {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.event-actions {
  display: flex;
  gap: 12px;
}
.event-actions:empty {
  display: none;
}
.foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 14px 24px;
  border-top: 1px solid var(--mp-panel-border);
}
.foot .el-button + .el-button {
  margin-left: 0;
}
.spacer {
  flex: 1;
}
</style>
