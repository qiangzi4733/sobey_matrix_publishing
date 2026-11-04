<template>
  <section class="section">
    <h2 class="section-title">提交前检查</h2>
    <ul class="checks">
      <li v-for="item in items" :key="item.label">
        <span class="mark" :class="item.level" aria-hidden="true">{{ MARKS[item.level] }}</span>
        <span class="text">
          <span>{{ item.label }}</span>
          <span v-if="item.hint" class="hint">{{ item.hint }}</span>
        </span>
        <span class="sr-only">{{ LEVELS[item.level] }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
// 填写时实时给出的检查结果。level：ok 没问题，warn 能提交但要留意，error 提交审核会被拦下
defineProps({ items: { type: Array, required: true } })

const MARKS = { ok: '✓', warn: '!', error: '×' }
const LEVELS = { ok: '通过', warn: '注意', error: '需要处理' }
</script>

<style scoped>
.checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.mark {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
}
.mark.ok {
  background: #e7f6ec;
  color: #146c2e;
}
.mark.warn {
  background: #fff1d6;
  color: #8a5300;
}
.mark.error {
  background: #fef0ef;
  color: #b42318;
}
.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
