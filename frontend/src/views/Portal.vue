<template>
  <div class="portal">
    <header class="top">
      <BrandLogo />
      <div class="top-right">
        <el-dropdown trigger="click" @command="onCommand">
          <button type="button" class="me">
            <span class="avatar" aria-hidden="true">{{ me?.name?.slice(0, 1) }}</span>
            <span class="me-name">{{ me?.name }}</span>
            <el-icon><CaretBottom /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ me?.tenant_name }}</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="body">
      <nav class="side" aria-label="模块分组">
        <button
          v-for="g in PORTAL_GROUPS"
          :key="g.key"
          type="button"
          class="side-item"
          :class="{ active: active === g.key }"
          @click="scrollTo(g.key)"
        >
          <span class="side-icon" :style="gradient(g.color)"><el-icon :size="12"><component :is="g.icon" /></el-icon></span>
          {{ g.label }}
        </button>
      </nav>

      <main ref="mainEl" class="main" @scroll="onScroll">
        <section v-for="g in PORTAL_GROUPS" :id="`group-${g.key}`" :key="g.key" class="group">
          <h2 class="group-title">
            <span class="side-icon" :style="gradient(g.color)"><el-icon :size="12"><component :is="g.icon" /></el-icon></span>
            {{ g.label }}
          </h2>
          <div class="tiles">
            <button
              v-for="item in g.items"
              :key="item.label"
              type="button"
              class="tile"
              :class="{ current: item.current }"
              @click="open(item)"
            >
              <span class="tile-icon" :style="gradient(item.color)"><el-icon :size="20"><component :is="item.icon" /></el-icon></span>
              <span class="tile-text">
                <span class="tile-name">{{ item.label }}</span>
                <span class="tile-desc">{{ item.desc }}</span>
              </span>
              <el-icon class="tile-go" :size="16"><ArrowRightBold /></el-icon>
            </button>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRightBold, CaretBottom } from '@element-plus/icons-vue'

import api, { clearToken } from '../api'
import BrandLogo from '../components/BrandLogo.vue'
import { PORTAL_GROUPS } from '../portal'

const router = useRouter()
const me = ref(null)
const active = ref(PORTAL_GROUPS[0].key)
const mainEl = ref(null)

onMounted(async () => {
  me.value = (await api.get('/auth/me')).data
})

const gradient = ([from, to]) => ({ background: `linear-gradient(135deg, ${from}, ${to})` })

function open(item) {
  if (item.to) router.push(item.to)
  else ElMessage.info(`「${item.label}」是智媒平台的其他模块，本环境只接入了矩阵分发`)
}

// 点左侧分组触发的平滑滚动期间不跟随滚动位置，否则末尾的短分组滚不到顶，高亮会跳到别的分组
let clickedAt = 0

function scrollTo(key) {
  active.value = key
  clickedAt = Date.now()
  const el = document.getElementById(`group-${key}`)
  mainEl.value.scrollTo({ top: el.offsetTop - 16, behavior: 'smooth' })
}

// 左侧高亮跟着滚动位置走：取顶部已经滚过的最后一个分组
function onScroll() {
  if (Date.now() - clickedAt < 1000) return
  const top = mainEl.value.scrollTop + 40
  let current = PORTAL_GROUPS[0].key
  for (const g of PORTAL_GROUPS) {
    if (document.getElementById(`group-${g.key}`).offsetTop <= top) current = g.key
  }
  // 滚到底时最后几个短分组到不了顶部，直接算最后一个
  const el = mainEl.value
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 2) current = PORTAL_GROUPS.at(-1).key
  active.value = current
}

function onCommand(cmd) {
  if (cmd === 'logout') {
    clearToken()
    router.push({ name: 'login' })
  }
}
</script>

<style scoped>
.portal {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f4f6fa;
}
.top {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 28px;
  background: #fff;
  box-shadow: 0 1px 0 #e8ebf1;
}
.me {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 6px;
  border: 0;
  background: none;
  font: inherit;
  color: var(--el-text-color-primary);
  cursor: pointer;
}
.avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #5fa2ff, #2f6bf0);
  color: #fff;
  font-weight: 600;
}
.me-name {
  font-size: 15px;
}
.body {
  flex: 1;
  min-height: 0;
  display: flex;
}
.side {
  flex: 0 0 196px;
  box-sizing: border-box;
  padding: 8px 8px;
  background: #fff;
}
.side-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 50px;
  margin-bottom: 6px;
  padding: 0 14px;
  border: 0;
  border-radius: 8px;
  background: none;
  font: inherit;
  font-size: 15px;
  color: var(--el-text-color-regular);
  text-align: left;
  cursor: pointer;
}
.side-item:hover {
  background: #f2f4f8;
}
.side-item.active {
  background: #e8ebf1;
  color: var(--el-text-color-primary);
  font-weight: 600;
}
.side-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  color: #fff;
}
.main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 8px 20px 40px;
  position: relative;
}
.group {
  padding-top: 12px;
  margin-bottom: 20px;
}
.group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 4px 0 16px;
  font-size: 17px;
  font-weight: 600;
}
.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 18px;
}
.tile {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 64px;
  padding: 0 14px 0 18px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(30, 40, 70, 0.06);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}
.tile:hover {
  box-shadow: 0 6px 16px rgba(30, 60, 140, 0.12);
  transform: translateY(-1px);
}
/* 本项目所在的模块，客户和领导一眼能找到 */
.tile.current {
  border-color: #9bb7f7;
  background: linear-gradient(90deg, #f1f5ff, #fff);
}
.tile-icon {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  color: #fff;
}
.tile-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.tile-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.tile-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tile-go {
  flex: none;
  color: #8a909c;
}
</style>
