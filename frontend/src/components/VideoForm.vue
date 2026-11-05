<template>
  <el-form :model="form" label-position="top" @submit.prevent="submit(false)">
    <FormShell :title="heading" @close="emit('cancel')">
      <template #subtitle>
        <span>{{ categoryPath(categories, category) || '未分类' }}</span>
        <el-icon><Right /></el-icon>
        <template v-if="currentAccount">
          <PlatformIcon :platform="currentAccount.platform" />
          <span>{{ PLATFORMS[currentAccount.platform] }} {{ currentAccount.display_name }}</span>
          <span v-if="currentAccount.status !== 'active'" class="warn">登录已失效，可以先提交审核，发布前要到「账号管理」重新登录</span>
        </template>
        <span v-else-if="lockedId" class="warn">分类绑定的账号不能发布视频，请到「分类管理」修改</span>
        <span v-else>选择发布账号</span>
      </template>
      <template #actions>
        <el-progress v-if="submitting && file" :percentage="progress" class="progress" />
        <el-button v-if="canDraft" :disabled="submitting" @click="submit(true)">存草稿</el-button>
        <el-button type="primary" native-type="submit" :loading="submitting">提交审核</el-button>
      </template>

      <el-alert v-if="reviewNote" :title="`退回原因：${reviewNote}`" type="warning" :closable="false" show-icon />

      <!-- 分类没绑定账号的老内容，客户自己选账号 -->
      <section v-if="!lockedId" class="section">
        <h2 class="section-title">发布账号</h2>
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
      </section>

      <section class="section">
        <h2 class="section-title">视频与封面</h2>
        <div class="file">
          <span class="file-thumb" aria-hidden="true"><el-icon :size="18"><VideoPlay /></el-icon></span>
          <span class="file-text">
            <span class="file-name">{{ file ? file.name : videoUrl ? '沿用原视频' : '还没有选择视频' }}</span>
            <span class="tip">{{ videoSummary || '支持 mp4 / mov' }}</span>
          </span>
          <el-button @click="fileInput.click()">{{ file || videoUrl ? '更换' : '选择视频' }}</el-button>
          <input ref="fileInput" type="file" accept=".mp4,.mov" hidden @change="pickFile" />
        </div>
        <div v-if="metaError" class="warn">浏览器读不出这个视频，可能是 H.265 等编码，平台可能无法处理，建议转成 H.264 的 mp4</div>
        <!-- 播放选中的视频，确认没选错文件；读宽高、时长也靠它。#t=0.1 让浏览器解出第一帧，否则是黑屏 -->
        <video
          v-else-if="previewVideo"
          :key="previewVideo"
          :src="`${previewVideo}#t=0.1`"
          class="player"
          controls
          preload="metadata"
          @loadedmetadata="readMeta"
          @error="metaError = Boolean(file)"
        />
        <div class="covers">
          <div class="cover-field">
            <span class="field-label">竖封面 3:4 <span class="tip">可不传，由平台自动生成</span></span>
            <CoverUpload v-model="form.coverUrl" />
            <span class="tip">jpg / png，5MB 以内</span>
          </div>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">文案</h2>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" :maxlength="titleMax" show-word-limit :placeholder="rules?.titleTip" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="4" maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item label="话题">
          <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="输入后回车，不用加 #" style="width: 100%" />
        </el-form-item>
      </section>

      <section v-if="optionsForm" class="section">
        <h2 class="section-title">
          <PlatformIcon :platform="platform" />{{ PLATFORMS[platform] }}专属
        </h2>
        <component :is="optionsForm" v-model="form.options" />
      </section>

    </FormShell>
  </el-form>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Right, VideoPlay } from '@element-plus/icons-vue'

import api from '../api'
import { categoryPath } from '../categories'
import { PLATFORMS, VIDEO_PLATFORMS, VIDEO_RULES } from '../platforms'
import CoverUpload from './CoverUpload.vue'
import FormShell from './FormShell.vue'
import PlatformIcon from './PlatformIcon.vue'
import DouyinOptions from './video-options/DouyinOptions.vue'

// 各平台的专属配置表单，没有专属配置的平台不用登记
const OPTION_FORMS = { douyin: DouyinOptions }

// 不传 postId 是新建，传了是修改；copyFrom 是复制已有内容新建。立即还是定时在审核通过后点「发布」时选
const props = defineProps({
  postId: { type: Number, default: null },
  copyFrom: { type: Number, default: null },
  categories: { type: Array, required: true },
  // 新建、复制时放进的分类（绑定了账号）；修改时分类不能改，用内容自己的
  categoryId: { type: Number, default: null },
})
const emit = defineEmits(['saved', 'cancel'])
const { postId, copyFrom } = props
const reviewNote = ref('')
// 新建、复制和草稿可以存草稿；已提交的内容存草稿等于撤回审核，暂不支持
const canDraft = ref(!postId)
const videoUrl = ref('')
const accounts = ref([])
const file = ref(null)
const fileInput = ref(null)
// 本地选的视频：预览地址和读到的分辨率、时长；读不出来多半是浏览器不支持的编码
const fileUrl = ref('')
const meta = ref(null)
const metaError = ref(false)
const submitting = ref(false)
const progress = ref(0)
const category = ref(props.categoryId)
// 分类决定的账号，客户不能改；为空是分类没绑定账号的老内容，客户自己选（规则和后端 posts._edit_account_id 一致）
const lockedId = ref(null)
// optionsPlatform：options 是按哪个平台填的，换到其他平台的账号时要清空
const form = reactive({
  title: '',
  description: '',
  tags: [],
  coverUrl: '',
  accountId: null,
  options: {},
  optionsPlatform: null,
})
let saved = ''

const heading = computed(() => (postId ? '修改视频' : copyFrom ? '复制视频' : '发布视频'))
const previewVideo = computed(() => fileUrl.value || videoUrl.value)

const accountGroups = computed(() =>
  VIDEO_PLATFORMS.map((platform) => ({ platform, accounts: accounts.value.filter((a) => a.platform === platform) })).filter(
    (g) => g.accounts.length,
  ),
)
const lockedAccount = computed(() => accounts.value.find((a) => a.id === lockedId.value))
const currentAccount = computed(() => accounts.value.find((a) => a.id === form.accountId) ?? null)
const platformOf = (id) => accounts.value.find((a) => a.id === id)?.platform ?? null
const platform = computed(() => platformOf(form.accountId))
const rules = computed(() => VIDEO_RULES[platform.value])
const titleMax = computed(() => rules.value?.titleMax ?? 200)
const optionsForm = computed(() => OPTION_FORMS[platform.value])

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

const formatDuration = (seconds) => {
  const s = Math.round(seconds)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

const videoSummary = computed(() => {
  if (!file.value) return videoUrl.value ? '不更换就用原来的视频' : ''
  const parts = []
  if (meta.value) {
    const { width, height, duration } = meta.value
    parts.push(`${width} × ${height} ${height > width ? '竖屏' : height === width ? '方形' : '横屏'}`, formatDuration(duration))
  }
  parts.push(`${(file.value.size / 1024 / 1024).toFixed(1)} MB`)
  return parts.join(' · ')
})

const snapshot = () => JSON.stringify(form)

// 外层关闭弹窗前用：上传中不能关，有改动要确认
defineExpose({
  busy: () => submitting.value,
  dirty: () => Boolean(file.value) || snapshot() !== saved,
})

function pickFile(event) {
  const picked = event.target.files[0]
  event.target.value = ''
  if (!picked) return
  if (fileUrl.value) URL.revokeObjectURL(fileUrl.value)
  file.value = picked
  meta.value = null
  metaError.value = false
  fileUrl.value = URL.createObjectURL(picked)
}

function readMeta(event) {
  const v = event.target
  // 有的编码能读到时长但宽高为 0，也算读不出来
  if (!v.videoWidth) metaError.value = true
  else meta.value = { width: v.videoWidth, height: v.videoHeight, duration: v.duration }
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
  if (!postId) body.append('category_id', category.value)
  else if (!lockedId.value && form.accountId) body.append('account_id', form.accountId)
  if (draft) body.append('draft', 'true')
  body.append('cover_url', form.coverUrl)
  // 没填的项不传，后端按未设置处理
  body.append('options', JSON.stringify(Object.fromEntries(Object.entries(form.options).filter(([, v]) => v))))

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
  let post = null
  if (postId || copyFrom) {
    post = (await api.get(`/posts/${postId || copyFrom}`)).data
    // 复制时沿用封面；专属配置发到同平台时沿用。原账号已移除时不知道配置属于哪个平台，丢掉
    Object.assign(form, {
      title: post.title,
      description: post.description,
      tags: post.tags,
      coverUrl: post.cover_url,
      options: post.account ? { ...post.options } : {},
      optionsPlatform: post.account?.platform ?? null,
    })
    videoUrl.value = post.video_url
    if (postId) {
      category.value = post.category_id
      form.accountId = post.account?.id ?? null
      reviewNote.value = post.review_note || ''
      canDraft.value = post.review_status === 'draft'
    }
  }
  // 草稿跟着分类当前的绑定；提交过的沿用原账号，原账号被移除了才用分类的
  const bound = props.categories.find((c) => c.id === category.value)?.account?.id ?? null
  if (!bound) lockedId.value = null
  else if (postId && post.review_status !== 'draft' && post.account) lockedId.value = post.account.id
  else lockedId.value = bound
  if (lockedId.value) {
    form.accountId = lockedId.value
    // 发到别的平台，原来的专属配置用不上
    if (form.optionsPlatform !== platformOf(lockedId.value)) {
      form.options = {}
      form.optionsPlatform = platformOf(lockedId.value)
    }
  }
  saved = snapshot()
})
onBeforeUnmount(() => {
  if (fileUrl.value) URL.revokeObjectURL(fileUrl.value)
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
.progress {
  width: 160px;
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
.file {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: 10px;
  background: var(--mp-page-bg);
}
.file-thumb {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 58px;
  border-radius: 6px;
  background: #3a4256;
  color: #fff;
}
.file-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.file-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.covers {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}
.cover-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.field-label {
  font-weight: 500;
}
.player {
  align-self: flex-start;
  max-width: 100%;
  max-height: 360px;
  border-radius: 8px;
  background: #000;
}
</style>
