// 分类接口返回平铺列表（id、parent_id），这里拼成树和完整路径

// 和后端 routers/categories.py 的 MAX_DEPTH 一致
export const CATEGORY_MAX_DEPTH = 3

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
