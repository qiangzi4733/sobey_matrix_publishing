<template>
  <el-card header="发布图文（微信公众号）" class="card">
    <el-form :model="form" label-width="90px" @submit.prevent="submit">
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
      <el-form-item label="公众号" required>
        <el-checkbox-group v-model="form.accountIds">
          <el-checkbox v-for="a in accounts" :key="a.id" :value="a.id" :disabled="a.status !== 'active'">
            {{ a.display_name }}
            <span v-if="a.status !== 'active'" class="tip">（需重新授权）</span>
          </el-checkbox>
        </el-checkbox-group>
        <div v-if="!accounts.length" class="tip">还没有公众号，请先到「账号管理」授权</div>
      </el-form-item>
      <el-form-item label="定时">
        <div>
          <el-date-picker v-model="form.scheduledAt" type="datetime" placeholder="不选则立即提交" :disabled-date="(d) => d < startOfToday" />
          <div class="tip">到点由本平台提交给公众号</div>
        </div>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="submitting">提交</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import api from '../api'
import { ARTICLE_PLATFORMS } from '../platforms'

const router = useRouter()
const accounts = ref([])
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
  accountIds: [],
  scheduledAt: null,
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

async function submit() {
  const content = editor.value.innerHTML.trim()
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (!form.coverUrl) return ElMessage.warning('请上传封面')
  if (!editor.value.innerText.trim() && !content.includes('<img')) return ElMessage.warning('请填写正文')
  if (!form.accountIds.length) return ElMessage.warning('请选择公众号')
  if (!form.draftOnly) {
    await ElMessageBox.confirm('发表后文章对外可见，确定直接发表？', '直接发表', { type: 'warning' })
  }

  submitting.value = true
  try {
    await api.post('/articles', {
      title: form.title,
      author: form.author,
      digest: form.digest,
      content,
      cover_url: form.coverUrl,
      source_url: form.sourceUrl,
      open_comment: form.openComment,
      draft_only: form.draftOnly,
      account_ids: form.accountIds,
      scheduled_at: form.scheduledAt ? form.scheduledAt.toISOString() : null,
    })
    ElMessage.success('已提交')
    router.push({ name: 'tasks' })
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const all = (await api.get('/accounts')).data
  accounts.value = all.filter((a) => ARTICLE_PLATFORMS.includes(a.platform))
})
</script>

<style scoped>
.card {
  max-width: 860px;
}
.tip {
  color: var(--el-text-color-secondary);
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
