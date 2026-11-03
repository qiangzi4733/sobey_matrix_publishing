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

export const formatTime = (value) => (value ? new Date(value).toLocaleString() : '-')
