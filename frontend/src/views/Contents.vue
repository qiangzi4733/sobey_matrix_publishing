<template>
  <PageHeader title="内容管理">
    <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索标题" clearable class="search" />
    <el-checkbox v-model="mine" @change="load">只看我提交的</el-checkbox>
    <!-- 新建先选分类：分类决定发到哪个账号、发视频还是图文 -->
    <el-dropdown trigger="click" placement="bottom-end" @command="createIn">
      <el-button type="primary" :icon="Plus">新建内容<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu class="create-menu">
          <li class="create-title" role="presentation">发到哪个分类？</li>
          <template v-if="createGroups.length">
            <template v-for="group in createGroups" :key="group.kind">
              <li class="create-group" role="presentation">{{ group.label }}</li>
              <el-dropdown-item v-for="c in group.items" :key="c.id" :command="c.id">
                <span class="create-item">
                  <PlatformIcon :platform="c.account.platform" :size="22" />
                  <span class="create-text">
                    <span>{{ categoryPath(categories, c.id) }}</span>
                    <span :class="c.account.status === 'active' ? 'tip' : 'warn'">
                      {{ PLATFORMS[c.account.platform] }} {{ c.account.display_name }}{{ c.account.status === 'active' ? '' : ' · 登录已失效，可以先写稿' }}
                    </span>
                  </span>
                  <span v-if="c.id === category" class="tip">当前分类</span>
                </span>
              </el-dropdown-item>
            </template>
          </template>
          <li v-else class="create-empty tip" role="presentation">还没有绑定了账号的分类</li>
          <li class="create-foot tip" role="presentation">没有合适的分类？<el-button link type="primary" @click="goSetup">去给分类绑定账号</el-button></li>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
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
            <span v-if="data.account" class="node-account" :class="{ warn: data.account.status !== 'active' }">
              <PlatformIcon :platform="data.account.platform" :size="12" />
              {{ data.account.display_name }}{{ data.account.status !== 'active' ? ' · 需重新登录' : '' }}
            </span>
          </span>
        </template>
      </el-tree>
    </div>
    <div class="main mp-panel">
      <div class="tabs" role="tablist" aria-label="按状态筛选">
        <template v-for="tab in POST_TABS" :key="tab.key">
          <span v-if="tab.key === 'draft' || tab.key === 'to_publish'" class="tab-sep" aria-hidden="true" />
          <button
            type="button"
            role="tab"
            class="tab"
            :class="{ active: filter === tab.key }"
            :aria-selected="filter === tab.key"
            @click="pickFilter(tab.key)"
          >
            {{ tab.label }}
            <span class="tab-count" :class="{ urgent: tab.urgent && counts[tab.key || 'all'] }">{{ counts[tab.key || 'all'] ?? 0 }}</span>
          </button>
        </template>
      </div>
      <el-table :data="shownPosts" empty-text="没有内容" @row-click="openDetail" row-class-name="row">
        <el-table-column label="内容" min-width="260">
          <template #default="{ row }">
            <div class="content-cell">
              <img v-if="row.cover_url" :src="row.cover_url" class="thumb" :class="row.kind" alt="" />
              <span v-else class="thumb placeholder" :class="row.kind" aria-hidden="true">
                <el-icon :size="16"><VideoPlay v-if="row.kind === 'video'" /><Document v-else /></el-icon>
              </span>
              <span class="content-text">
                <span class="title">{{ row.title }}</span>
                <span class="tip">{{ row.kind === 'article' ? '图文' : '视频' }} · {{ categoryPath(categories, row.category_id) || '未分类' }}</span>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布账号" min-width="140">
          <template #default="{ row }">
            <span v-if="row.account" class="with-icon"><PlatformIcon :platform="row.account.platform" :size="18" />{{ row.account.display_name }}</span>
            <span v-else-if="row.account_name" class="tip">{{ row.account_name }}（已移除）</span>
            <span v-else-if="row.review_status === 'draft'" class="tip">未选择</span>
            <span v-else class="warn">账号已移除，请修改</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <div class="status-cell">
              <StatusTag :tone="POST_STATUS[postStatus(row)].tone">{{ postStatusLabel(row) }}</StatusTag>
              <span v-if="row.review_status === 'rejected' && row.review_note" class="warn ellipsis" :title="row.review_note">{{ row.review_note }}</span>
              <span v-else-if="row.account && row.account.status !== 'active' && postStatus(row) !== 'published'" class="warn">账号登录失效</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="150">
          <template #default="{ row }">
            <div>{{ rowTime(row).value }}</div>
            <div class="tip">{{ rowTime(row).label }}</div>
          </template>
        </el-table-column>
        <el-table-column label="提交人" width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ row.creator_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="right">
          <template #default="{ row }">
            <!-- 点行打开详情，按钮要拦住冒泡 -->
            <span class="ops" @click.stop>
              <el-button v-if="primaryAction(row)" size="small" :type="primaryAction(row).type" @click="primaryAction(row).run(row)">
                {{ primaryAction(row).label }}
              </el-button>
              <el-dropdown trigger="click" @command="(cmd) => moreAction(cmd, row)">
                <el-button size="small" text :icon="MoreFilled" aria-label="更多操作" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="detail">详情</el-dropdown-item>
                    <el-dropdown-item v-if="isEditable(row) && primaryAction(row)?.label !== '修改' && primaryAction(row)?.label !== '继续编辑'" command="edit">修改</el-dropdown-item>
                    <el-dropdown-item command="copy">复制到其他分类</el-dropdown-item>
                    <el-dropdown-item v-if="isEditable(row)" command="remove" divided class="danger-item">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="detailVisible" :with-header="false" size="min(720px, 92%)" class="detail-drawer">
      <PostDetail
        v-if="detail"
        :post="detail"
        :categories="categories"
        @close="detailVisible = false"
        @refresh="refresh"
        @approve="approve"
        @reject="openReject"
        @publish="openPublish"
        @edit="edit"
        @copy="copy"
        @remove="remove"
      />
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
import { ArrowDown, Document, MoreFilled, Plus, Search, VideoPlay } from '@element-plus/icons-vue'

import api from '../api'
import ArticleForm from '../components/ArticleForm.vue'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import PostDetail from '../components/PostDetail.vue'
import StatusTag from '../components/StatusTag.vue'
import VideoForm from '../components/VideoForm.vue'
import { buildTree, categoryKind, categoryPath } from '../categories'
import { refreshBadges } from '../badges'
import { PLATFORMS, POST_STATUS, POST_TABS, formatTime, isEditable, postStatus, postStatusLabel } from '../platforms'

const route = useRoute()
const router = useRouter()
const filter = ref(route.query.status ?? 'pending')
const posts = ref([])
const counts = ref({})
const keyword = ref('')
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

// 搜索只在已加载的这一页里按标题过滤
const shownPosts = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return k ? posts.value.filter((p) => p.title.toLowerCase().includes(k)) : posts.value
})

// 新建菜单：绑定了账号的分类按视频、图文分组，当前选中的分类排在最前
const createGroups = computed(() => {
  const groups = [
    { kind: 'video', label: '视频', items: [] },
    { kind: 'article', label: '图文', items: [] },
  ]
  for (const c of categories.value) groups.find((g) => g.kind === categoryKind(c))?.items.push(c)
  for (const g of groups) g.items.sort((a, b) => (b.id === category.value) - (a.id === category.value))
  return groups.filter((g) => g.items.length)
})

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
  if (category.value === 'none') params.uncategorized = true
  else if (category.value !== 'all') params.category_id = category.value
  if (mine.value) params.mine = true
  const [list, count] = await Promise.all([
    api.get('/posts', { params: filter.value ? { ...params, status: filter.value } : params }),
    // 页签上的数量跟着分类、「只看我提交的」筛选
    api.get('/posts/counts', { params }),
  ])
  posts.value = list.data
  counts.value = count.data
  refreshBadges()
}

function pickFilter(key) {
  filter.value = key
  router.replace({ query: { ...route.query, status: key } })
  load()
}

function createIn(categoryId) {
  const c = categories.value.find((item) => item.id === categoryId)
  openForm(categoryKind(c), null, null, categoryId)
}

// 时间列：定时的显示定时，审核过的显示审核时间，其他显示最后修改
function rowTime(row) {
  if (row.scheduled_at) return { value: formatTime(row.scheduled_at), label: '定时' }
  if (row.reviewed_at && row.review_status !== 'pending') {
    return { value: formatTime(row.reviewed_at), label: row.review_status === 'rejected' ? '退回' : '审核通过' }
  }
  return { value: formatTime(row.updated_at), label: row.review_status === 'draft' ? '最后保存' : '提交' }
}

// 每行只放一个最该做的操作，其余在「更多」里
function primaryAction(row) {
  switch (postStatus(row)) {
    case 'draft':
      return { label: '继续编辑', type: 'default', run: edit }
    case 'pending':
      // 审核要先看内容，在详情里通过或退回
      return { label: '审核', type: 'primary', run: openDetail }
    case 'rejected':
      return { label: '修改', type: 'default', run: edit }
    case 'to_publish':
      return { label: '发布', type: 'primary', run: openPublish }
    case 'failed':
      return { label: '查看原因', type: 'default', run: openDetail }
    default:
      return null
  }
}

function moreAction(command, row) {
  ;({ detail: openDetail, edit, copy, remove })[command](row)
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
    ElMessage.success('已提交发布，可以在详情里看进度')
    await load()
    await openDetail(publishing.value)
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
.search {
  width: 220px;
}
.side {
  flex: 0 0 220px;
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
/* 分类名下面一行显示绑定的账号，树节点要比默认的高 */
.side :deep(.el-tree-node__content) {
  height: auto;
  min-height: 32px;
  padding-top: 4px;
  padding-bottom: 4px;
  border-radius: 6px;
}
.node {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.node-account {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.main {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.tabs {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--mp-panel-border);
  overflow-x: auto;
}
.tab {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-regular);
  font: inherit;
  cursor: pointer;
}
.tab:hover {
  background: var(--el-fill-color-light);
}
.tab.active {
  background: var(--mp-nav-active-bg);
  color: var(--mp-nav-active-fg);
  font-weight: 600;
}
.tab-count {
  min-width: 16px;
  padding: 0 5px;
  border-radius: 9px;
  background: #f0f1f3;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
  line-height: 18px;
  text-align: center;
}
.tab-count.urgent {
  background: #fff1d6;
  color: #8a5300;
}
.tab-sep {
  flex: none;
  width: 1px;
  height: 18px;
  margin: 0 6px;
  background: var(--mp-panel-border);
}
.main :deep(.row) {
  cursor: pointer;
}
.content-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.thumb {
  flex: none;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
}
/* 视频竖封面 3:4，图文封面横的 */
.thumb.video {
  width: 36px;
}
.thumb.article {
  width: 64px;
}
.thumb.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8ebf1;
  color: var(--el-text-color-secondary);
}
.content-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.title {
  font-weight: 500;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.with-icon {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
}
.ellipsis {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ops {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.warn {
  color: #b42318;
  font-size: 12px;
}
.copy-tip {
  margin-top: 8px;
}
.publish-form {
  margin-top: 16px;
}
.create-menu {
  width: 340px;
}
.create-title {
  padding: 8px 16px;
  font-weight: 600;
}
.create-group {
  padding: 8px 16px 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.create-menu :deep(.el-dropdown-menu__item),
.create-menu.el-dropdown-menu .el-dropdown-menu__item {
  padding: 8px 16px;
  line-height: 1.4;
}
.create-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
.create-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.create-empty {
  margin: 0;
  padding: 8px 16px;
}
.create-foot {
  margin-top: 4px;
  padding: 10px 16px 6px;
  border-top: 1px solid var(--mp-panel-border);
}
.danger-item {
  color: var(--el-color-danger);
}
</style>
<style>
/* 抽屉挂在 body 下，scoped 样式管不到；详情自己排版，去掉默认内边距 */
.detail-drawer .el-drawer__body {
  padding: 0;
}
</style>
