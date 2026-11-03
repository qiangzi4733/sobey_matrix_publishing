<template>
  <div>
    <el-alert v-if="reviewNote" :title="`退回原因：${reviewNote}`" type="warning" :closable="false" class="note" />
    <el-form :model="form" label-width="90px" @submit.prevent="submit(false)">
      <!-- 先选账号：账号决定发到哪个平台，下面的字数限制、定时范围和专属配置都跟着平台变 -->
      <el-form-item label="发布账号" required>
        <div class="accounts">
          <div v-for="group in accountGroups" :key="group.platform" class="account-group">
            <span class="group-name"><PlatformIcon :platform="group.platform" /> {{ PLATFORMS[group.platform] }}</span>
            <el-radio-group v-model="form.accountId">
              <el-radio v-for="a in group.accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
                {{ a.display_name }}
                <span v-if="a.status !== 'active'" class="tip">（需重新登录）</span>
              </el-radio>
            </el-radio-group>
          </div>
          <div v-if="!accounts.length" class="tip">还没有可发布的账号，请先到「账号管理」添加</div>
        </div>
      </el-form-item>
      <el-form-item label="视频" required>
        <video v-if="videoUrl && !file" :src="videoUrl" controls class="video" />
        <el-upload :auto-upload="false" :limit="1" accept=".mp4,.mov" :on-change="pickFile" :on-remove="() => (file = null)">
          <el-button>{{ videoUrl ? '更换视频' : '选择视频文件' }}</el-button>
          <template #tip><div class="tip">支持 mp4 / mov{{ videoUrl ? '，不选则沿用原视频' : '' }}</div></template>
        </el-upload>
      </el-form-item>
      <el-form-item label="封面">
        <div>
          <CoverUpload v-model="form.coverUrl" />
          <div class="tip">3:4 竖版，jpg / png，5MB 以内；不传由平台自动生成</div>
        </div>
      </el-form-item>
      <el-form-item label="标题" required>
        <el-input v-model="form.title" :maxlength="titleMax" show-word-limit :placeholder="rules?.titleTip" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="4" maxlength="1000" show-word-limit />
      </el-form-item>
      <el-form-item label="话题">
        <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="输入后回车，不用加 #" style="width: 100%" />
      </el-form-item>
      <el-form-item label="分类">
        <CategorySelect v-model="form.categoryId" :categories="categories" style="width: 320px" />
      </el-form-item>
      <el-form-item label="定时发布">
        <div>
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则立即发布" :disabled-date="(d) => d < startOfToday" />
          <div class="tip">{{ scheduleTip }}。审核通过点「发布」时还可以修改</div>
        </div>
      </el-form-item>
      <template v-if="optionsForm">
        <el-divider content-position="left">{{ PLATFORMS[platform] }}专属配置</el-divider>
        <component :is="optionsForm" v-model="form.options" />
      </template>
      <el-form-item v-if="submitting && file" label="上传进度">
        <el-progress :percentage="progress" style="width: 100%" />
      </el-form-item>
      <el-form-item>
        <el-button :disabled="submitting" @click="$emit('cancel')">取消</el-button>
        <el-button v-if="canDraft" :disabled="submitting" @click="submit(true)">存草稿</el-button>
        <el-button type="primary" native-type="submit" :loading="submitting">提交审核</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { PLATFORMS, VIDEO_PLATFORMS, VIDEO_RULES } from '../platforms'
import CategorySelect from './CategorySelect.vue'
import CoverUpload from './CoverUpload.vue'
import PlatformIcon from './PlatformIcon.vue'
import DouyinOptions from './video-options/DouyinOptions.vue'

// 各平台的专属配置表单，没有专属配置的平台不用登记
const OPTION_FORMS = { douyin: DouyinOptions }

// 不传 postId 是新建，传了是修改；copyFrom 是复制已有内容新建，账号和定时要重新选
const props = defineProps({
  postId: { type: Number, default: null },
  copyFrom: { type: Number, default: null },
  categories: { type: Array, required: true },
  // 新建时默认放到内容管理里当前选中的分类
  defaultCategory: { type: Number, default: null },
})
const emit = defineEmits(['saved', 'cancel'])
const { postId, copyFrom } = props
const reviewNote = ref('')
// 新建、复制和草稿可以存草稿；已提交的内容存草稿等于撤回审核，暂不支持
const canDraft = ref(!postId)
const videoUrl = ref('')
const accounts = ref([])
const file = ref(null)
const submitting = ref(false)
const progress = ref(0)
// optionsPlatform：options 是按哪个平台填的，换到其他平台的账号时要清空
const form = reactive({
  title: '',
  description: '',
  tags: [],
  coverUrl: '',
  categoryId: props.defaultCategory,
  accountId: null,
  scheduledAt: null,
  options: {},
  optionsPlatform: null,
})
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))
let saved = ''

const accountGroups = computed(() =>
  VIDEO_PLATFORMS.map((platform) => ({ platform, accounts: accounts.value.filter((a) => a.platform === platform) })).filter(
    (g) => g.accounts.length,
  ),
)
const platformOf = (id) => accounts.value.find((a) => a.id === id)?.platform ?? null
const platform = computed(() => platformOf(form.accountId))
const rules = computed(() => VIDEO_RULES[platform.value])
const titleMax = computed(() => rules.value?.titleMax ?? 200)
const optionsForm = computed(() => OPTION_FORMS[platform.value])
const scheduleTip = computed(() =>
  rules.value
    ? `${PLATFORMS[platform.value]}需在 ${rules.value.schedule}`
    : VIDEO_PLATFORMS.map((p) => `${PLATFORMS[p]}需在 ${VIDEO_RULES[p].schedule}`).join('；'),
)

watch(
  () => form.accountId,
  async (id, oldId) => {
    const next = platformOf(id)
    if (!next || next === form.optionsPlatform) return
    if (form.optionsPlatform && Object.values(form.options).some(Boolean)) {
      try {
        await ElMessageBox.confirm(
          `换成${PLATFORMS[next]}的账号后，已填的${PLATFORMS[form.optionsPlatform]}专属配置会清空`,
          '切换发布平台',
          { type: 'warning', confirmButtonText: '切换', cancelButtonText: '不切换' },
        )
      } catch {
        form.accountId = oldId
        return
      }
    }
    form.options = {}
    form.optionsPlatform = next
  },
)

const snapshot = () => JSON.stringify(form)

// 外层关闭弹窗前用：上传中不能关，有改动要确认
defineExpose({
  busy: () => submitting.value,
  dirty: () => Boolean(file.value) || snapshot() !== saved,
})

function pickFile(uploadFile) {
  file.value = uploadFile.raw
}

// 存草稿只要求标题，其余提交审核时再校验
async function submit(draft) {
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (form.accountId && form.title.length > titleMax.value) return ElMessage.warning(`${PLATFORMS[platform.value]}标题最多 ${titleMax.value} 字`)
  if (!draft) {
    if (!form.accountId) return ElMessage.warning('请选择发布账号')
    if (!file.value && !videoUrl.value) return ElMessage.warning('请选择视频')
  }

  const body = new FormData()
  if (file.value) body.append('video', file.value)
  else if (copyFrom && videoUrl.value) body.append('copy_from', copyFrom)
  body.append('title', form.title)
  body.append('description', form.description)
  body.append('tags', form.tags.join(','))
  if (form.accountId) body.append('account_id', form.accountId)
  if (draft) body.append('draft', 'true')
  body.append('cover_url', form.coverUrl)
  // 没填的项不传，后端按未设置处理
  body.append('options', JSON.stringify(Object.fromEntries(Object.entries(form.options).filter(([, v]) => v))))
  if (form.categoryId) body.append('category_id', form.categoryId)
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
    ElMessage.success(draft ? '已存为草稿' : '已提交审核')
    emit('saved', draft)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const all = (await api.get('/accounts')).data
  accounts.value = all.filter((a) => VIDEO_PLATFORMS.includes(a.platform))
  if (postId || copyFrom) {
    const post = (await api.get(`/posts/${postId || copyFrom}`)).data
    // 复制时沿用原分类、封面；专属配置在选了同平台的账号时沿用。原账号已移除时不知道配置属于哪个平台，丢掉
    Object.assign(form, {
      title: post.title,
      description: post.description,
      tags: post.tags,
      coverUrl: post.cover_url,
      categoryId: post.category_id,
      options: post.account ? { ...post.options } : {},
      optionsPlatform: post.account?.platform ?? null,
    })
    videoUrl.value = post.video_url
    if (postId) {
      form.accountId = post.account?.id ?? null
      form.scheduledAt = post.scheduled_at ? new Date(post.scheduled_at) : null
      reviewNote.value = post.review_note || ''
      canDraft.value = post.review_status === 'draft'
    }
  }
  saved = snapshot()
})
</script>

<style scoped>
.note {
  margin-bottom: 16px;
}
.accounts {
  width: 100%;
}
.account-group {
  display: flex;
  align-items: center;
  gap: 16px;
}
.group-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 80px;
  flex: none;
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
