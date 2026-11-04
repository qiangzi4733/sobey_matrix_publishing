import { reactive } from 'vue'

import api from './api'

// 左侧导航上的提醒：内容里等人处理的条数、登录失效的账号数。
// 内容管理、账号管理加载数据后调用 refreshBadges，其他页面切换时由 Layout 刷新
export const badges = reactive({ todo: 0, expiredAccounts: 0 })

export async function refreshBadges() {
  const [counts, accounts] = await Promise.all([api.get('/posts/counts'), api.get('/accounts')])
  const c = counts.data
  badges.todo = c.pending + c.to_publish + c.failed
  badges.expiredAccounts = accounts.data.filter((a) => a.status !== 'active').length
}
