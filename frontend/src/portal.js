// 门户页的模块清单。按公司「智媒发布运营平台」的门户排列，矩阵分发只是其中一个模块；
// 只有带 to 的模块在本项目里能进，其余是给客户、领导看整体结构用的占位。
// color 是图标底色的渐变两端。
import {
  Bell,
  ChatDotRound,
  Collection,
  Cpu,
  DataAnalysis,
  DataLine,
  Document,
  EditPen,
  Film,
  FolderOpened,
  Grid,
  Histogram,
  Iphone,
  Key,
  MagicStick,
  Microphone,
  Monitor,
  Notebook,
  Picture,
  PieChart,
  Promotion,
  Reading,
  Search,
  Service,
  Share,
  Shop,
  Stamp,
  Tickets,
  TrendCharts,
  User,
  VideoCamera,
  VideoPlay,
  Warning,
  Connection,
} from '@element-plus/icons-vue'

const BLUE = ['#5fa2ff', '#2f6bf0']
const SKY = ['#62d3ff', '#1f8fef']
const VIOLET = ['#a98bff', '#6b4ff0']
const PINK = ['#ff8fa8', '#f0466e']
const ORANGE = ['#ffb36b', '#f5741f']
const GREEN = ['#5ee0a0', '#14a96b']
const TEAL = ['#5fe0d6', '#14a3a8']

export const PORTAL_GROUPS = [
  {
    key: 'collect',
    label: '内容采编',
    icon: EditPen,
    color: BLUE,
    items: [
      { label: '热点新闻', desc: '互联网热点采集分析', icon: Reading, color: BLUE },
      { label: '热点洞察', desc: 'AI 自动获取新闻', icon: Search, color: SKY },
      { label: '选题策划', desc: '报题、选题、策划', icon: Notebook, color: PINK },
      { label: '内容采编', desc: '内容采集、编辑', icon: EditPen, color: VIOLET },
      { label: '内容审核', desc: '内容审核、发布', icon: Stamp, color: BLUE },
      { label: '通联协作', desc: '通联记者、机构供稿管理', icon: Connection, color: SKY },
      { label: '通联协作-用户端', desc: '通联记者、机构供稿', icon: User, color: BLUE },
      { label: 'APE', desc: '智能内容生产', icon: MagicStick, color: VIOLET },
      { label: '内容库', desc: '统一内容资源库', icon: Collection, color: BLUE },
      { label: '融媒热线', desc: '群众热线受理', icon: Service, color: BLUE },
    ],
  },
  {
    key: 'publish',
    label: '发布管理',
    icon: Promotion,
    color: TEAL,
    items: [
      // 本项目
      { label: '矩阵分发', desc: '多账号审核、定时发布', icon: Share, color: BLUE, to: '/dashboard', current: true },
      { label: '内容运营', desc: '内容改写、样式模板调整', icon: Document, color: BLUE },
      { label: 'APP资讯发布', desc: 'CMS 资讯图文、链接、图集', icon: Tickets, color: BLUE },
      { label: 'APP视频发布', desc: 'VMS 视频、短视频、电视剧', icon: VideoPlay, color: VIOLET },
      { label: '互联网直播', desc: '互联网互动直播、活动直播', icon: VideoCamera, color: SKY },
      { label: '电视广播', desc: '互联网电视、广播直播及回看', icon: Monitor, color: ORANGE },
    ],
  },
  {
    key: 'tools',
    label: '运营工具',
    icon: MagicStick,
    color: VIOLET,
    items: [
      { label: 'AI云创', desc: 'AI 辅助内容创作', icon: MagicStick, color: TEAL },
      { label: '新媒体运营', desc: '新媒体账号运营', icon: TrendCharts, color: BLUE },
      { label: 'token HUB', desc: '模型调用统一管理', icon: Key, color: ['#3a4a6b', '#0f1a33'] },
      { label: '数字分身', desc: '数字人播报', icon: User, color: GREEN },
      { label: '智能体', desc: '业务智能体', icon: Cpu, color: BLUE },
      { label: '小程序', desc: '小程序管理', icon: Iphone, color: BLUE },
      { label: '网站编辑', desc: '网站内容编辑', icon: Grid, color: BLUE },
      { label: '智能助手', desc: '智能图片、视频、音频生成', icon: ChatDotRound, color: VIOLET },
      { label: 'H5工具', desc: '可视化 H5 活动、投票、抽奖', icon: Iphone, color: PINK },
      { label: '大屏编辑', desc: '可视化大屏编辑呈现', icon: Monitor, color: BLUE },
      { label: '视频编辑', desc: '在线视频剪辑', icon: Film, color: BLUE },
      { label: '无限画布', desc: '设计与排版画布', icon: Picture, color: PINK },
      { label: '数据新闻', desc: '数据可视化新闻', icon: DataLine, color: BLUE },
      { label: '视频工具', desc: '视频下载和去水印', icon: VideoPlay, color: TEAL },
      { label: '视频舆情', desc: '视频舆情监测', icon: Warning, color: BLUE },
      { label: '企微私域运营', desc: '企业微信私域运营', icon: ChatDotRound, color: SKY },
    ],
  },
  {
    key: 'activity',
    label: '活动管理',
    icon: Bell,
    color: ORANGE,
    items: [
      { label: '报料', desc: '用户报料、问政', icon: Microphone, color: PINK },
      { label: '举报', desc: '举报受理', icon: Warning, color: ORANGE },
      { label: '活动', desc: '线上活动管理', icon: Bell, color: PINK },
      { label: '机器人', desc: '智能客服机器人', icon: Cpu, color: VIOLET },
    ],
  },
  {
    key: 'data',
    label: '数据分析',
    icon: DataAnalysis,
    color: PINK,
    items: [
      { label: '传播分析', desc: '全渠道传播数据', icon: Histogram, color: PINK },
      { label: '账号数据', desc: '矩阵账号数据看板', icon: PieChart, color: BLUE },
    ],
  },
  {
    key: 'app',
    label: 'APP管理',
    icon: Iphone,
    color: VIOLET,
    items: [
      { label: 'APP配置', desc: '栏目、首页与版本配置', icon: FolderOpened, color: VIOLET },
      { label: '商城', desc: '积分商城管理', icon: Shop, color: ORANGE },
    ],
  },
]
