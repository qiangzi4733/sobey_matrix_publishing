<template>
  <el-form :model="form" label-position="top" @submit.prevent="submit(false)">
    <FormShell :title="heading" @close="emit('cancel')">
      <template #subtitle>
        <span>{{ categoryPath(categories, category) || '未分类' }}</span>
        <el-icon><Right /></el-icon>
        <template v-if="currentAccount">
          <PlatformIcon :platform="currentAccount.platform" />
          <span>{{ PLATFORMS[currentAccount.platform] }} {{ currentAccount.display_name }}</span>
          <span v-if="currentAccount.status !== 'active'" class="warn">登录已失效</span>
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

      <section class="section">
        <h2 class="section-title">发布时间</h2>
        <div class="when" role="radiogroup" aria-label="发布时间">
          <label class="when-option" :class="{ active: !scheduleOn }">
            <input v-model="scheduleOn" type="radio" :value="false" />
            <span class="when-text">
              <span>审核通过后手动发布</span>
              <span class="tip">点「发布」时立即提交给平台</span>
            </span>
          </label>
          <label class="when-option" :class="{ active: scheduleOn }">
            <input v-model="scheduleOn" type="radio" :value="true" />
            <span class="when-text">
              <span>定时发布</span>
              <span class="tip">{{ scheduleTip }}（北京时间）</span>
            </span>
          </label>
        </div>
        <el-form-item v-if="scheduleOn" label="发布时间">
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="选择日期和时间" :disabled-date="(d) => d < startOfToday" />
        </el-form-item>
        <span class="tip">审核通过点「发布」时还可以修改。</span>
      </section>

      <section v-if="optionsForm" class="section">
        <h2 class="section-title">
          <PlatformIcon :platform="platform" />{{ PLATFORMS[platform] }}专属
        </h2>
        <component :is="optionsForm" v-model="form.options" />
      </section>

      <template #aside>
        <section class="section">
          <h2 class="section-title">{{ platform ? `${PLATFORMS[platform]}里大概长这样` : '预览' }}</h2>
          <div class="phone">
            <div class="screen">
              <img v-if="form.coverUrl" :src="form.coverUrl" class="screen-media" alt="" />
              <!-- #t=0.1 让浏览器解出第一帧当画面，否则只有黑屏 -->
              <video v-else-if="previewVideo" :src="`${previewVideo}#t=0.1`" class="screen-media" muted preload="metadata" />
              <div class="caption">
                <span class="caption-name">@{{ currentAccount?.display_name ?? '账号' }}</span>
                <span class="caption-text">{{ caption }}</span>
              </div>
            </div>
          </div>
          <span class="tip">只是示意，以平台实际显示为准</span>
        </section>
        <CheckList :items="checks" />
      </template>
    </FormShell>
    <!-- 读本地视频的分辨率和时长，用于提交前检查 -->
    <video v-if="fileUrl" :src="fileUrl" preload="metadata" hidden @loadedmetadata="readMeta" @error="metaError = true" />
  </el-form>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Right, VideoPlay } from '@element-plus/icons-vue'

import api from '../api'
import { categoryPath } from '../categories'
import { PLATFORMS, VIDEO_PLATFORMS, VIDEO_RULES, formatTime } from '../platforms'
import CheckList from './CheckList.vue'
import CoverUpload from './CoverUpload.vue'
import FormShell from './FormShell.vue'
import PlatformIcon from './PlatformIcon.vue'
import DouyinOptions from './video-options/DouyinOptions.vue'

// 各平台的专属配置表单，没有专属配置的平台不用登记
const OPTION_FORMS = { douyin: DouyinOptions }

// 不传 postId 是新建，传了是修改；copyFrom 是复制已有内容新建，定时要重新选
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
const scheduleOn = ref(false)
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
  scheduledAt: null,
  options: {},
  optionsPlatform: null,
})
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))
let saved = ''

const heading = computed(() => (postId ? '修改视频' : copyFrom ? '复制视频' : '发布视频'))
const previewVideo = computed(() => fileUrl.value || videoUrl.value)
const caption = computed(() =>
  [form.title || '标题', form.description, form.tags.map((t) => `#${t}`).join(' ')].filter(Boolean).join(' '),
)

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

// 关掉定时就清空时间，免得提交上去
watch(scheduleOn, (on) => {
  if (!on) form.scheduledAt = null
})

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

// 只检查能确定的事；视频大小、时长的平台上限还没核实，不在这里拦
const checks = computed(() => {
  const items = []
  if (!file.value && !videoUrl.value) items.push({ level: 'error', label: '还没有选择视频' })
  else if (metaError.value) items.push({ level: 'warn', label: '浏览器读不出这个视频', hint: '可能是 H.265 等编码，平台可能无法处理，建议转成 H.264 的 mp4' })
  else if (file.value && meta.value) items.push({ level: 'ok', label: '视频可以正常读取', hint: videoSummary.value })
  else items.push({ level: 'ok', label: file.value ? '视频已选择' : '沿用原视频' })

  const max = titleMax.value
  if (!form.title.trim()) items.push({ level: 'error', label: '还没有填写标题' })
  else if (form.title.length > max) items.push({ level: 'error', label: `标题 ${form.title.length} / ${max} 字`, hint: `${PLATFORMS[platform.value]}标题最多 ${max} 字` })
  else items.push({ level: 'ok', label: `标题 ${form.title.length} / ${max} 字` })

  if (!form.coverUrl) items.push({ level: 'warn', label: '没有上传竖封面', hint: '由平台用视频画面自动生成' })
  else items.push({ level: 'ok', label: '已上传竖封面' })

  if (scheduleOn.value) {
    const at = form.scheduledAt
    const r = rules.value
    if (!at) items.push({ level: 'warn', label: '还没有选择定时时间', hint: '不选就是审核通过后手动发布' })
    else if (r) {
      const minutes = (at - Date.now()) / 60000
      if (minutes < r.scheduleMin || minutes > r.scheduleDays * 1440) {
        items.push({ level: 'warn', label: `定时 ${formatTime(at)} 不在范围内`, hint: `${PLATFORMS[platform.value]}只能定在 ${r.schedule}，点「发布」时要改` })
      } else {
        items.push({ level: 'ok', label: `定时 ${formatTime(at)}`, hint: `在 ${r.schedule}；审核太久的话发布时可能要改` })
      }
    }
  }

  const a = currentAccount.value
  if (!a) items.push({ level: 'error', label: '还没有发布账号' })
  else if (a.status !== 'active') items.push({ level: 'warn', label: `${PLATFORMS[a.platform]} ${a.display_name} 登录已失效`, hint: '可以先提交审核，发布前要到「账号管理」重新登录' })
  else items.push({ level: 'ok', label: '账号登录正常', hint: `${PLATFORMS[a.platform]} ${a.display_name}` })
  return items
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
      form.scheduledAt = post.scheduled_at ? new Date(post.scheduled_at) : null
      scheduleOn.value = Boolean(form.scheduledAt)
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
.when {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.when-option {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  cursor: pointer;
}
.when-option.active {
  border-color: var(--el-color-primary);
  background: #f5f8ff;
}
.when-option input {
  margin-top: 3px;
  accent-color: var(--el-color-primary);
}
.when-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.phone {
  align-self: center;
  width: 220px;
  height: 400px;
  padding: 8px;
  box-sizing: border-box;
  border-radius: 22px;
  background: #11131a;
}
.screen {
  position: relative;
  height: 100%;
  overflow: hidden;
  border-radius: 16px;
  background: #46506a;
}
.screen-media {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 40px 12px 14px;
  color: #fff;
  font-size: 12px;
  line-height: 1.5;
  /* 底部压暗，白字在任何封面上都看得清 */
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.65));
}
.caption-name {
  font-size: 13px;
  font-weight: 600;
}
.caption-text {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
</style>
