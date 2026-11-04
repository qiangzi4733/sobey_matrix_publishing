<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openEdit(null)">新建分类</el-button>
      <span class="tip">绑定了账号的分类才能新建内容，下级分类不沿用上级的绑定；有内容或下级分类的不能删除</span>
    </div>
    <el-table :data="tree" row-key="id" default-expand-all :tree-props="{ children: 'children' }" empty-text="还没有分类">
      <el-table-column prop="name" label="分类名称" min-width="180" />
      <el-table-column label="绑定账号" min-width="180">
        <template #default="{ row }">
          <span v-if="row.account" class="account">
            <PlatformIcon :platform="row.account.platform" />
            {{ row.account.display_name }}
            <span v-if="row.account.status !== 'active'" class="warn">（需重新登录）</span>
          </span>
          <span v-else class="tip">未绑定</span>
        </template>
      </el-table-column>
      <el-table-column prop="post_count" label="内容数" width="80" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(null, row.id)">新建下级</el-button>
          <el-button link type="primary" @click="openEdit(row)">修改</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" :title="editing ? '修改分类' : '新建分类'" width="440px" append-to-body>
      <el-form label-width="100px" @submit.prevent>
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
        <el-form-item label="分类名称" required>
          <el-input v-model="form.name" maxlength="50" @keyup.enter="save" />
        </el-form-item>
        <el-form-item label="新媒体渠道">
          <el-select v-model="form.platform" clearable placeholder="不绑定" style="width: 100%">
            <el-option v-for="(label, key) in PLATFORMS" :key="key" :value="key" :label="label" :disabled="!PUBLISHABLE.includes(key)">
              <span class="account"><PlatformIcon :platform="key" /> {{ label }}</span>
              <span v-if="!PUBLISHABLE.includes(key)" class="tip">（暂未开放）</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.platform" label="渠道账号" required>
          <el-select v-model="form.accountId" placeholder="请选择账号" style="width: 100%">
            <el-option v-for="a in platformAccounts" :key="a.id" :value="a.id" :label="a.display_name">
              {{ a.display_name }}
              <span v-if="a.status !== 'active'" class="tip">（需重新登录）</span>
            </el-option>
          </el-select>
          <div v-if="!platformAccounts.length" class="tip">还没有{{ PLATFORMS[form.platform] }}账号，请先到「账号管理」添加</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="save">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { buildTree } from '../categories'
import { ARTICLE_PLATFORMS, PLATFORMS, VIDEO_PLATFORMS } from '../platforms'
import PlatformIcon from './PlatformIcon.vue'

const props = defineProps({ categories: { type: Array, required: true } })
const emit = defineEmits(['changed'])

// 快手还不能发布，渠道下拉里列出但不能选
const PUBLISHABLE = [...VIDEO_PLATFORMS, ...ARTICLE_PLATFORMS]

const tree = computed(() => buildTree(props.categories))
const editVisible = ref(false)
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
  editVisible.value = true
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
    if (editing.value) await api.put(`/categories/${editing.value.id}`, body)
    else await api.post('/categories', body)
    editVisible.value = false
    ElMessage.success('已保存')
    emit('changed')
  } finally {
    busy.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`删除分类「${row.name}」？`, '删除', { type: 'warning' })
  await api.delete(`/categories/${row.id}`)
  ElMessage.success('已删除')
  emit('changed')
}
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.warn {
  color: var(--el-color-danger);
  font-size: 12px;
}
.account {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
