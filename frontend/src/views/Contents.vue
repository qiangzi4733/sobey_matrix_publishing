<template>
  <div class="page">
    <div class="side">
      <div class="side-head">
        <span>分类</span>
        <el-button link type="primary" @click="managerVisible = true">管理</el-button>
      </div>
      <el-tree
        :data="sideTree"
        node-key="key"
        :current-node-key="category"
        highlight-current
        default-expand-all
        :expand-on-click-node="false"
        @node-click="(node) => pickCategory(node.key)"
      />
    </div>
    <div class="main">
      <div class="toolbar">
        <span class="filters">
          <el-radio-group v-model="filter" @change="load">
            <el-radio-button value="pending">待审核</el-radio-button>
            <el-radio-button value="approved">待发布</el-radio-button>
            <el-radio-button value="rejected">已退回</el-radio-button>
            <el-radio-button value="">全部</el-radio-button>
          </el-radio-group>
          <el-checkbox v-model="mine" @change="load">只看我提交的</el-checkbox>
        </span>
        <span>
          <el-button :disabled="!selected.length" @click="openMove">移到分类</el-button>
          <el-button type="primary" @click="openForm('video')">发布视频</el-button>
          <el-button type="primary" @click="openForm('article')">发布图文</el-button>
        </span>
      </div>
      <el-table :data="posts" empty-text="没有内容" @selection-change="(rows) => (selected = rows)">
        <el-table-column type="selection" width="40" />
        <el-table-column label="标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" @click="openDetail(row)">{{ row.title }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="70">
          <template #default="{ row }">{{ row.kind === 'article' ? '图文' : '视频' }}</template>
        </el-table-column>
        <el-table-column label="分类" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.category_id">{{ categoryPath(categories, row.category_id) }}</span>
            <span v-else class="tip">未分类</span>
          </template>
        </el-table-column>
        <el-table-column label="发布账号" min-width="160">
          <template #default="{ row }">
            <template v-if="row.account">{{ PLATFORMS[row.account.platform] }} · {{ row.account.display_name }}</template>
            <span v-else-if="row.review_status !== 'published'" class="warn">账号已移除，请修改</span>
          </template>
        </el-table-column>
        <el-table-column label="定时" width="170">
          <template #default="{ row }">{{ row.scheduled_at ? formatTime(row.scheduled_at) : '立即' }}</template>
        </el-table-column>
        <el-table-column label="提交" width="170">
          <template #default="{ row }">
            <div>{{ row.creator_name || '-' }}</div>
            <div class="tip">{{ formatTime(row.updated_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="REVIEW_STATUS[row.review_status].type">{{ REVIEW_STATUS[row.review_status].label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核意见" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.review_note || '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230">
          <template #default="{ row }">
            <template v-if="row.review_status === 'pending'">
              <el-button link type="success" @click="approve(row)">通过</el-button>
              <el-button link type="warning" @click="openReject(row)">退回</el-button>
            </template>
            <el-button v-if="row.review_status === 'approved'" link type="primary" @click="openPublish(row)">发布</el-button>
            <template v-if="row.review_status !== 'published'">
              <el-button link type="primary" @click="edit(row)">修改</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
            <el-button v-else link type="primary" @click="$router.push({ name: 'tasks' })">发布记录</el-button>
            <el-button link type="primary" @click="copy(row)">复制</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="detailVisible" :title="detail?.title" size="50%">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="状态">{{ REVIEW_STATUS[detail.review_status].label }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.review_note" label="审核意见">{{ detail.review_note }}</el-descriptions-item>
          <el-descriptions-item label="发布账号">
            <template v-if="detail.account">
              {{ PLATFORMS[detail.account.platform] }} · {{ detail.account.display_name }}
              <span v-if="detail.account.status !== 'active'" class="warn">（登录已失效）</span>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="分类">{{ categoryPath(categories, detail.category_id) || '未分类' }}</el-descriptions-item>
          <el-descriptions-item label="定时">{{ detail.scheduled_at ? formatTime(detail.scheduled_at) : '立即' }}</el-descriptions-item>
          <template v-if="detail.kind === 'video'">
            <el-descriptions-item label="描述"><div class="pre">{{ detail.description || '-' }}</div></el-descriptions-item>
            <el-descriptions-item label="话题">{{ detail.tags.map((t) => `#${t}`).join(' ') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="封面">
              <img v-if="detail.cover_url" :src="detail.cover_url" class="video-cover" alt="封面" />
              <span v-else>平台自动生成</span>
            </el-descriptions-item>
            <!-- 平台专属配置 -->
            <el-descriptions-item v-for="(value, key) in detail.options" :key="key" :label="VIDEO_OPTION_LABELS[key]?.label ?? key">
              <img v-if="VIDEO_OPTION_LABELS[key]?.image" :src="value" class="video-cover landscape" alt="" />
              <template v-else>{{ value }}</template>
            </el-descriptions-item>
          </template>
          <template v-else>
            <el-descriptions-item label="作者">{{ detail.author || '-' }}</el-descriptions-item>
            <el-descriptions-item label="摘要">{{ detail.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发布方式">{{ detail.draft_only ? '只存到草稿箱' : '直接发表（对外可见）' }}</el-descriptions-item>
            <el-descriptions-item v-if="detail.source_url" label="原文链接">{{ detail.source_url }}</el-descriptions-item>
          </template>
        </el-descriptions>
        <video v-if="detail.video_url" :src="detail.video_url" controls class="video" />
        <template v-else>
          <img :src="detail.cover_url" class="cover" alt="封面" />
          <div class="article" v-html="articleHtml"></div>
        </template>
        <div v-if="detail.review_status === 'pending'" class="actions">
          <el-button type="success" @click="approve(detail)">审核通过</el-button>
          <el-button type="warning" @click="openReject(detail)">退回</el-button>
        </div>
        <div class="actions">
          <el-button v-if="detail.review_status === 'approved'" type="primary" @click="openPublish(detail)">发布</el-button>
          <el-button @click="copy(detail)">复制到其他账号</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 新建、修改：视频字段少用弹窗；图文有正文编辑器，用宽抽屉 -->
    <el-dialog
      v-model="videoFormVisible"
      :title="editingId ? '修改视频' : copyingId ? '复制视频' : '发布视频'"
      width="720px"
      top="5vh"
      :before-close="beforeFormClose"
      @closed="resetForm"
    >
      <VideoForm v-if="videoFormVisible" ref="formRef" :post-id="editingId" :copy-from="copyingId" :categories="categories" :default-category="defaultCategory" @saved="formSaved" @cancel="closeForm" />
    </el-dialog>
    <el-drawer
      v-model="articleFormVisible"
      :title="`${editingId ? '修改' : copyingId ? '复制' : '发布'}图文（微信公众号）`"
      size="min(960px, 92%)"
      :before-close="beforeFormClose"
      @closed="resetForm"
    >
      <ArticleForm v-if="articleFormVisible" ref="formRef" :post-id="editingId" :copy-from="copyingId" :categories="categories" :default-category="defaultCategory" @saved="formSaved" @cancel="closeForm" />
    </el-drawer>

    <el-dialog v-model="managerVisible" title="分类管理" width="640px">
      <CategoryManager :categories="categories" @changed="loadCategories" />
    </el-dialog>

    <el-dialog v-model="moveVisible" title="移到分类" width="440px">
      <p>把选中的 {{ selected.length }} 条内容移到：</p>
      <CategorySelect v-model="moveTarget" :categories="categories" placeholder="未分类" />
      <div class="tip move-tip">只改变归类，不影响审核和发布状态</div>
      <template #footer>
        <el-button @click="moveVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="move">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="退回" width="460px">
      <el-input v-model="rejectNote" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="退回原因，提交人修改时能看到" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="warning" :loading="busy" @click="reject">退回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishVisible" title="发布" width="480px">
      <template v-if="publishing">
        <p>《{{ publishing.title }}》将发布到：</p>
        <div>{{ PLATFORMS[publishing.account.platform] }} · {{ publishing.account.display_name }}</div>
        <el-form label-width="70px" class="publish-form">
          <el-form-item label="时间">
            <el-radio-group v-model="publishMode">
              <el-radio value="now">立即发布</el-radio>
              <el-radio value="schedule">定时发布</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="publishMode === 'schedule'" label="定时">
            <div>
              <el-date-picker v-model="publishAt" type="datetime" :disabled-date="(d) => d < startOfToday" />
              <div v-if="scheduleExpired" class="warn">原定时间已过，请重新选择</div>
              <div class="tip">视频号需在 10 分钟后、30 天内；抖音需在 2 小时后、14 天内</div>
            </div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="publishVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="publish">确定发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import ArticleForm from '../components/ArticleForm.vue'
import CategoryManager from '../components/CategoryManager.vue'
import CategorySelect from '../components/CategorySelect.vue'
import VideoForm from '../components/VideoForm.vue'
import { buildTree, categoryPath } from '../categories'
import { cleanHtml } from '../html'
import { PLATFORMS, REVIEW_STATUS, VIDEO_OPTION_LABELS, formatTime } from '../platforms'

const route = useRoute()
const router = useRouter()
const filter = ref(route.query.status ?? 'pending')
const posts = ref([])
const categories = ref([])
// 左侧选中的分类：'all' 全部、'none' 未分类，其余是分类 id（包含下级分类的内容）
const category = ref('all')
const mine = ref(false)
const selected = ref([])
const managerVisible = ref(false)
const moveVisible = ref(false)
const moveTarget = ref(null)
const detail = ref(null)
const detailVisible = ref(false)
const rejectVisible = ref(false)
const rejectNote = ref('')
const rejecting = ref(null)
const publishVisible = ref(false)
const publishing = ref(null)
const publishMode = ref('now')
const publishAt = ref(null)
const scheduleExpired = ref(false)
const busy = ref(false)
const videoFormVisible = ref(false)
const articleFormVisible = ref(false)
const editingId = ref(null)
const copyingId = ref(null)
const formRef = ref(null)
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))

const articleHtml = computed(() => cleanHtml(detail.value?.content ?? ''))

const sideTree = computed(() => {
  const toNode = (c) => ({ key: c.id, label: c.name, children: c.children.map(toNode) })
  return [{ key: 'all', label: '全部' }, { key: 'none', label: '未分类' }, ...buildTree(categories.value).map(toNode)]
})
const defaultCategory = computed(() => (typeof category.value === 'number' ? category.value : null))

async function load() {
  const params = {}
  if (filter.value) params.review_status = filter.value
  if (category.value === 'none') params.uncategorized = true
  else if (category.value !== 'all') params.category_id = category.value
  if (mine.value) params.mine = true
  posts.value = (await api.get('/posts', { params })).data
}

async function loadCategories() {
  categories.value = (await api.get('/categories')).data
  // 选中的分类被删掉了，回到全部
  if (typeof category.value === 'number' && !categories.value.some((c) => c.id === category.value)) {
    pickCategory('all')
  }
}

function pickCategory(key) {
  category.value = key
  load()
}

function openMove() {
  moveTarget.value = defaultCategory.value
  moveVisible.value = true
}

async function move() {
  busy.value = true
  try {
    const count = (await api.post('/posts/category', { post_ids: selected.value.map((p) => p.id), category_id: moveTarget.value })).data
    moveVisible.value = false
    ElMessage.success(`已移动 ${count} 条`)
    await Promise.all([load(), loadCategories()])
  } finally {
    busy.value = false
  }
}

async function refresh() {
  await load()
  if (detailVisible.value) detail.value = (await api.get(`/posts/${detail.value.id}`)).data
}

async function openDetail(row) {
  detail.value = (await api.get(`/posts/${row.id}`)).data
  detailVisible.value = true
}

async function approve(row) {
  await api.post(`/posts/${row.id}/approve`)
  ElMessage.success('已通过，可以在「待发布」里发布')
  await refresh()
}

function openReject(row) {
  rejecting.value = row
  rejectNote.value = ''
  rejectVisible.value = true
}

async function reject() {
  if (!rejectNote.value.trim()) return ElMessage.warning('请填写退回原因')
  busy.value = true
  try {
    await api.post(`/posts/${rejecting.value.id}/reject`, { note: rejectNote.value.trim() })
    rejectVisible.value = false
    ElMessage.success('已退回')
    await refresh()
  } finally {
    busy.value = false
  }
}

function openPublish(row) {
  if (!row.account) return ElMessage.warning('发布账号已被移除，请先修改内容、重新选择账号')
  publishing.value = row
  const at = row.scheduled_at ? new Date(row.scheduled_at) : null
  scheduleExpired.value = Boolean(at && at <= new Date())
  publishMode.value = at ? 'schedule' : 'now'
  publishAt.value = scheduleExpired.value ? null : at
  publishVisible.value = true
}

async function publish() {
  if (publishMode.value === 'schedule' && !publishAt.value) return ElMessage.warning('请选择定时时间')
  if (publishMode.value === 'now') {
    await ElMessageBox.confirm('立即发布后内容会提交到平台，确定发布？', '立即发布', { type: 'warning' })
  }
  busy.value = true
  try {
    const scheduledAt = publishMode.value === 'schedule' ? publishAt.value.toISOString() : null
    await api.post(`/posts/${publishing.value.id}/publish`, { scheduled_at: scheduledAt })
    publishVisible.value = false
    detailVisible.value = false
    ElMessage.success('已提交发布')
    router.push({ name: 'tasks' })
  } finally {
    busy.value = false
  }
}

function openForm(kind, postId = null, copyFrom = null) {
  editingId.value = postId
  copyingId.value = copyFrom
  if (kind === 'article') articleFormVisible.value = true
  else videoFormVisible.value = true
}

function edit(row) {
  detailVisible.value = false
  openForm(row.kind, row.id)
}

// 复制内容和视频，换个账号再发；视频只能复制给视频渠道，图文只能给公众号
function copy(row) {
  detailVisible.value = false
  openForm(row.kind, null, row.id)
}

function resetForm() {
  editingId.value = null
  copyingId.value = null
}

async function beforeFormClose(done) {
  const form = formRef.value
  if (form?.busy()) return ElMessage.warning('正在提交，请稍候')
  if (form?.dirty()) {
    try {
      await ElMessageBox.confirm('填写的内容还没有提交，确定关闭？', '放弃修改', { type: 'warning', confirmButtonText: '放弃', cancelButtonText: '继续编辑' })
    } catch {
      return
    }
  }
  done()
}

function closeForm() {
  beforeFormClose(() => {
    videoFormVisible.value = false
    articleFormVisible.value = false
  })
}

async function formSaved() {
  videoFormVisible.value = false
  articleFormVisible.value = false
  // 新提交和修改后的内容都在「待审核」
  filter.value = 'pending'
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`删除《${row.title}》？删除后不能恢复。`, '删除', { type: 'warning' })
  await api.delete(`/posts/${row.id}`)
  ElMessage.success('已删除')
  detailVisible.value = false
  await load()
}

onMounted(async () => {
  await Promise.all([load(), loadCategories()])
  // 从「发布记录」或旧地址 /publish 跳过来时直接打开表单
  if (['video', 'article'].includes(route.query.create)) {
    openForm(route.query.create)
    router.replace({ query: { ...route.query, create: undefined } })
  }
})
</script>

<style scoped>
.page {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.side {
  flex: 0 0 200px;
  padding-right: 12px;
  border-right: 1px solid var(--el-border-color);
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  margin-bottom: 8px;
  font-weight: 600;
}
.main {
  flex: 1;
  min-width: 0;
}
.filters {
  display: flex;
  align-items: center;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.warn {
  color: var(--el-color-danger);
  font-size: 12px;
}
.pre {
  white-space: pre-wrap;
}
.video {
  width: 100%;
  max-height: 480px;
  margin-top: 16px;
  background: #000;
}
.video-cover {
  display: block;
  width: 90px;
  height: 120px;
  object-fit: cover;
  border-radius: 4px;
}
.video-cover.landscape {
  width: 160px;
}
.cover {
  width: 270px;
  height: 115px;
  object-fit: cover;
  margin-top: 16px;
  border-radius: 4px;
}
.article {
  margin-top: 12px;
  padding: 8px 12px;
  line-height: 1.7;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.article :deep(img) {
  max-width: 100%;
}
.actions {
  margin-top: 16px;
}
.move-tip {
  margin-top: 8px;
}
.publish-form {
  margin-top: 16px;
}
</style>
