<template>
  <div class="wrap">
    <el-upload :show-file-list="false" accept=".jpg,.jpeg,.png" :http-request="upload" :disabled="uploading">
      <div v-loading="uploading" class="box" :class="shape">
        <img v-if="url" :src="url" alt="封面" />
        <span v-else class="placeholder">+ 上传</span>
      </div>
    </el-upload>
    <el-button v-if="url" link type="danger" @click="url = ''">移除</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import api from '../api'

// 视频封面，值是 /api/video-covers 返回的地址，空字符串表示不用自定义封面
const url = defineModel({ type: String, default: '' })
defineProps({
  // portrait 竖版 3:4，landscape 横版 4:3，只影响预览框的比例
  shape: { type: String, default: 'portrait' },
})
const uploading = ref(false)

async function upload({ file }) {
  if (file.size > 5 * 1024 * 1024) return ElMessage.warning('封面不能超过 5MB')
  const body = new FormData()
  body.append('image', file)
  uploading.value = true
  try {
    url.value = (await api.post('/video-covers', body)).data.url
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.box {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
  cursor: pointer;
}
.box.portrait {
  width: 90px;
  height: 120px;
}
.box.landscape {
  width: 160px;
  height: 120px;
}
.box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.placeholder {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
