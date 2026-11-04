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

// 发布视频时各平台不同的规则，和后端 platforms/video_options.py、scheduling.py 保持一致
export const VIDEO_RULES = {
  douyin: { titleMax: 30, schedule: '2 小时后、14 天内' },
  channels: { titleMax: 200, schedule: '10 分钟后、30 天内', titleTip: '视频号短标题会自动截取为 7~15 字' },
}

// 平台专属配置在内容详情里的显示名；image 表示值是图片地址
export const VIDEO_OPTION_LABELS = {
  cover_landscape: { label: '横封面', image: true },
}

// 审核状态和发布状态分开显示；发布状态是这一轮发布任务的结果，没点「发布」时为空。tone 是 StatusTag 的颜色
export const REVIEW_STATUS = {
  draft: { label: '草稿', tone: 'gray' },
  pending: { label: '待审核', tone: 'amber' },
  rejected: { label: '已退回', tone: 'red' },
  approved: { label: '已通过', tone: 'green' },
}

export const PUBLISH_STATUS = {
  publishing: { label: '发布中', tone: 'sky' },
  // 平台自带定时的已交给平台、或等本平台到点提交，到点前都不对外可见
  scheduled: { label: '已定时', tone: 'purple' },
  success: { label: '发布成功', tone: 'green' },
  draft_saved: { label: '已存草稿', tone: 'green' },
  failed: { label: '发布失败', tone: 'red' },
}

// 没点过发布、或这一轮发布失败的内容可以修改、删除（和后端 _get_editable 一致）
export const isEditable = (post) => !post.publish_status || post.publish_status === 'failed'


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
