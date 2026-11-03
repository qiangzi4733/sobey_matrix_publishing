<template>
  <!-- 任意一层都能选，不选为未分类 -->
  <el-tree-select
    :model-value="modelValue"
    :data="tree"
    :props="{ label: 'name', children: 'children' }"
    node-key="id"
    check-strictly
    default-expand-all
    clearable
    :placeholder="placeholder"
    style="width: 100%"
    @update:model-value="(v) => $emit('update:modelValue', v ?? null)"
  />
</template>

<script setup>
import { computed } from 'vue'

import { buildTree } from '../categories'

const props = defineProps({
  modelValue: { type: Number, default: null },
  categories: { type: Array, required: true },
  placeholder: { type: String, default: '未分类' },
})
defineEmits(['update:modelValue'])

const tree = computed(() => buildTree(props.categories))
</script>
