<template>
  <div>
    <PageHeader title="分类管理" description="内容建在哪个分类，就发到这个分类绑定的账号。下级分类不沿用上级的绑定。">
      <el-button type="primary" :icon="Plus" @click="openDialog(null)">新建分类</el-button>
    </PageHeader>

    <section class="tree-panel mp-panel" aria-label="分类列表">
      <div class="tree-head">
        <span>分类名称</span>
        <span>发布到</span>
        <span class="count-col">内容数量</span>
        <span class="ops-col">操作</span>
      </div>
      <el-tree
        v-if="tree.length"
        :data="tree"
        node-key="id"
        :props="{ label: 'name', children: 'children' }"
        default-expand-all
        :expand-on-click-node="false"
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
              <span v-else class="tip">未绑定 · 不能在这里新建内容</span>
            </span>
            <span class="count-col">{{ data.post_count }}</span>
            <span class="ops-col" @click.stop>
              <el-button link type="primary" @click="openDialog(null, data.id)">加下级</el-button>
              <el-button link type="primary" @click="openDialog(data)">修改</el-button>
              <el-button link type="danger" @click="remove(data)">删除</el-button>
            </span>
          </span>
        </template>
      </el-tree>
      <p v-else class="empty tip">还没有分类，点右上角「新建分类」</p>
    </section>

    <el-dialog v-model="dialogOpen" :title="editing ? '修改分类' : '新建分类'" width="520px" :close-on-click-modal="false" destroy-on-close>
      <el-form label-width="84px" @submit.prevent="save">
        <el-form-item label="上级分类">
          <el-tree-select
            v-model="form.parentId"
            :data="parentTree"
            :props="{ label: 'name', children: 'children', disabled: 'disabled' }"
            node-key="id"
            check-strictly
            default-expand-all
            clearable
            placeholder="无（一级分类）"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="分类名称" required>
          <el-input v-model="form.name" maxlength="50" placeholder="如：体育学院、校报专栏" />
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
        <el-form-item v-if="form.platform" label="渠道账号" required>
          <div class="account-list" role="radiogroup" aria-label="渠道账号">
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
        <p v-if="editing?.post_count" class="note">改绑定只影响之后：已提交的内容仍发到原来的账号，草稿提交审核时改用新账号。</p>
        <!-- 让回车能提交 -->
        <button type="submit" hidden />
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="save">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import api from '../api'
import { buildTree } from '../categories'
import PageHeader from '../components/PageHeader.vue'
import PlatformIcon from '../components/PlatformIcon.vue'
import { ARTICLE_PLATFORMS, PLATFORMS, VIDEO_PLATFORMS } from '../platforms'

const route = useRoute()
const router = useRouter()

// 快手还不能发布，渠道下拉里列出但不能选
const PUBLISHABLE = [...VIDEO_PLATFORMS, ...ARTICLE_PLATFORMS]

const categories = ref([])
const tree = computed(() => buildTree(categories.value))
const dialogOpen = ref(false)
// 正在修改的分类，新建时为 null
const editing = ref(null)
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

async function openDialog(row, parentId = null) {
  editing.value = row
  Object.assign(form, {
    name: row?.name ?? '',
    parentId: row ? row.parent_id : parentId,
    platform: row?.account?.platform ?? null,
    accountId: row?.account?.id ?? null,
  })
  dialogOpen.value = true
  // 每次打开都重新取：账号可能刚在「账号管理」里添加或移除
  accounts.value = (await api.get('/accounts')).data
}

async function save() {
  if (busy.value) return
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
    if (editing.value) await api.put(`/categories/${editing.value.id}`, body)
    else await api.post('/categories', body)
    ElMessage.success('已保存')
    dialogOpen.value = false
    await load()
  } finally {
    busy.value = false
  }
}

async function remove(row) {
  // 后端也会拦，这里先给出原因，免得客户点了才知道
  if (row.children?.length) return ElMessage.warning('这个分类下还有下级分类，先删除下级分类')
  if (row.post_count) return ElMessage.warning('这个分类里还有内容，不能删除')
  await ElMessageBox.confirm(`删除分类「${row.name}」？`, '删除', { type: 'warning' })
  await api.delete(`/categories/${row.id}`)
  ElMessage.success('已删除')
  await load()
}

async function load() {
  categories.value = (await api.get('/categories')).data
}

onMounted(async () => {
  await load()
  // 从内容管理的「去设置」过来时，直接打开那个分类的修改窗口
  const row = categories.value.find((c) => c.id === Number(route.query.edit))
  if (row) {
    router.replace({ query: {} })
    await openDialog(row)
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
.tree-panel {
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
  flex: 0 0 64px;
}
.ops-col {
  flex: 0 0 150px;
  text-align: right;
}
.ops-col .el-button + .el-button {
  margin-left: 10px;
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
.empty {
  padding: 24px 8px;
  margin: 0;
  text-align: center;
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
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--mp-page-bg);
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}
</style>
