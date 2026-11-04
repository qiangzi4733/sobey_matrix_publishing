<template>
  <div>
    <el-alert v-if="reviewNote" :title="`退回原因：${reviewNote}`" type="warning" :closable="false" class="note" />
    <el-form :model="form" label-width="90px" @submit.prevent="submit(false)">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" maxlength="64" show-word-limit />
      </el-form-item>
      <el-form-item label="作者">
        <el-input v-model="form.author" maxlength="16" show-word-limit style="width: 240px" />
      </el-form-item>
      <el-form-item label="封面" required>
        <div>
          <el-upload :show-file-list="false" accept=".jpg,.jpeg,.png" :http-request="uploadCover">
            <img v-if="form.coverUrl" :src="form.coverUrl" class="cover" alt="封面" />
            <el-button v-else>上传封面</el-button>
          </el-upload>
          <div class="tip">jpg / png，1MB 以内，建议 900×383</div>
        </div>
      </el-form-item>
      <el-form-item label="摘要">
        <el-input v-model="form.digest" type="textarea" :rows="2" maxlength="120" show-word-limit placeholder="不填则微信自动截取正文前 54 字" />
      </el-form-item>
      <el-form-item label="正文" required>
        <div class="editor">
          <div class="editor-toolbar">
            <el-button size="small" @mousedown.prevent @click="format('h2')">标题</el-button>
            <el-button size="small" @mousedown.prevent @click="format('p')">正文</el-button>
            <el-button size="small" @mousedown.prevent @click="exec('bold')"><b>B</b></el-button>
            <el-button size="small" @mousedown.prevent @click="imageInput.click()">插入图片</el-button>
            <input ref="imageInput" type="file" accept=".jpg,.jpeg,.png" hidden @change="insertImage" />
          </div>
          <!-- 粘贴只保留纯文本：外部图片和样式发到公众号会被过滤 -->
          <div ref="editor" class="editor-body" contenteditable="true" @paste="pastePlain"></div>
        </div>
      </el-form-item>
      <el-form-item label="原文链接">
        <el-input v-model="form.sourceUrl" placeholder="可选，https:// 开头" />
      </el-form-item>
      <el-form-item label="留言">
        <el-switch v-model="form.openComment" active-text="打开留言" />
      </el-form-item>
      <el-form-item label="发布方式">
        <el-radio-group v-model="form.draftOnly">
          <el-radio :value="true">只存到草稿箱</el-radio>
          <el-radio :value="false">直接发表（对外可见）</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="分类">{{ categoryPath(categories, category) || '未分类' }}</el-form-item>
      <el-form-item label="公众号" required>
        <div v-if="lockedId">
          <template v-if="lockedAccount">
            {{ lockedAccount.display_name }}
            <span v-if="lockedAccount.status !== 'active'" class="warn">（授权已失效，请先到「账号管理」重新授权）</span>
          </template>
          <span v-else class="warn">分类绑定的账号不是公众号，不能发布图文，请到「分类与绑定」修改</span>
        </div>
        <el-radio-group v-else v-model="form.accountId">
          <el-radio v-for="a in accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
            {{ a.display_name }}
            <span v-if="a.status !== 'active'" class="tip">（需重新授权）</span>
          </el-radio>
        </el-radio-group>
        <div v-if="!lockedId && !accounts.length" class="tip">还没有公众号，请先到「账号管理」授权</div>
      </el-form-item>
      <el-form-item label="定时">
        <div>
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则立即提交" :disabled-date="(d) => d < startOfToday" />
          <div class="tip">到点由本平台提交给公众号。审核通过点「发布」时还可以修改</div>
        </div>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { categoryPath } from '../categories'
import { cleanHtml } from '../html'
import { ARTICLE_PLATFORMS } from '../platforms'

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
const lockedAccount = computed(() => accounts.value.find((a) => a.id === lockedId.value))
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
  saved = snapshot()
})
</script>

<style scoped>
.note {
  margin-bottom: 16px;
}
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.warn {
  color: var(--el-color-danger);
  font-size: 12px;
}
.cover {
  width: 270px;
  height: 115px;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
}
.editor {
  width: 100%;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.editor-toolbar {
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color);
}
.editor-body {
  min-height: 300px;
  padding: 8px 12px;
  line-height: 1.7;
  outline: none;
}
.editor-body :deep(img) {
  max-width: 100%;
}
</style>
