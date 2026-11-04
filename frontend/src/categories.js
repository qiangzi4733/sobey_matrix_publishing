import { ARTICLE_PLATFORMS, VIDEO_PLATFORMS } from './platforms'

// 分类接口返回平铺列表（id、parent_id），这里拼成树和完整路径

export function buildTree(list) {
  const nodes = new Map(list.map((c) => [c.id, { ...c, children: [] }]))
  const roots = []
  for (const node of nodes.values()) {
    const parent = nodes.get(node.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  return roots
}

// 如「新闻稿 / 地方 / 安岳」；分类不存在时返回空字符串
export function categoryPath(list, id) {
  const byId = new Map(list.map((c) => [c.id, c]))
  const names = []
  for (let c = byId.get(id); c; c = byId.get(c.parent_id)) names.unshift(c.name)
  return names.join(' / ')
}

// 分类绑定的账号能新建哪种内容：公众号发图文，视频渠道发视频；没绑定为空
export function categoryKind(category) {
  const platform = category?.account?.platform
  if (VIDEO_PLATFORMS.includes(platform)) return 'video'
  if (ARTICLE_PLATFORMS.includes(platform)) return 'article'
  return null
}
