<template>
  <el-form :model="form" label-position="top" @submit.prevent="submit(false)">
    <FormShell :title="heading" @close="emit('cancel')">
      <template #subtitle>
        <span>{{ categoryPath(categories, category) || '未分类' }}</span>
        <el-icon><Right /></el-icon>
        <template v-if="currentAccount">
          <PlatformIcon platform="wechat_mp" />
          <span>公众号 {{ currentAccount.display_name }}</span>
          <span v-if="currentAccount.status !== 'active'" class="warn">授权已失效</span>
        </template>
        <span v-else-if="lockedId" class="warn">分类绑定的账号不是公众号，不能发布图文，请到「分类与绑定」修改</span>
        <span v-else>选择公众号</span>
      </template>
      <template #actions>
        <el-button v-if="canDraft" :disabled="submitting" @click="submit(true)">存草稿</el-button>
        <el-button type="primary" native-type="submit" :loading="submitting">提交审核</el-button>
      </template>

      <el-alert v-if="reviewNote" :title="`退回原因：${reviewNote}`" type="warning" :closable="false" show-icon />

      <!-- 按公众号文章的样子编辑：标题、作者在正文上方 -->
      <article class="paper">
        <div class="toolbar" role="toolbar" aria-label="正文格式">
          <el-button text @mousedown.prevent @click="format('h2')">小标题</el-button>
          <el-button text @mousedown.prevent @click="format('p')">正文</el-button>
          <el-button text aria-label="加粗" @mousedown.prevent @click="exec('bold')"><b>B</b></el-button>
          <span class="toolbar-sep" aria-hidden="true" />
          <el-button text :icon="Picture" @mousedown.prevent @click="imageInput.click()">插入图片</el-button>
          <input ref="imageInput" type="file" accept=".jpg,.jpeg,.png" hidden @change="insertImage" />
        </div>
        <div class="paper-body">
          <div class="title-row">
            <input v-model="form.title" class="title-input" maxlength="64" placeholder="请输入标题" aria-label="标题" />
            <span class="tip">{{ form.title.length }} / 64</span>
          </div>
          <label class="author">
            作者
            <input v-model="form.author" maxlength="16" placeholder="可不填" />
          </label>
          <!-- 粘贴只保留纯文本：外部图片和样式发到公众号会被过滤 -->
          <div ref="editor" class="editor-body" contenteditable="true" aria-label="正文" data-placeholder="从这里开始写正文" @paste="pastePlain" @input="syncEmpty"></div>
        </div>
      </article>

      <template #aside>
        <section class="section">
          <h2 class="section-title">封面和摘要</h2>
          <el-upload :show-file-list="false" accept=".jpg,.jpeg,.png" :http-request="uploadCover">
            <div class="card-preview">
              <div class="card-cover">
                <img v-if="form.coverUrl" :src="form.coverUrl" alt="封面" />
                <span v-else class="tip">+ 上传封面（必填）</span>
              </div>
              <div class="card-text">
                <span class="card-title">{{ form.title || '标题' }}</span>
                <span class="tip">{{ form.coverUrl ? '点击更换封面 · ' : '' }}jpg / png，1MB 以内，建议 900×383</span>
              </div>
            </div>
          </el-upload>
          <el-form-item label="摘要">
            <el-input v-model="form.digest" type="textarea" :rows="2" maxlength="120" show-word-limit placeholder="不填则微信自动截取正文前 54 字" />
          </el-form-item>
        </section>

        <!-- 分类没绑定账号的老内容，客户自己选公众号 -->
        <section v-if="!lockedId" class="section">
          <h2 class="section-title">公众号</h2>
          <el-radio-group v-model="form.accountId">
            <el-radio v-for="a in accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
              {{ a.display_name }}
              <span v-if="a.status !== 'active'" class="tip">（需重新授权）</span>
            </el-radio>
          </el-radio-group>
          <div v-if="!accounts.length" class="tip">还没有公众号，请先到「账号管理」授权</div>
        </section>

        <section class="section">
          <h2 class="section-title">发布方式</h2>
          <label class="choice" :class="{ active: !form.draftOnly }">
            <input v-model="form.draftOnly" type="radio" :value="false" />
            <span class="choice-text">
              <span>直接发表</span>
              <span class="tip">发表后有链接即可访问，不推送给粉丝</span>
            </span>
          </label>
          <label class="choice" :class="{ active: form.draftOnly }">
            <input v-model="form.draftOnly" type="radio" :value="true" />
            <span class="choice-text">
              <span>只存到草稿箱</span>
              <span class="tip">到公众号后台再手动群发或发表</span>
            </span>
          </label>
          <el-form-item label="定时">
            <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则审核后点「发布」时提交" :disabled-date="(d) => d < startOfToday" style="width: 100%" />
          </el-form-item>
          <span class="tip">到点由本平台提交给公众号。审核通过点「发布」时还可以修改。</span>
        </section>

        <section class="section">
          <h2 class="section-title">更多</h2>
          <el-form-item label="原文链接">
            <el-input v-model="form.sourceUrl" placeholder="可选，https:// 开头" />
          </el-form-item>
          <div class="switch-row">
            <span>开启留言</span>
            <el-switch v-model="form.openComment" aria-label="开启留言" />
          </div>
        </section>
      </template>
    </FormShell>
  </el-form>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Picture, Right } from '@element-plus/icons-vue'

import api from '../api'
import { categoryPath } from '../categories'
import { cleanHtml } from '../html'
import { ARTICLE_PLATFORMS } from '../platforms'
import FormShell from './FormShell.vue'
import PlatformIcon from './PlatformIcon.vue'

// 不传 postId 是新建，传了是修改；copyFrom 是复制已有内容新建，定时要重新选。
// 正文图片和封面不会随内容删除，复制的内容直接引用同一批图片
const props = defineProps({
  postId: { type: Number, default: null },
  copyFrom: { type: Number, default: null },
  categories: { type: Array, required: true },
  // 新建、复制时放进的分类（绑定了公众号）；修改时分类不能改，用内容自己的
  categoryId: { type: Number, default: null },
})
const emit = defineEmits(['saved', 'cancel'])
const { postId, copyFrom } = props
const reviewNote = ref('')
// 新建、复制和草稿可以存草稿；已提交的内容存草稿等于撤回审核，暂不支持
const canDraft = ref(!postId)
const accounts = ref([])
const category = ref(props.categoryId)
// 分类决定的公众号，客户不能改；为空是分类没绑定账号的老内容，客户自己选（规则和后端 posts._edit_account_id 一致）
const lockedId = ref(null)
const currentAccount = computed(() => accounts.value.find((a) => a.id === form.accountId) ?? null)
const heading = computed(() => (postId ? '修改图文' : copyFrom ? '复制图文' : '发布图文'))
const editor = ref(null)
const imageInput = ref(null)
const submitting = ref(false)
const startOfToday = new Date(new Date().setHours(0, 0, 0, 0))
const form = reactive({
  title: '',
  author: '',
  digest: '',
  coverUrl: '',
  sourceUrl: '',
  openComment: false,
  draftOnly: true,
  accountId: null,
  scheduledAt: null,
})
let saved = ''

// 正文在 contenteditable 里，不在 form 中，一起比较
const snapshot = () => JSON.stringify(form) + (editor.value?.innerHTML ?? '')

// 外层关闭抽屉前用：提交中不能关，有改动要确认
defineExpose({
  busy: () => submitting.value,
  dirty: () => snapshot() !== saved,
})

async function upload(file) {
  const body = new FormData()
  body.append('image', file)
  return (await api.post('/article-images', body)).data.url
}

async function uploadCover({ file }) {
  form.coverUrl = await upload(file)
}

function exec(command, value) {
  editor.value.focus()
  document.execCommand(command, false, value)
}

function format(tag) {
  exec('formatBlock', `<${tag}>`)
}

async function insertImage(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  const url = await upload(file)
  exec('insertHTML', `<p><img src="${url}" style="max-width: 100%"></p>`)
}

function pastePlain(event) {
  event.preventDefault()
  document.execCommand('insertText', false, event.clipboardData.getData('text/plain'))
}

// 正文为空时显示占位提示（contenteditable 删空后常残留一个 <br>，:empty 判断不了）
function syncEmpty() {
  const el = editor.value
  el.classList.toggle('empty', !el.innerText.trim() && !el.querySelector('img'))
}

// 存草稿只要求标题，其余提交审核时再校验
async function submit(draft) {
  const content = editor.value.innerHTML.trim()
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (!draft) {
    if (!form.coverUrl) return ElMessage.warning('请上传封面')
    if (!editor.value.innerText.trim() && !content.includes('<img')) return ElMessage.warning('请填写正文')
    if (!form.accountId) return ElMessage.warning('请选择公众号')
  }
  if (!draft && !form.draftOnly) {
    await ElMessageBox.confirm('审核通过并发布后文章对外可见，确定选择直接发表？', '直接发表', { type: 'warning' })
  }

  submitting.value = true
  try {
    const body = {
      title: form.title,
      author: form.author,
      digest: form.digest,
      content,
      cover_url: form.coverUrl,
      source_url: form.sourceUrl,
      open_comment: form.openComment,
      draft_only: form.draftOnly,
      account_id: lockedId.value ? null : form.accountId,
      category_id: postId ? null : category.value,
      scheduled_at: form.scheduledAt ? form.scheduledAt.toISOString() : null,
      draft,
    }
    if (postId) await api.put(`/articles/${postId}`, body)
    else await api.post('/articles', body)
    ElMessage.success(draft ? '已存为草稿' : '已提交审核')
    emit('saved', draft)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const all = (await api.get('/accounts')).data
  accounts.value = all.filter((a) => ARTICLE_PLATFORMS.includes(a.platform))
  let post = null
  if (postId || copyFrom) {
    post = (await api.get(`/posts/${postId || copyFrom}`)).data
    Object.assign(form, {
      title: post.title,
      author: post.author,
      digest: post.description,
      coverUrl: post.cover_url,
      sourceUrl: post.source_url,
      openComment: post.open_comment,
      draftOnly: post.draft_only,
    })
    editor.value.innerHTML = cleanHtml(post.content)
    if (postId) {
      category.value = post.category_id
      form.accountId = post.account?.id ?? null
      form.scheduledAt = post.scheduled_at ? new Date(post.scheduled_at) : null
      reviewNote.value = post.review_note || ''
      canDraft.value = post.review_status === 'draft'
    }
  }
  // 草稿跟着分类当前的绑定；提交过的沿用原账号，原账号被移除了才用分类的
  const bound = props.categories.find((c) => c.id === category.value)?.account?.id ?? null
  if (!bound) lockedId.value = null
  else if (postId && post.review_status !== 'draft' && post.account) lockedId.value = post.account.id
  else lockedId.value = bound
  if (lockedId.value) form.accountId = lockedId.value
  syncEmpty()
  saved = snapshot()
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
.paper {
  background: #fff;
  border: 1px solid var(--mp-panel-border);
  border-radius: var(--mp-panel-radius);
}
.toolbar {
  position: sticky;
  top: 61px;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid var(--mp-panel-border);
  border-radius: var(--mp-panel-radius) var(--mp-panel-radius) 0 0;
}
.toolbar .el-button + .el-button {
  margin-left: 0;
}
.toolbar-sep {
  width: 1px;
  height: 20px;
  margin: 0 6px;
  background: var(--mp-panel-border);
}
.paper-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 32px 56px 48px;
}
.title-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title-row .tip {
  align-self: flex-end;
}
.title-input {
  border: 0;
  outline: 0;
  padding: 0;
  font: inherit;
  font-size: 26px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.title-input::placeholder,
.author input::placeholder {
  color: var(--el-text-color-placeholder);
}
.author {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
}
.author input {
  width: 180px;
  padding: 2px 0;
  border: 0;
  border-bottom: 1px dashed var(--el-border-color);
  outline: 0;
  font: inherit;
  color: var(--el-text-color-primary);
}
.editor-body {
  min-height: 420px;
  font-size: 16px;
  line-height: 1.85;
  color: #2a2e35;
  outline: none;
}
.editor-body.empty::before {
  content: attr(data-placeholder);
  color: var(--el-text-color-placeholder);
  pointer-events: none;
}
.editor-body :deep(img) {
  max-width: 100%;
}
.card-preview {
  display: flex;
  flex-direction: column;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--mp-panel-border);
  border-radius: 10px;
  text-align: left;
  cursor: pointer;
}
.card-cover {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 2.35;
  background: var(--mp-page-bg);
}
.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
}
.card-title {
  font-weight: 600;
  line-height: 1.5;
  word-break: break-word;
}
/* el-upload 的触发区默认是行内块，撑满卡片宽度 */
.section :deep(.el-upload) {
  display: block;
}
.choice {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  cursor: pointer;
}
.choice.active {
  border-color: var(--el-color-primary);
  background: #f5f8ff;
}
.choice input {
  margin-top: 3px;
  accent-color: var(--el-color-primary);
}
.choice-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
