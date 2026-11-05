<template>
  <div class="shell">
    <header class="bar">
      <el-button class="close" :icon="Close" aria-label="关闭" @click="emit('close')" />
      <div class="heading">
        <h1>{{ title }}</h1>
        <div class="sub"><slot name="subtitle" /></div>
      </div>
      <div class="actions"><slot name="actions" /></div>
    </header>
    <div class="body">
      <div class="main"><slot /></div>
      <aside v-if="$slots.aside" class="aside"><slot name="aside" /></aside>
    </div>
  </div>
</template>

<script setup>
import { Close } from '@element-plus/icons-vue'

// 发布视频、图文的全屏表单外框：顶栏放标题、发到哪里和提交按钮，下面填写；传了 aside 插槽时右边放预览和检查
defineProps({ title: { type: String, required: true } })
const emit = defineEmits(['close'])
</script>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--mp-page-bg);
}
.bar {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  padding: 12px 28px;
  background: #fff;
  border-bottom: 1px solid var(--mp-panel-border);
}
.close {
  width: 36px;
  height: 36px;
}
.heading {
  flex: 1;
  min-width: 240px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}
.sub {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.body {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: flex-start;
  gap: 24px;
  padding: 24px 28px 48px;
}
.main {
  flex: 999 1 560px;
  max-width: 820px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.aside {
  flex: 1 1 300px;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 84px;
}
/* 表单里的分块：白色卡片 + 小标题 */
.shell :deep(.section) {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px;
  background: #fff;
  border: 1px solid var(--mp-panel-border);
  border-radius: var(--mp-panel-radius);
}
.shell :deep(.section-title) {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.shell :deep(.section .el-form-item) {
  margin-bottom: 0;
}
</style>
