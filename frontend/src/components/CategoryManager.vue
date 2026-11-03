<template>
  <div>
    <div class="toolbar">
      <el-button type="primary" @click="openEdit(null)">新建分类</el-button>
      <span class="tip">最多 {{ CATEGORY_MAX_DEPTH }} 层；有内容或下级分类的不能删除</span>
    </div>
    <el-table :data="tree" row-key="id" default-expand-all :tree-props="{ children: 'children' }" empty-text="还没有分类">
      <el-table-column prop="name" label="分类名称" min-width="200" />
      <el-table-column prop="post_count" label="内容数" width="80" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button v-if="depthOf(row.id) < CATEGORY_MAX_DEPTH" link type="primary" @click="openEdit(null, row.id)">新建下级</el-button>
          <el-button link type="primary" @click="openEdit(row)">修改</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" :title="editing ? '修改分类' : '新建分类'" width="440px" append-to-body>
      <el-form label-width="90px" @submit.prevent>
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
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" @click="save">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { CATEGORY_MAX_DEPTH, buildTree } from '../categories'

const props = defineProps({ categories: { type: Array, required: true } })
const emit = defineEmits(['changed'])

const tree = computed(() => buildTree(props.categories))
const editVisible = ref(false)
const editing = ref(null)
const busy = ref(false)
const form = reactive({ name: '', parentId: null })

const parentOf = (id) => props.categories.find((c) => c.id === id)?.parent_id ?? null
const childrenOf = (id) => props.categories.filter((c) => c.parent_id === id)

function depthOf(id) {
  let depth = 0
  for (let c = id; c != null; c = parentOf(c)) depth += 1
  return depth
}

function heightOf(id) {
  return 1 + Math.max(0, ...childrenOf(id).map((c) => heightOf(c.id)))
}

// 修改时不能选自己和下级；选了之后总层数不能超限（连同自己的下级一起算）
const parentTree = computed(() => {
  const self = editing.value?.id
  const height = self ? heightOf(self) : 1
  const mark = (nodes, depth, inSelf) =>
    nodes.map((n) => {
      const blocked = inSelf || n.id === self
      return { ...n, disabled: blocked || depth + height > CATEGORY_MAX_DEPTH, children: mark(n.children, depth + 1, blocked) }
    })
  return mark(tree.value, 1, false)
})

function openEdit(row, parentId = null) {
  editing.value = row
  form.name = row?.name ?? ''
  form.parentId = row ? row.parent_id : parentId
  editVisible.value = true
}

async function save() {
  if (!form.name.trim()) return ElMessage.warning('请填写分类名称')
  busy.value = true
  try {
    const body = { name: form.name.trim(), parent_id: form.parentId ?? null }
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
</style>
