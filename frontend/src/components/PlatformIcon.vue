<template>
  <img :src="ICONS[platform]" :alt="PLATFORMS[platform]" :style="{ width: `${size}px`, height: `${size}px` }" class="icon" />
</template>

<script setup>
import { PLATFORMS } from '../platforms'
import channels from '../assets/platforms/channels.png'
import douyin from '../assets/platforms/douyin.svg'
import kuaishou from '../assets/platforms/kuaishou.svg'
import wechatMp from '../assets/platforms/wechat_mp.svg'

// 公众号、抖音、快手是矢量图（图形来自 simple-icons，CC0）；视频号没有矢量版，用官网 favicon
const ICONS = { wechat_mp: wechatMp, douyin, kuaishou, channels }

defineProps({
  platform: { type: String, required: true },
  size: { type: Number, default: 16 },
})
</script>

<style scoped>
.icon {
  flex: none;
  vertical-align: middle;
}
</style>
