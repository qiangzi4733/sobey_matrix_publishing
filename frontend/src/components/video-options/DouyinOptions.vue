<template>
  <el-form-item label="横封面">
    <div>
      <CoverUpload v-model="options.cover_landscape" shape="landscape" />
      <div class="tip">4:3 横版，jpg / png，5MB 以内；不传由抖音用竖封面或视频画面自动生成。抖音建议横竖封面都设置</div>
    </div>
  </el-form-item>
</template>

<script setup>
import CoverUpload from '../CoverUpload.vue'

// 抖音专属配置，字段和后端 video_options.DouyinOptions 一致
const options = defineModel({ type: Object, required: true })
</script>

<style scoped>
.tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
