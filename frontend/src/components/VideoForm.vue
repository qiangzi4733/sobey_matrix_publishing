<template>
  <div>
    <el-alert v-if="reviewNote" :title="`退回原因：${reviewNote}`" type="warning" :closable="false" class="note" />
    <el-form :model="form" label-width="90px" @submit.prevent="submit">
      <el-form-item label="视频" required>
        <video v-if="videoUrl && !file" :src="videoUrl" controls class="video" />
        <el-upload :auto-upload="false" :limit="1" accept=".mp4,.mov" :on-change="pickFile" :on-remove="() => (file = null)">
          <el-button>{{ videoUrl ? '更换视频' : '选择视频文件' }}</el-button>
          <template #tip><div class="tip">支持 mp4 / mov{{ videoUrl ? '，不选则沿用原视频' : '' }}</div></template>
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
        <el-radio-group v-model="form.accountId">
          <el-radio v-for="a in accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
            {{ PLATFORMS[a.platform] }} · {{ a.display_name }}
            <span v-if="a.status !== 'active'" class="tip">（需重新登录）</span>
          </el-radio>
        </el-radio-group>
        <div v-if="!accounts.length" class="tip">还没有可发布的账号，请先到「账号管理」添加</div>
      </el-form-item>
      <el-form-item label="定时发布">
        <div>
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则立即发布" :disabled-date="(d) => d < startOfToday" />
          <div class="tip">视频号需在 10 分钟后、30 天内；抖音需在 2 小时后、14 天内。审核通过点「发布」时还可以修改</div>
        </div>
      </el-form-item>
      <el-form-item v-if="submitting && file" label="上传进度">
        <el-progress :percentage="progress" style="width: 100%" />
      </el-form-item>
      <el-form-item>
        <el-button :disabled="submitting" @click="$emit('cancel')">取消</el-button>
        <el-button type="primary" native-type="submit" :loading="submitting">提交审核</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'
import { PLATFORMS, VIDEO_PLATFORMS } from '../platforms'

// 不传 postId 是新建，传了是修改；copyFrom 是复制已有内容新建，账号和定时要重新选
const props = defineProps({ postId: { type: Number, default: null }, copyFrom: { type: Number, default: null } })
const emit = defineEmits(['saved', 'cancel'])
const { postId, copyFrom } = props
const reviewNote = ref('')
const videoUrl = ref('')
const accounts = ref([])
const file = ref(null)
const submitting = ref(false)
const progress = ref(0)
const form = reactive({ title: '', description: '', tags: [], accountId: null, scheduledAt: null })
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))
let saved = ''

const snapshot = () => JSON.stringify(form)

// 外层关闭弹窗前用：上传中不能关，有改动要确认
defineExpose({
  busy: () => submitting.value,
  dirty: () => Boolean(file.value) || snapshot() !== saved,
})

function pickFile(uploadFile) {
  file.value = uploadFile.raw
}

async function submit() {
  if (!file.value && !videoUrl.value) return ElMessage.warning('请选择视频')
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (!form.accountId) return ElMessage.warning('请选择发布账号')

  const body = new FormData()
  if (file.value) body.append('video', file.value)
  else if (copyFrom) body.append('copy_from', copyFrom)
  body.append('title', form.title)
  body.append('description', form.description)
  body.append('tags', form.tags.join(','))
  body.append('account_id', form.accountId)
  if (form.scheduledAt) body.append('scheduled_at', form.scheduledAt.toISOString())

  submitting.value = true
  progress.value = 0
  const config = {
    onUploadProgress: (e) => {
      if (e.total) progress.value = Math.min(99, Math.round((e.loaded / e.total) * 100))
    },
  }
  try {
    if (postId) await api.put(`/posts/${postId}`, body, config)
    else await api.post('/posts', body, config)
    ElMessage.success('已提交审核')
    emit('saved')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const all = (await api.get('/accounts')).data
  accounts.value = all.filter((a) => VIDEO_PLATFORMS.includes(a.platform))
  if (postId || copyFrom) {
    const post = (await api.get(`/posts/${postId || copyFrom}`)).data
    Object.assign(form, { title: post.title, description: post.description, tags: post.tags })
    videoUrl.value = post.video_url
    if (postId) {
      form.accountId = post.account?.id ?? null
      form.scheduledAt = post.scheduled_at ? new Date(post.scheduled_at) : null
      reviewNote.value = post.review_note || ''
    }
  }
  saved = snapshot()
})
</script>

<style scoped>
.note {
  margin-bottom: 16px;
}
.video {
  display: block;
  width: 320px;
  max-height: 240px;
  margin-bottom: 8px;
  background: #000;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
