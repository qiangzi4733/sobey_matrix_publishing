<template>
  <!-- 公司平台的标志。拿到正式 logo 图片后换成 <img> -->
  <span class="brand">
    <svg class="mark" viewBox="0 0 64 40" aria-hidden="true">
      <defs>
        <linearGradient id="brand-fm" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stop-color="#1a3fbf" />
          <stop offset="1" stop-color="#2f7bf5" />
        </linearGradient>
      </defs>
      <path d="M2 30 Q20 8 62 4 Q30 12 14 30 Z" fill="#7fb3ff" opacity="0.7" />
      <text x="6" y="34" font-size="30" font-style="italic" font-weight="900" font-family="Arial Black, Arial, sans-serif" fill="url(#brand-fm)">FM</text>
    </svg>
    <span class="text">
      <span class="en">Fast Media</span>
      <span class="cn">智媒发布运营平台</span>
    </span>
  </span>
</template>

<style scoped>
.brand {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #1a3fbf;
}
.mark {
  width: 64px;
  height: 40px;
}
.text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}
.en {
  font-size: 21px;
  font-weight: 800;
  font-family: Arial, Helvetica, sans-serif;
  letter-spacing: 0.2px;
}
.cn {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
}
</style>
