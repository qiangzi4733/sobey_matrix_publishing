<template>
  <span class="status-tag" :class="tone"><slot /></span>
</template>

<script setup>
// 状态一律用圆角胶囊，颜色按含义分：灰=草稿/未开始，琥珀=等人处理，红=失败/退回，
// 蓝=待发布，天蓝=进行中，紫=已定时，绿=成功。文字和底色的对比度都在 4.5:1 以上。
defineProps({
  tone: {
    type: String,
    default: 'gray',
    validator: (v) => ['gray', 'amber', 'red', 'blue', 'sky', 'purple', 'green'].includes(v),
  },
})
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 11px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  vertical-align: middle;
}
.gray {
  background: #f0f1f3;
  color: #4a505b;
}
.amber {
  background: #fff1d6;
  color: #8a5300;
}
.red {
  background: #fef0ef;
  color: #b42318;
}
.blue {
  background: #eef2ff;
  color: #2643b8;
}
.sky {
  background: #e6f4ff;
  color: #0b5cad;
}
.purple {
  background: #f1ebff;
  color: #5b33b6;
}
.green {
  background: #e7f6ec;
  color: #146c2e;
}
</style>
