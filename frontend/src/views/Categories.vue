<template>
  <div>
    <PageHeader title="分类与绑定" description="内容建在哪个分类，就发到这个分类绑定的账号。下级分类不沿用上级的绑定。">
      <el-button type="primary" :icon="Plus" @click="startCreate(null)">新建一级分类</el-button>
    </PageHeader>

    <div class="layout">
      <section class="tree-panel mp-panel" aria-label="分类树">
        <div class="tree-head">
          <span>分类</span>
          <span>发布到</span>
          <span class="count-col">内容</span>
        </div>
        <el-tree
          v-if="tree.length"
          :data="tree"
          node-key="id"
          :props="{ label: 'name', children: 'children' }"
          :current-node-key="selectedId"
          highlight-current
          default-expand-all
          :expand-on-click-node="false"
          @node-click="(node) => select(node.id)"
        >
          <template #default="{ data }">
            <span class="row">
              <span class="row-name">{{ data.name }}</span>
              <span class="row-account">
                <span v-if="data.account" class="chip" :class="{ warn: data.account.status !== 'active' }">
                  <PlatformIcon :platform="data.account.platform" :size="14" />
                  {{ data.account.display_name }}
                  <template v-if="data.account.status !== 'active'"> · 需重新登录</template>
                </span>
                <span v-else class="tip">未绑定<span class="unbound-hint"> · 不能在这里新建内容</span></span>
              </span>
              <span class="count-col">{{ data.post_count }}</span>
              <span class="row-ops" @click.stop>
                <el-button link type="primary" @click="startCreate(data.id)">加下级</el-button>
              </span>
            </span>
          </template>
        </el-tree>
        <p v-else class="empty tip">还没有分类，点右上角「新建一级分类」</p>
      </section>

      <aside ref="panel" class="edit-panel mp-panel" aria-label="编辑分类">
        <template v-if="mode">
          <div class="edit-head">
            <span class="tip">{{ mode === 'edit' ? parentLabel(editing.parent_id) : '新建分类' }}</span>
            <h2>{{ mode === 'edit' ? editing.name : form.parentId ? `在「${nameOf(form.parentId)}」下新建` : '新建一级分类' }}</h2>
          </div>
          <el-form label-position="top" @submit.prevent="save">
            <el-form-item label="分类名称" required>
              <el-input v-model="form.name" maxlength="50" placeholder="如：体育学院、校报专栏" />
            </el-form-item>
            <el-form-item label="上级分类">
              <el-tree-select
                v-model="form.parentId"
                :data="parentTree"
                :props="{ label: 'name', children: 'children', disabled: 'disabled' }"
                node-key="id"
                check-strictly
                default-expand-all
                clearable
                placeholder="无（第一层）"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="发布渠道">
              <div class="channels" role="radiogroup" aria-label="发布渠道">
                <label class="choice" :class="{ active: !form.platform }">
                  <input v-model="form.platform" type="radio" :value="null" />
                  <span>不绑定</span>
                </label>
                <label
                  v-for="(label, key) in PLATFORMS"
                  :key="key"
                  class="choice"
                  :class="{ active: form.platform === key, disabled: !PUBLISHABLE.includes(key) }"
                >
                  <input v-model="form.platform" type="radio" :value="key" :disabled="!PUBLISHABLE.includes(key)" />
                  <PlatformIcon :platform="key" :size="18" />
                  <span>{{ label }}{{ PUBLISHABLE.includes(key) ? '' : '（未开放）' }}</span>
                </label>
              </div>
            </el-form-item>
            <el-form-item v-if="form.platform" label="账号" required>
              <div class="account-list" role="radiogroup" aria-label="账号">
                <label v-for="a in platformAccounts" :key="a.id" class="choice account" :class="{ active: form.accountId === a.id }">
                  <input v-model="form.accountId" type="radio" :value="a.id" />
                  <img v-if="a.avatar_url" :src="a.avatar_url" referrerpolicy="no-referrer" class="avatar" alt="" />
                  <span v-else class="avatar initial" aria-hidden="true">{{ a.display_name.slice(0, 1) }}</span>
                  <span class="account-text">
                    <span>{{ a.display_name }}</span>
                    <span :class="a.status === 'active' ? 'tip' : 'warn'">
                      {{ a.status === 'active' ? '登录正常' : '需重新登录' }} · 已绑定 {{ boundCount(a.id) }} 个分类
                    </span>
                  </span>
                </label>
                <span v-if="!platformAccounts.length" class="tip">还没有{{ PLATFORMS[form.platform] }}账号</span>
                <el-button link type="primary" class="add-link" @click="router.push({ name: 'accounts' })">+ 添加{{ PLATFORMS[form.platform] }}账号</el-button>
              </div>
            </el-form-item>
            <p v-if="mode === 'edit' && editing.post_count" class="note">改绑定只影响之后：已提交的内容仍发到原来的账号，草稿提交审核时改用新账号。</p>
            <div class="edit-actions">
              <el-button type="primary" native-type="submit" :loading="busy">保存</el-button>
              <el-button @click="cancel">取消</el-button>
              <span class="spacer" />
              <el-button v-if="mode === 'edit'" text type="danger" @click="remove(editing)">删除分类</el-button>
            </div>
          </el-form>
        </template>
        <div v-else class="edit-empty">
          <el-icon :size="28"><FolderOpened /></el-icon>
          <p>点左边的分类查看和修改绑定，<br />或新建一个分类。</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, Plus } from '@element-plus/icons-vue'

import api from '../api'
import { buildTree } from '../categories'
import { useMobile } from '../useMobile'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import { ARTICLE_PLATFORMS, PLATFORMS, VIDEO_PLATFORMS } from '../platforms'

const route = useRoute()
const isMobile = useMobile()
const panel = ref(null)
const router = useRouter()

// 快手还不能发布，渠道下拉里列出但不能选
const PUBLISHABLE = [...VIDEO_PLATFORMS, ...ARTICLE_PLATFORMS]

const categories = ref([])
const tree = computed(() => buildTree(categories.value))
// 右边面板：'edit' 修改选中的分类，'create' 新建，null 没选
const mode = ref(null)
const editing = ref(null)
const selectedId = computed(() => (mode.value === 'edit' ? editing.value?.id : null))
const busy = ref(false)
const accounts = ref([])
const form = reactive({ name: '', parentId: null, platform: null, accountId: null })

const platformAccounts = computed(() => accounts.value.filter((a) => a.platform === form.platform))

// 换了渠道，原来选的账号不属于新渠道了
watch(
  () => form.platform,
  () => {
    if (!platformAccounts.value.some((a) => a.id === form.accountId)) form.accountId = null
  },
)

const nameOf = (id) => categories.value.find((c) => c.id === id)?.name ?? ''
const parentLabel = (id) => (id ? `${nameOf(id)} /` : '一级分类')
const boundCount = (accountId) => categories.value.filter((c) => c.account?.id === accountId).length

// 修改时不能选自己和下级
const parentTree = computed(() => {
  const self = editing.value?.id
  const mark = (nodes, inSelf) =>
    nodes.map((n) => {
      const blocked = inSelf || n.id === self
      return { ...n, disabled: blocked, children: mark(n.children, blocked) }
    })
  return mark(tree.value, false)
})

async function openEdit(row, parentId = null) {
  // 每次打开都重新取：账号可能刚在「账号管理」里添加或移除
  accounts.value = (await api.get('/accounts')).data
  editing.value = row
  Object.assign(form, {
    name: row?.name ?? '',
    parentId: row ? row.parent_id : parentId,
    platform: row?.account?.platform ?? null,
    accountId: row?.account?.id ?? null,
  })
  mode.value = row ? 'edit' : 'create'
}

async function select(id) {
  await openEdit(categories.value.find((c) => c.id === id))
  revealPanel()
}

async function startCreate(parentId) {
  await openEdit(null, parentId)
  revealPanel()
}

// 手机上编辑面板排在分类树下面，点了之后滚过去
function revealPanel() {
  if (isMobile.value) panel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function cancel() {
  mode.value = null
  editing.value = null
}

async function save() {
  if (!form.name.trim()) return ElMessage.warning('请填写分类名称')
  if (form.platform && !form.accountId) return ElMessage.warning('请选择渠道账号')
  const accountId = form.platform ? form.accountId : null
  const before = editing.value?.account?.id ?? null
  if (editing.value?.post_count && before && accountId !== before) {
    await ElMessageBox.confirm(
      '分类里已有的内容仍发到原来的账号（草稿除外，草稿提交审核时改用新账号），之后新建的内容发到新账号。',
      '修改绑定账号',
      { type: 'warning', confirmButtonText: '确定修改' },
    )
  }
  busy.value = true
  try {
    const body = { name: form.name.trim(), parent_id: form.parentId ?? null, account_id: accountId }
    const { data } = editing.value
      ? await api.put(`/categories/${editing.value.id}`, body)
      : await api.post('/categories', body)
    ElMessage.success('已保存')
    await load()
    // 保存后停在这个分类上，方便接着改
    await openEdit(categories.value.find((c) => c.id === data.id))
  } finally {
    busy.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`删除分类「${row.name}」？`, '删除', { type: 'warning' })
  await api.delete(`/categories/${row.id}`)
  ElMessage.success('已删除')
  cancel()
  await load()
}

async function load() {
  categories.value = (await api.get('/categories')).data
}

onMounted(async () => {
  await load()
  // 从内容管理的「去设置」过来时，直接选中那个分类
  const row = categories.value.find((c) => c.id === Number(route.query.edit))
  if (row) {
    router.replace({ query: {} })
    await openEdit(row)
  }
})
</script>

<style scoped>
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.warn {
  color: #b42318;
  font-size: 12px;
}
.layout {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-start;
}
.tree-panel {
  flex: 999 1 520px;
  min-width: 0;
  padding: 8px 12px 12px;
}
/* 树节点按层级缩进，名称列吃掉缩进，右边几列固定宽度才能上下对齐 */
.tree-head,
.row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.tree-head > :first-child,
.row-name {
  flex: 1;
  min-width: 0;
}
.tree-head > :nth-child(2),
.row-account {
  flex: 0 0 280px;
}
.count-col {
  flex: 0 0 40px;
}
.tree-head::after,
.row-ops {
  flex: 0 0 56px;
}
.tree-head::after {
  content: '';
}
.tree-head {
  /* 和树节点的展开箭头对齐 */
  padding: 8px 8px 8px 24px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  border-bottom: 1px solid var(--mp-panel-border);
  margin-bottom: 4px;
}
.tree-panel :deep(.el-tree-node__content) {
  height: 48px;
  border-radius: 8px;
}
.row {
  flex: 1;
  min-width: 0;
  padding-right: 8px;
}
.row-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-account {
  min-width: 0;
  overflow: hidden;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 2px 10px 2px 4px;
  border-radius: 14px;
  background: #f0f1f3;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip.warn {
  background: #fef0ef;
  color: #b42318;
}
.count-col {
  text-align: right;
  color: var(--el-text-color-regular);
}
.row-ops {
  text-align: right;
}
.empty {
  padding: 24px 8px;
  margin: 0;
  text-align: center;
}
.edit-panel {
  flex: 1 1 340px;
  max-width: 420px;
  box-sizing: border-box;
  padding: 20px;
  position: sticky;
  top: 24px;
}
.edit-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 16px;
}
h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  word-break: break-word;
}
.channels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}
.choice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  line-height: 1.4;
  cursor: pointer;
}
.choice.active {
  border-color: var(--el-color-primary);
  background: #f5f8ff;
}
.choice.disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.choice input {
  margin: 0;
  accent-color: var(--el-color-primary);
}
.account-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.choice.account {
  padding: 10px 12px;
}
.avatar {
  flex: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}
.avatar.initial {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #dde3f0;
  color: var(--mp-nav-active-fg);
  font-weight: 700;
}
.account-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.add-link {
  align-self: flex-start;
}
.note {
  margin: 0 0 16px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--mp-page-bg);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.edit-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.edit-actions .el-button + .el-button {
  margin-left: 0;
}
.spacer {
  flex: 1;
}
.edit-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}
.edit-empty p {
  margin: 0;
  line-height: 1.7;
}
@media (max-width: 768px) {
  .tree-head {
    display: none;
  }
  .row-account {
    flex-basis: 120px;
  }
  .count-col {
    display: none;
  }
  .edit-panel {
    position: static;
    max-width: none;
  }
}
@media (max-width: 768px) {
  .unbound-hint {
    display: none;
  }
}
</style>
