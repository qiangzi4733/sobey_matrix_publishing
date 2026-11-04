<template>
  <div class="page-header">
    <div class="text">
      <h1>{{ title }}</h1>
      <p v-if="description || $slots.description"><slot name="description">{{ description }}</slot></p>
    </div>
    <div v-if="$slots.default" class="actions"><slot /></div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px 16px;
  margin-bottom: 20px;
}
.text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
}
p {
  margin: 0;
  color: var(--el-text-color-secondary);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
</style>
