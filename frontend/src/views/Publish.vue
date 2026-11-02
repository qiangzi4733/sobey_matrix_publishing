<template>
  <el-card header="发布视频" class="card">
    <el-form :model="form" label-width="90px" @submit.prevent="submit">
      <el-form-item label="视频" required>
        <el-upload :auto-upload="false" :limit="1" accept=".mp4,.mov" :on-change="pickFile" :on-remove="() => (file = null)">
          <el-button>选择视频文件</el-button>
          <template #tip><div class="tip">支持 mp4 / mov</div></template>
        </el-upload>
      </el-form-item>
      <el-form-item label="标题" required>
        <el-input v-model="form.title" maxlength="200" show-word-limit placeholder="视频号短标题会自动截取为 7~15 字" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="4" maxlength="1000" show-word-limit />
      </el-form-item>
      <el-form-item label="话题">
        <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="输入后回车，不用加 #" style="width: 100%" />
      </el-form-item>
      <el-form-item label="发布账号" required>
        <el-checkbox-group v-model="form.accountIds">
          <el-checkbox v-for="a in accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
            {{ PLATFORMS[a.platform] }} · {{ a.display_name }}
            <span v-if="a.status !== 'active'" class="tip">（需重新登录）</span>
          </el-checkbox>
        </el-checkbox-group>
        <div v-if="!accounts.length" class="tip">还没有可发布的账号，请先到「账号管理」添加</div>
      </el-form-item>
      <el-form-item label="定时发布">
        <div>
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则立即发布" :disabled-date="(d) => d < startOfToday" />
          <div class="tip">视频号：需在 10 分钟后、30 天内，提交后由视频号到点自动发布</div>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="submitting">提交发布</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import api from '../api'
import { PLATFORMS, PUBLISHABLE_PLATFORMS } from '../platforms'

const router = useRouter()
const accounts = ref([])
const file = ref(null)
const submitting = ref(false)
const form = reactive({ title: '', description: '', tags: [], accountIds: [], scheduledAt: null })
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))

function pickFile(uploadFile) {
  file.value = uploadFile.raw
}

async function submit() {
  if (!file.value) return ElMessage.warning('请选择视频')
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (!form.accountIds.length) return ElMessage.warning('请选择发布账号')

  const body = new FormData()
  body.append('video', file.value)
  body.append('title', form.title)
  body.append('description', form.description)
  body.append('tags', form.tags.join(','))
  body.append('account_ids', form.accountIds.join(','))
  if (form.scheduledAt) body.append('scheduled_at', form.scheduledAt.toISOString())

  submitting.value = true
  try {
    await api.post('/posts', body)
    ElMessage.success('已提交，正在发布')
    router.push({ name: 'tasks' })
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const all = (await api.get('/accounts')).data
  accounts.value = all.filter((a) => PUBLISHABLE_PLATFORMS.includes(a.platform))
})
</script>

<style scoped>
.card {
  max-width: 760px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
