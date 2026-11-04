<template>
  <PageHeader title="内容管理">
    <!-- 只有绑定了账号的分类能新建，账号决定发视频还是图文 -->
    <template v-if="currentKind">
      <span class="tip with-icon"><PlatformIcon :platform="current.account.platform" :size="14" /> 发到 {{ current.account.display_name }}</span>
      <el-button v-if="currentKind === 'video'" type="primary" :icon="Plus" @click="openForm('video')">发布视频</el-button>
      <el-button v-else type="primary" :icon="Plus" @click="openForm('article')">发布图文</el-button>
    </template>
    <template v-else>
      <span class="tip">{{ current ? '这个分类还没有绑定发布账号' : '选择左侧已绑定账号的分类后才能发布' }}</span>
      <el-button @click="goSetup">去设置</el-button>
    </template>
  </PageHeader>
  <div class="page">
    <div class="side mp-panel">
      <div class="side-head">
        <span>分类</span>
        <el-button link type="primary" @click="router.push({ name: 'categories' })">管理</el-button>
      </div>
      <el-tree
        :data="sideTree"
        node-key="key"
        :current-node-key="category"
        highlight-current
        default-expand-all
        :expand-on-click-node="false"
        @node-click="(node) => pickCategory(node.key)"
      >
        <template #default="{ data }">
          <span class="node">
            <span class="node-name">{{ data.label }}</span>
            <!-- 绑定的账号登录失效时在树上就提醒，免得提交时才发现 -->
            <PlatformIcon v-if="data.account" :platform="data.account.platform" :size="14" :class="{ dim: data.account.status !== 'active' }" />
            <span v-if="data.account && data.account.status !== 'active'" class="warn">需重新登录</span>
          </span>
        </template>
      </el-tree>
    </div>
    <div class="main mp-panel">
      <div class="toolbar">
        <span class="filters">
          <el-radio-group v-model="filter" @change="load">
            <el-radio-button value="draft">草稿</el-radio-button>
            <el-radio-button value="pending">待审核</el-radio-button>
            <el-radio-button value="rejected">已退回</el-radio-button>
            <el-radio-button value="to_publish">待发布</el-radio-button>
            <el-radio-button value="publishing">发布中</el-radio-button>
            <el-radio-button value="scheduled">已定时</el-radio-button>
            <el-radio-button value="published">已发布</el-radio-button>
            <el-radio-button value="failed">发布失败</el-radio-button>
            <el-radio-button value="">全部</el-radio-button>
          </el-radio-group>
          <el-checkbox v-model="mine" @change="load">只看我提交的</el-checkbox>
        </span>
      </div>
      <el-table :data="posts" empty-text="没有内容">
        <el-table-column label="标题" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <StatusTag class="kind">{{ row.kind === 'article' ? '图文' : '视频' }}</StatusTag>
            <!-- el-link 是 inline-flex，标题过长时整个被截掉，所以用普通文字 -->
            <span class="title-link" @click="openDetail(row)">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="分类" min-width="80" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.category_id">{{ categoryPath(categories, row.category_id) }}</span>
            <span v-else class="tip">未分类</span>
          </template>
        </el-table-column>
        <el-table-column label="发布账号" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.account"><PlatformIcon :platform="row.account.platform" /> {{ row.account.display_name }}</template>
            <span v-else-if="row.account_name" class="tip">{{ row.account_name }}（已移除）</span>
            <span v-else-if="row.review_status === 'draft'" class="tip">未选择</span>
            <span v-else class="warn">账号已移除，请修改</span>
          </template>
        </el-table-column>
        <el-table-column label="定时" width="135">
          <template #default="{ row }">{{ row.scheduled_at ? formatTime(row.scheduled_at) : '立即' }}</template>
        </el-table-column>
        <el-table-column label="提交" width="135">
          <template #default="{ row }">
            <div>{{ row.creator_name || '-' }}</div>
            <div class="tip">{{ formatTime(row.updated_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="审核" width="90">
          <template #default="{ row }">
            <!-- 退回原因放在悬停提示里，省一列 -->
            <el-tooltip :disabled="!row.review_note" :content="`退回原因：${row.review_note}`" placement="top">
              <StatusTag :tone="REVIEW_STATUS[row.review_status].tone">{{ REVIEW_STATUS[row.review_status].label }}</StatusTag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="发布" width="100">
          <template #default="{ row }">
            <StatusTag v-if="row.publish_status" :tone="PUBLISH_STATUS[row.publish_status].tone">{{ PUBLISH_STATUS[row.publish_status].label }}</StatusTag>
            <StatusTag v-else-if="row.review_status === 'approved'" tone="blue">未发布</StatusTag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <!-- 审核要先看内容，在详情里通过或退回 -->
            <el-button v-if="row.review_status === 'pending'" link type="success" @click="openDetail(row)">审核</el-button>
            <el-button v-if="row.review_status === 'approved' && !row.publish_status" link type="primary" @click="openPublish(row)">发布</el-button>
            <el-button v-if="row.publish_status" link type="primary" @click="$router.push({ name: 'tasks' })">发布记录</el-button>
            <template v-if="isEditable(row)">
              <el-button link type="primary" @click="edit(row)">修改</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
            <el-button link type="primary" @click="copy(row)">复制</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="detailVisible" :title="detail?.title" size="50%">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="审核状态">{{ REVIEW_STATUS[detail.review_status].label }}</el-descriptions-item>
          <el-descriptions-item label="发布状态">
            {{ detail.publish_status ? PUBLISH_STATUS[detail.publish_status].label : detail.review_status === 'approved' ? '未发布' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.review_note" label="审核意见">{{ detail.review_note }}</el-descriptions-item>
          <el-descriptions-item label="发布账号">
            <template v-if="!detail.account">{{ detail.account_name ? `${detail.account_name}（已移除）` : '-' }}</template>
            <template v-else>
              {{ PLATFORMS[detail.account.platform] }} · {{ detail.account.display_name }}
              <span v-if="detail.account.status !== 'active'" class="warn">（登录已失效）</span>
            </template>
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
          <el-button v-if="detail.review_status === 'approved' && !detail.publish_status" type="primary" @click="openPublish(detail)">发布</el-button>
          <el-button v-if="isEditable(detail)" @click="edit(detail)">修改</el-button>
          <el-button @click="copy(detail)">复制</el-button>
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
      <VideoForm v-if="videoFormVisible" ref="formRef" :post-id="editingId" :copy-from="copyingId" :categories="categories" :category-id="formCategory" @saved="formSaved" @cancel="closeForm" />
    </el-dialog>
    <el-drawer
      v-model="articleFormVisible"
      :title="`${editingId ? '修改' : copyingId ? '复制' : '发布'}图文（微信公众号）`"
      size="min(960px, 92%)"
      :before-close="beforeFormClose"
      @closed="resetForm"
    >
      <ArticleForm v-if="articleFormVisible" ref="formRef" :post-id="editingId" :copy-from="copyingId" :categories="categories" :category-id="formCategory" @saved="formSaved" @cancel="closeForm" />
    </el-drawer>

    <el-dialog v-model="copyVisible" title="复制到分类" width="440px">
      <p>《{{ copying?.title }}》复制到：</p>
      <el-tree-select
        v-model="copyTarget"
        :data="copyTree"
        :props="{ label: 'label', children: 'children', disabled: 'disabled' }"
        node-key="id"
        check-strictly
        default-expand-all
        placeholder="选择分类"
        style="width: 100%"
      >
        <template #default="{ data }">
          {{ data.label }}<span v-if="data.account" class="tip">（{{ PLATFORMS[data.account.platform] }} · {{ data.account.display_name }}）</span>
        </template>
      </el-tree-select>
      <div class="tip copy-tip">发到目标分类绑定的账号；{{ copying?.kind === 'article' ? '图文只能复制到绑定了公众号的分类' : '视频只能复制到绑定了视频渠道的分类' }}</div>
      <template #footer>
        <el-button @click="copyVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCopy">下一步</el-button>
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
import { Plus } from '@element-plus/icons-vue'

import api from '../api'
import ArticleForm from '../components/ArticleForm.vue'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import StatusTag from '../components/StatusTag.vue'
import VideoForm from '../components/VideoForm.vue'
import { buildTree, categoryKind, categoryPath } from '../categories'
import { cleanHtml } from '../html'
import { PLATFORMS, PUBLISH_STATUS, REVIEW_STATUS, VIDEO_OPTION_LABELS, formatTime, isEditable } from '../platforms'

const route = useRoute()
const router = useRouter()
const filter = ref(route.query.status ?? 'pending')
const posts = ref([])
const categories = ref([])
// 左侧选中的分类：'all' 全部、'none' 未分类，其余是分类 id（包含下级分类的内容）
const category = ref('all')
const mine = ref(false)
const copyVisible = ref(false)
const copying = ref(null)
const copyTarget = ref(null)
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
// 新建、复制时内容放进的分类，账号由它决定；修改时不用（分类不能改）
const formCategory = ref(null)
const formRef = ref(null)
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))

const articleHtml = computed(() => cleanHtml(detail.value?.content ?? ''))

const sideTree = computed(() => {
  const toNode = (c) => ({ key: c.id, label: c.name, account: c.account, children: c.children.map(toNode) })
  return [{ key: 'all', label: '全部' }, { key: 'none', label: '未分类' }, ...buildTree(categories.value).map(toNode)]
})
const current = computed(() => categories.value.find((c) => c.id === category.value) ?? null)
const currentKind = computed(() => categoryKind(current.value))

// 复制只能到绑定了同类渠道的分类（视频到视频渠道、图文到公众号）
const copyTree = computed(() => {
  const toNode = (c) => ({
    id: c.id,
    label: c.name,
    account: c.account,
    disabled: categoryKind(c) !== copying.value?.kind,
    children: c.children.map(toNode),
  })
  return buildTree(categories.value).map(toNode)
})

async function load() {
  const params = {}
  if (filter.value) params.status = filter.value
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

// 选中的是没绑定账号的分类时，直接打开它的修改窗口去绑定
function goSetup() {
  router.push({ name: 'categories', query: current.value ? { edit: current.value.id } : {} })
}

function pickCategory(key) {
  category.value = key
  load()
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

function openForm(kind, postId = null, copyFrom = null, categoryId = category.value) {
  editingId.value = postId
  copyingId.value = copyFrom
  formCategory.value = postId ? null : categoryId
  if (kind === 'article') articleFormVisible.value = true
  else videoFormVisible.value = true
}

async function edit(row) {
  if (row.publish_status === 'failed') {
    // 有些失败发生在点了平台的发布按钮之后，作品可能其实已经发出去了
    await ElMessageBox.confirm(
      '上次发布失败。修改前请先到平台后台确认作品没有发出去，以免重复发布。修改后需要重新审核、重新发布。',
      '修改发布失败的内容',
      { type: 'warning', confirmButtonText: '继续修改' },
    )
  }
  detailVisible.value = false
  openForm(row.kind, row.id)
}

// 复制内容和视频到另一个分类，发到那个分类绑定的账号
function copy(row) {
  copying.value = row
  // 当前分类能放就默认放这里
  copyTarget.value = currentKind.value === row.kind ? category.value : null
  copyVisible.value = true
}

function confirmCopy() {
  if (!copyTarget.value) return ElMessage.warning('请选择分类')
  copyVisible.value = false
  detailVisible.value = false
  openForm(copying.value.kind, null, copying.value.id, copyTarget.value)
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

async function formSaved(draft) {
  videoFormVisible.value = false
  articleFormVisible.value = false
  // 跳到刚保存的内容所在的分组
  filter.value = draft ? 'draft' : 'pending'
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
  box-sizing: border-box;
  padding: 12px;
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  padding: 0 4px 0 8px;
  margin-bottom: 4px;
  font-weight: 600;
}
.main {
  flex: 1;
  min-width: 0;
  padding: 12px 16px 16px;
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
  gap: 16px;
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
.kind {
  margin-right: 6px;
}
.title-link {
  color: var(--el-color-primary);
  cursor: pointer;
}
.title-link:hover {
  text-decoration: underline;
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
.copy-tip {
  margin-top: 8px;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.node {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.dim {
  opacity: 0.4;
}
.publish-form {
  margin-top: 16px;
}
</style>
