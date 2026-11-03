export const PLATFORMS = {
  wechat_mp: '微信公众号',
  douyin: '抖音',
  channels: '视频号',
  kuaishou: '快手',
}

// 扫码登录、需要定期检测登录状态的平台（已接入的）
export const QR_LOGIN_PLATFORMS = ['channels', 'douyin']

// 已支持发布视频、图文的平台
export const VIDEO_PLATFORMS = ['channels', 'douyin']
export const ARTICLE_PLATFORMS = ['wechat_mp']

export const REVIEW_STATUS = {
  pending: { label: '待审核', type: 'warning' },
  rejected: { label: '已退回', type: 'danger' },
  approved: { label: '待发布', type: 'primary' },
  published: { label: '已发布', type: 'success' },
}

// 客户都在国内，时间一律按北京时间显示，不随浏览器时区变化；格式如 2026-11-02 18:28
const BEIJING = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export const formatTime = (value) => {
  if (!value) return '-'
  const part = Object.fromEntries(BEIJING.formatToParts(new Date(value)).map((p) => [p.type, p.value]))
  return `${part.year}-${part.month}-${part.day} ${part.hour}:${part.minute}`
}
