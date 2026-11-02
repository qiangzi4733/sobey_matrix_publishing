export const PLATFORMS = {
  wechat_mp: '微信公众号',
  douyin: '抖音',
  channels: '视频号',
  kuaishou: '快手',
}

// 扫码登录、需要定期检测登录状态的平台（已接入的）
export const QR_LOGIN_PLATFORMS = ['channels', 'douyin']

// 已支持发布的平台
export const PUBLISHABLE_PLATFORMS = ['channels', 'douyin']

export const formatTime = (value) => (value ? new Date(value).toLocaleString() : '-')
