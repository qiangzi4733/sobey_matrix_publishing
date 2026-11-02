<template>
  <div>
    <div class="toolbar">
      <el-radio-group v-model="platform" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="(label, key) in PLATFORMS" :key="key" :value="key">
          {{ label }}
        </el-radio-button>
      </el-radio-group>
      <el-dropdown @command="addAccount">
        <el-button type="primary">添加账号</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="wechat_mp">授权微信公众号</el-dropdown-item>
            <el-dropdown-item command="douyin">扫码登录抖音</el-dropdown-item>
            <el-dropdown-item command="channels">扫码登录视频号</el-dropdown-item>
            <el-dropdown-item command="kuaishou" disabled>授权快手（权限申请中）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-table :data="accounts" v-loading="loading" empty-text="还没有账号，点击右上角添加">
      <el-table-column label="平台" width="120">
        <template #default="{ row }">{{ PLATFORMS[row.platform] }}</template>
      </el-table-column>
      <el-table-column prop="display_name" label="名称" />
      <el-table-column label="状态" width="140">
        <template #default="{ row }">
          <el-tag :type="STATUS[row.status].type">{{ STATUS[row.status].label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="添加时间" width="200">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="rename(row)">改名</el-button>
          <el-button link type="danger" @click="remove(row)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'

const PLATFORMS = {
  wechat_mp: '微信公众号',
  douyin: '抖音',
  channels: '视频号',
  kuaishou: '快手',
}
const STATUS = {
  active: { label: '正常', type: 'success' },
  expired: { label: '需重新授权', type: 'warning' },
  error: { label: '异常', type: 'danger' },
}

const accounts = ref([])
const platform = ref('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params = platform.value ? { platform: platform.value } : {}
    accounts.value = (await api.get('/accounts', { params })).data
  } finally {
    loading.value = false
  }
}

function addAccount(command) {
  // 授权 / 扫码流程在后续阶段实现
  ElMessage.info(`${PLATFORMS[command]}接入开发中`)
}

async function rename(row) {
  const { value } = await ElMessageBox.prompt('新的名称', '改名', { inputValue: row.display_name })
  await api.patch(`/accounts/${row.id}`, { display_name: value })
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定移除「${row.display_name}」？移除后需要重新授权才能使用。`, '移除账号', {
    type: 'warning',
  })
  await api.delete(`/accounts/${row.id}`)
  await load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}
</style>
