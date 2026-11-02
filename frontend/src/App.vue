<template>
  <router-view />
</template>

<style>
html,
body,
#app {
  margin: 0;
  height: 100%;
}
html {
  /* 暂只做浅色主题；不跟随系统深色模式 */
  color-scheme: light;
}
body {
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
}
</style>
