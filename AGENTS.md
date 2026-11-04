# AGENTS.md

给接手本项目的 AI 编码助手（Claude Code 等）看的工作说明。用中文和用户沟通。

## 项目是什么

新媒体矩阵分发平台，**面向客户的多租户 SaaS**：

- 客户注册后成为一个租户（公司），在平台里管理自己名下的多个矩阵账号，一条内容只发到一个账号（2026-11-03 起，之前可多选；同一内容要发多个账号就分别提交）。
- 微信公众号、快手：客户**授权**自己的账号（官方 API）。
- 抖音、微信视频号：客户**扫码登录**，平台保存登录态并定期检测，失效后提醒重新扫码（浏览器自动化）。
- 公众号用「发表」（草稿 `draft/add` → `freepublish/submit`），**不是群发**。
- 部署目标：Ubuntu 20.04 云服务器（固定 IP），全部跑在 Docker Compose 里。

### 运行方式（抖音、视频号）

客户只用浏览器访问我们的网站（B/S），不装任何软件、不需要开着自己的电脑。真正操作抖音/视频号的是**服务器上的无窗口 Chrome**（browser-worker）：

- 扫码登录：服务器 Chrome 打开平台登录页，把二维码转给客户网页，客户用手机扫；登录态（cookie）保存在服务器、加密存库。
- 发布：客户提交后任务进队列，服务器为每个任务**新开一个浏览器环境并装上该账号的登录态**，替客户上传、填表、发布，结束后把刷新后的登录态存回。账号之间互不干扰。
- 定时检测：每 6 小时用保存的登录态打开一次平台，确认有效并让平台续期。

由此带来的约束（设计新功能时要考虑）：

- 在平台看来所有账号都从**同一台服务器（同一 IP、同一设备环境）**登录和发布，账号多了可能触发风控，规模上去后需要按账号配代理 IP。
- 服务器对平台是「新设备」，抖音首次登录会要求短信身份验证；正式部署换了 IP/环境后可能再触发一次。
- 客户自己在别处登录可能把平台挤下线（视频号疑似只允许一个网页登录，待确认）。
- 并发有限：目前 browser-worker 同时处理 2 个任务（每个浏览器约几百 MB 内存），其余排队；客户多了要加 worker。

### 平台进度

| 平台 | 方式 | 状态 |
|---|---|---|
| 视频号 | 扫码登录 + 浏览器自动化（patchright + Google Chrome） | **核心链路已跑通**：扫码登录、登录检测、发布、平台原生定时发表，均已用真实账号验证（立即发布由用户自行测试，结果未记录）。还缺的功能见「待办」 |
| 微信公众号 | 微信开放平台**第三方平台**（平台型）授权，用户的资质已申请下来 | **本地模拟授权 + 真实草稿/发表接口已跑通**（2026-11-03）：第三方平台一侧由 `mock_wechat.py` 模拟，存草稿和直接发表都已用测试公众号真实验证。真实第三方平台要等域名和部署 |
| 抖音 | 扫码登录 + 浏览器自动化（参考 social-auto-upload 的 `uploader/douyin_uploader`） | **核心链路已跑通**：扫码登录（含短信身份验证）、登录检测、发布、平台原生定时发布。登录、检测、定时发布已用真实账号验证；立即发布未测。还缺的功能见「待办」 |
| 快手 | 快手开放平台 OAuth，scope `user_video_publish`，三步上传发布 | **等待权限审批，暂不做** |

## 架构

```
frontend (Vue3 + Element Plus, Vite)
   │ /api 代理
backend (FastAPI)  ── PostgreSQL（业务数据）
   │                └ Redis（Celery broker + 扫码登录会话 + 短信验证码中转）
   ├─ worker          Celery 默认队列 `celery`：定时分发、批量检测（以后公众号 API 发布也放这里）
   ├─ browser-worker  Celery `browser` 队列：扫码登录、登录检测、视频号/抖音发布（amd64 + Chrome）
   └─ beat            每分钟分发到点的定时任务；每 6 小时检测扫码类账号
```

关键文件：

- `backend/app/models.py`：`Tenant` / `User` / `Account`（矩阵账号，凭证加密存 `credentials_encrypted`）/ `Post`（一次发布的内容，带审核状态 `review_status`、提交时选的 `account_id`（账号被移除后为空、要修改时重新选）和这一轮的发布任务 `current_task_id`）/ `PublishTask`（**点「发布」时才生成**；发布失败后修改再发布会有多条，旧的留作发布记录；引入单账号前的旧内容也可能有多条）/ `Category`（内容分类，租户内一棵树，可以绑定一个发布账号 `account_id`；`Post.category_id` 为空是未分类）。
- `backend/app/tasks.py`：所有 Celery 任务；`PUBLISHABLE`、`BROWSER_PLATFORMS` 控制平台能力；`enqueue_publish` 按平台选队列。
- `backend/app/platforms/`：每个平台一个模块。`base.py` 定义 `LoginExpired` / `PublishError(message, screenshot)`；`browser.py` 是浏览器类平台共用的启动/截图工具和 `AskCode` 类型；`scheduling.py` 定义哪些平台用**平台原生定时**；`video_options.py` 定义发布视频时各平台的标题字数上限和**专属配置**；`channels.py` 视频号、`douyin.py` 抖音。`tasks._browser_module()` 按平台取模块。
- `backend/app/login_sessions.py`：扫码登录会话（Redis，15 分钟过期），worker 写二维码和进度，前端每 2 秒轮询。
- `backend/app/verification.py`：**短信验证码中转**。平台中途要求验证码时，worker 把验证弹窗截图推给前端并等待客户输入（scope：登录 `login:{id}`、发布 `task:{id}`）。前端：扫码弹窗里出现输入框；发布记录里出现「输入验证码」按钮。
- `backend/app/routers/`：`auth`（注册/登录/JWT）、`accounts`（账号、扫码登录、检测）、`categories`（内容分类）、`posts`（视频/图文的提交审核、修改、通过、退回、发布、删除，任务列表、重试、失败截图）。
- `frontend/src/platforms.js`：前端的平台名称和能力列表，接入新平台时同步修改。
- `backend/app/platforms/wechat_mp.py`：公众号第三方平台授权（ticket → component token → 预授权码 → auth_code → refresh_token）和草稿/发表；`wechat_crypto.py` 推送消息的签名与加解密；`routers/wechat_mp.py` 发起授权、回调、授权事件接收 URL（`/api/wechat-mp/events`）。
- `backend/app/mock_wechat.py`：`WECHAT_MP_MOCK=true` 时挂载的「开放平台」模拟：按官方格式模拟 ticket 推送（beat 每 10 分钟）、第三方平台接口和授权确认页；授权方 access_token 用测试公众号 AppID/AppSecret 真实换取，草稿/发表走真实接口。`/api/mock-wx/push-ticket`、`/push-unauthorized` 可手动触发推送。**生产必须关闭**。
- 图文：`Article`（正文、封面，按 post_id 挂在 `Post` 上）、`PublishResult`（草稿 media_id、文章链接）是新表，没有改已有表。正文图片先传到本平台 `/api/article-images/{tenant}/{uuid}`，发布时由 worker 转传微信（`uploadimg`）。

### 必须遵守的设计约定

- **租户隔离**：所有查询都按 `user.tenant_id` 过滤；访问其他租户的资源一律返回 404，不要返回 403（避免泄露存在性）。
- **凭证**：平台 token / cookie 一律用 `app.security.encrypt_credentials` 加密后存库，不落明文文件。扫码类平台存 `{"storage_state": ...}`。`CREDENTIALS_KEY` 丢失后所有账号需重新授权。
- **浏览器依赖隔离**：`patchright` 只装在 browser-worker 镜像里。平台模块（如 `channels.py`）只能在任务函数**内部**导入；backend 需要用到的规则（如定时范围）放到不依赖浏览器的模块（如 `scheduling.py`）。
- **发布不可重复**：`run_publish_task` 用 `acks_late=False`，并用 `UPDATE ... WHERE status='queued'` 抢占任务。宁可漏发不可重发。
- **定时发布两种模式**：`scheduling.NATIVE_SCHEDULE` 里的平台在提交时就把定时时间交给平台（视频号：10 分钟后～30 天内；抖音：2 小时后～14 天内；都按北京时间）；其他平台建任务时状态为 `scheduled`，由 beat 到点改为 `queued`。不要用 Celery 的 `eta` 做长延时（Redis visibility timeout 会导致重复投递）。
- **平台模块的写法**（参考 `channels.py` / `douyin.py`，接口保持一致，任务层不区分平台）：
  - `login(on_qr, on_status, ask_code) -> (storage_state, {"external_id", "nickname", "avatar_url"})`；`check(state) -> state`；`publish(state, video, title, description, tags, schedule_at, ask_code, cover, options) -> state`（`cover` 竖封面文件路径，`options` 本平台专属配置，图片字段已换成文件路径）；
  - 用同步 API（`patchright.sync_api`），登录态作为 dict 传入/传出；
  - 平台要求短信验证码时调用 `ask_code(提示, 弹窗截图)`，返回客户输入的验证码；
  - 发布、检测成功后返回刷新后的 `storage_state`，由任务写回数据库；
  - 登录失效抛 `LoginExpired`，可预期的失败抛 `PublishError` 并附 `screenshot(...)` 现场截图；
  - 页面选择器写明实测日期，平台改版时最先坏的就是这里。
- **数据库用 Alembic 迁移**（2026-11-03 引入）：配置和迁移文件在 `backend/app/alembic.ini`、`backend/app/migrations/`（放在 app 里是因为开发环境只挂载了 app 目录）。backend 启动时由 `app.migrate.upgrade()` 升级到最新版本；引入前用 `create_all` 建的库会先自动标记为 `0001`。改模型后在 backend 容器里生成迁移并检查内容：`alembic -c app/alembic.ini revision --autogenerate -m "说明"`，再用 `alembic -c app/alembic.ini check` 确认模型和库一致。不要手改生产库。
- 非原生枚举字段（`Enum(..., native_enum=False)`）的列宽按建表时最长的取值确定，以后要加更长的取值时先写迁移改列宽；新枚举字段直接写明 `length`。
- **审核状态和发布状态分开**（2026-11-03，用户确认）：
  - 审核状态 `review_status`：草稿 / 待审核 / 已退回 / 已通过。**草稿只有提交人自己看得到**（列表、详情、审核、移动分类都按 `created_by` 过滤，别人访问返回 404），存草稿只要求标题，账号、视频、封面、正文等在提交审核时才校验；已提交的内容不能再存为草稿。
  - 发布状态不单独存，由 `Post.current_task` 算出（`posts._publish_status`）：没有任务为「未发布」，排队/执行中为「发布中」，我们自己等定时（`scheduled`）或平台原生定时已提交但还没到点为「已定时」，成功为「发布成功」（公众号只存草稿时为「已存草稿」），失败为「发布失败」。「发布成功」只表示提交给了平台，不代表平台审核通过（还没接）。
  - 审核通过后人手动点「发布」才生成 `PublishTask`（之后的排队、定时、重试不变）；点「发布」时锁住内容行，**重新校验账号状态和定时范围**（审核期间可能过期），可以改定时。
  - **没点过发布、或这一轮发布失败的内容可以修改、删除**，其他（发布中、已定时、已发布）不能。发布失败后修改会清空 `current_task`、回到待审核，旧任务留在发布记录里但不能再重试（`can_retry`，重试和修改都锁内容行，互斥）。前端修改失败内容前提醒客户先去平台确认没有发出去（有些失败发生在点了平台发布按钮之后）。
  - 审核状态变更按当前状态条件 `UPDATE`，重复点击只生效一次。目前同一租户任何用户都能审核（包括审核自己提交的），以后做基于角色的权限。
  - 内容列表按「要谁处理」分页签：草稿、待审核、已退回、待发布、发布中、已定时、已发布、发布失败、全部（后端 `GET /api/posts?status=`）。列表里审核要点进详情（先看内容再通过/退回）。
  - 迁移 0006：旧的「已发布」改为「已通过」+ `current_task_id` 指向最新任务，旧内容的 `account_id` 从发布任务补上；账号已移除的显示任务里记下的 `account_name`。
- **视频表单 = 通用字段 + 平台专属配置**（2026-11-03，用户确认）：视频、竖封面（3:4，可不传）、标题、描述、话题、分类、定时是通用字段，存在 `Post` 上；只有某个平台才有的选项存 `Post.options`（JSON），每个平台一个 pydantic 模型（`video_options.py`，`extra="forbid"`），提交时按所选账号的平台校验，标题字数上限也按平台。图片字段接口里传 `/api/video-covers/...` 地址、库里存相对 media_dir 的路径。账号由分类决定（见「分类绑定账号」），表单里的字数、定时提示跟着账号的平台变，专属配置组件放 `components/video-options/`、登记在 `VideoForm.vue` 的 `OPTION_FORMS`；只有分类没绑定账号的老内容修改时能自己选账号，换成其他平台的账号时确认后清空专属配置。复制到同平台账号时沿用配置。视频封面和图文图片一样不随内容删除（复制出来的内容共用）。加新选项：后端模型 + 前端组件 + `platforms.js` 的 `VIDEO_OPTION_LABELS`（详情页显示名）+ 平台模块读取。
- **前端入口是「内容管理」页**（`views/Contents.vue`）：列表里完成新建、修改、审核、发布、删除。发布视频用弹窗、发布图文用宽抽屉（表单组件 `components/VideoForm.vue` / `ArticleForm.vue`）；有未提交的改动时关闭要确认，提交中不能关。旧地址 `/publish`、`/publish-article`、`/review` 都重定向到这里。
- **内容分类**（2026-11-03）：租户内多级分类，层数不限（2026-11-04 去掉了 3 层限制），一条内容一个分类。按分类筛选时包含下级分类；有下级分类或内容的分类不能删除（不自动改成未分类）。分类的增删改在左侧菜单的「分类与绑定」页（`views/Categories.vue`，2026-11-04 从内容管理的弹窗挪出来，原名「分类管理」），内容管理页左侧只是分类树（筛选用），另有「只看我提交的」筛选。以后做权限时按分类给用户分配可管理范围（用户已确认）。
- **分类绑定账号**（2026-11-04，用户确认）：客户用分类管理账号。分类可以绑定一个账号（界面上先选渠道再选账号，库里只存 `Category.account_id`，快手未开放不能选）；一个账号可以绑多个分类。
  - 绑定只对这个分类自己生效，**下级分类不沿用上级的**。内容管理页只有选中绑定了账号的分类才显示新建按钮：绑公众号显示「发布图文」，绑抖音/视频号显示「发布视频」；「全部」「未分类」和没绑定的分类显示「去设置」引导。
  - 新建（包括复制）必须放进绑定了账号的分类，账号由分类决定，客户不能改；**内容建好后分类不能改**（「移到分类」功能已删除，表单里分类只显示）。
  - 改绑定只影响之后：草稿在提交审核时用分类当前的账号；已提交的内容修改时沿用原账号，原账号被移除了才改用分类的；分类没绑定账号的老内容修改时客户自己选。规则在后端 `posts._edit_account_id`，前端两个表单里有同样的判断。
  - 账号被移除时分类的绑定由外键置空，移除前提示影响几个分类。分类树上绑定的账号登录失效时标「需重新登录」。
- **复制**：内容列表和详情可以复制任意状态的内容，选一个绑定了同类渠道的目标分类再提交（发到那个分类的账号，定时清空）。视频提交时带 `copy_from`，后端给原视频建硬链接，不重新上传、也不和原内容共用路径（删除内容会删视频文件）；图文直接引用同一批图片（正文图片和封面不随内容删除）。视频只能复制到视频渠道、图文只能到公众号。
- 审核预览视频用 `/api/posts/{id}/video?token=`：`<video>` 带不上登录头，令牌只对这一个视频有效、2 小时过期（`security.create_video_token`）。用户提交的正文 HTML 放进页面前都要经过前端 `src/html.js` 的 `cleanHtml`。
- 代码风格：中文注释，只写「为什么」；跟随周围代码的命名和写法；不加无用的抽象。
- **UI 重构**（2026-11-04 开始，用户确认方向）：设计稿在 Claude 画布「矩阵分发平台 UI 重构」（https://claude.ai/artifact/Da6jWWWW8SkyeCpbbnWUyc，共 10 张），分 5 步做：① 主题、公共组件、左侧导航（已完成）② 内容管理和详情（状态合并成一列、页签带数量、新建先选分类、发布记录并进详情后删掉单独页面）③ 视频/图文表单改全屏页 + 预览和提交前检查 ④ 账号卡片、分类与绑定左右分栏 ⑤ 工作台首页、登录页、手机适配。
  - 继续用 Element Plus，外观靠 `src/theme.css` 覆盖它的 CSS 变量（改主色要把 light-N / dark-2 一起改）；自己的变量用 `--mp-` 前缀，白色卡片用 `.mp-panel`。
  - 不用 Google Fonts（国内访问不了），用系统中文字体。
  - 状态一律用 `components/StatusTag.vue`（`tone`：gray/amber/red/blue/sky/purple/green），`platforms.js` 里的状态定义带 `tone`；页面标题用 `components/PageHeader.vue`，主操作放在它的默认插槽里；平台图标仍用 `PlatformIcon.vue`（真实 logo，设计稿里的字母方块只是占位）。

### 已踩过的坑（视频号，2026-11 实测）

- 视频号上传必须用 **Google Chrome**（Chromium 不支持 H.264）。Chrome 只有 linux/amd64，所以 browser-worker 固定 `platform: linux/amd64`，在 Apple Silicon 开发机上走仿真，速度偏慢（扫码登录全程约 85 秒，发布约 75 秒）。
- 登录二维码在 `open.weixin.qq.com/connect/qrconnect` 的 iframe 里，可见的是 `img.web_qrcode_img`，同一 iframe 里还有一个**隐藏的** `img.qrcode`，必须按 `:visible` 过滤。
- 登录后账号信息从 `auth/auth_data` 接口响应的 `data.finderUser`（`nickname` / `uniqId` / `headImgUrl`）获取，以 `uniqId`（`sph...`）作为 `external_id` 去重。
- 不能直接打开 `/platform/post/create`（表单不挂载），要先进 `/platform` 首页再点「发表视频」。
- 定时发表日历会停在上次查看的月份，需要能前后翻；超过 30 天的日期是 disabled。
- 微信头像有防盗链，前端 `<img>` 要加 `referrerpolicy="no-referrer"`。
- **视频号助手疑似同一账号只允许一个网页登录**：2026-11-02 用户自己登录视频号助手后，平台保存的登录态随即失效（待用户确认）。若属实，客户自己登录视频号助手就会把平台挤掉，需要重新扫码。
- 视频号流程移植自 social-auto-upload（MIT），见 `THIRD_PARTY_NOTICES.md`。上游源码可 `git clone --depth 1 https://github.com/dreammis/social-auto-upload` 到临时目录**只读参考**，不要整体引入为依赖，原因见下一节。

### 为什么没有直接用 social-auto-upload 做引擎（2026-11-02 已向用户说明；用户只是询问原因，尚未表态是否要改变做法）

用户最初的计划是「用这个开源项目实现抖音和视频号」。实际做法是**参考它的页面操作流程，按本项目需要重写**（每个平台约 400 行），原因：

- 它是「一个人在自己电脑上用」的设计：cookie 存成本地文件、全局配置 `conf.py`；我们需要多租户、凭证加密存库。
- 它默认有人守在可见的浏览器/终端前：身份验证时提示「请在弹出的浏览器中手动输入」，发布时的短信验证码从终端或**全局固定的 `verify_code.txt`** 读取——服务器无窗口，且多客户并发会串号。
- 它内置作者自己的业务设定：抖音强制勾选「内容由AI生成」、打开同步其他平台；视频号标注「含AI生成内容」。
- 它正在重构，接口不稳定；固定版本后也就拿不到上游修复。

它的价值在于**持续参考选择器和功能实现**：补封面、自主声明、合集、商品链接、图文等功能时直接参考它移植；平台改版导致我们出错时，先看它最近的提交有没有对应修复。用户如果以后想改成「发布环节调用它的上传器」（登录和验证仍用我们自己的），需要处理临时 cookie 文件、全局配置和验证码文件冲突。

### 已踩过的坑（抖音，2026-11 实测）

- 登录页二维码是 `#animate_qrcode_container` 里的 `data:image` 图片，会自己定时刷新；**扫码后同一位置会换成扫码人的头像卡片**（也是图片），不能拿「二维码图片是否可见」判断扫码状态。前端展示的是整块扫码栏 `#douyin_login_comp_scan_code`，客户能看到「需在手机上进行确认」等状态。
- 扫码并在手机确认后，新设备会弹「身份验证」面板（class 含 `second_verify_panel` / `uc_verification_component_layout`）：先选验证方式（选含「短信」的那项），面板随即整体换成「接收短信验证码」页（自动发送）。**操作一律限定在面板内、每步重新定位**——背后的手机号登录表单也有验证码输入框和「获取验证码」，被盖住点不动。
- 「验证」按钮不在面板元素内部，按整页找文字恰好为「验证」的元素（登录表单的按钮是「登录」，不会误中）。
- 验证通过一次后，同一浏览器环境再扫码可能不再要求短信验证。
- 账号信息用登录后的 `GET /web/api/media/user/info/` 读取，以 `user.uid` 作为 `external_id`（抖音号客户可以改，不能用来去重）。
- 发布页：上传后跳到 `/creator-micro/content/post/video`；标题 `input[placeholder*="填写作品标题"]`（最多 30 字），描述是 `div.zone-container[contenteditable]`；定时发布在 `.semi-input[placeholder="日期和时间"]` 输入 `YYYY-MM-DD HH:MM` 后回车，**超出范围抖音会把值改回默认（当前 + 2 小时）**，必须回读核对。
- 封面（2026-11-03 实测）：上传完成后表单里有「竖封面3:4」「横封面4:3」两个入口（`[class^="coverControl-"]`），打开的是同一个弹窗 `div.dy-creator-content-modal`，顶部切换「设置竖封面 / 设置横封面」。上传框要用 `.semi-upload:has(.semi-upload-drag-area-main-text)` 里的那个（左侧「生成参考图」还有一个）。切到横封面时抖音会先把竖封面同步过去，再上传会覆盖。点「完成」后弹窗消失即成功，随后抖音自动做「封面检测」。
- 没有移植上游的两个默认行为：自动勾选「内容由AI生成」声明、打开同步到其他平台开关（都是上游自己的业务需要）。
- 扫码登录调试经验：不要猜页面结构，先让程序在状态变化时记录整页截图 + 面板 HTML，再写选择器。

## 开发环境（非常重要）

开发机是 **VirtualBuddy 里的 macOS 虚拟机**，Docker Engine 在 **Mac 宿主机**上，通过 SSH Docker Context `mac-host` 访问。完整规则见用户提供的
`/Users/qiangzi/Desktop/VirtualBuddyShared/VM-share/VirtualBuddy_Claude_Remote_Docker_Guide.md`，开始 Docker 工作前先读。要点：

- **不要安装或重新配置 Docker**、SSH、Docker Context。Bash 里可能需要先 `export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"`。
- 第一次连接偶尔会报 `No route to host`，先重试，不要急着排障。
- 宿主机地址会随虚拟机网络变化：2026-11-02 起虚拟机改为 NAT（虚拟机 `192.168.64.6`，宿主机即网关 `192.168.64.1`），旧地址 `172.16.192.6` 已不可用。连不上时先看 `route -n get default` 的网关，并用 `ssh-keyscan` 核对主机密钥指纹与已知的一致，再**征得用户同意**后更新 `~/.ssh/config` 和 `docker context update mac-host`。
- 项目在共享目录：虚拟机路径 `/Users/qiangzi/Desktop/VirtualBuddyShared/VM-share/projects/matrix-publishing` = 宿主机路径 `/Users/qiangzi/VM-share/projects/matrix-publishing`。**运行时 bind mount 必须用宿主机路径**，由 `.env.docker-host` 的 `HOST_PROJECT_DIR` 提供。
- 端口发布在**宿主机**的 127.0.0.1 上，不在虚拟机里。虚拟机里访问前端要开 SSH 隧道（见下）。例外：前端端口按 `.env.docker-host` 的 `FRONTEND_BIND` 绑定，2026-11-03 起设为 `0.0.0.0`，局域网可以直接访问 `http://宿主机局域网IP:5173`（当时宿主机是 `172.19.4.171`，会随网络变）。
- 虚拟机系统时区是美国太平洋时间，比北京时间晚 15～16 小时。本文档和迁移文件名里的日期都按**北京时间**写，记录新日期时也按北京时间（`TZ=Asia/Shanghai date`）。
- 未经用户同意不要执行 `docker system prune`、`docker volume prune`、`docker compose down -v` 等清理操作。
- 国内网络：Docker Hub 直连会断，镜像走 `.env.docker-host` 里的 `IMAGE_MIRROR`（DaoCloud）。镜像站在构建时偶尔对基础镜像返回 401，先 `docker pull` 该镜像再构建。PyPI 用阿里云、npm 用 npmmirror、apt 用阿里云 https 并开了重试。

### 常用命令

在项目根目录执行，所有 compose 命令都要带 `--env-file .env.docker-host`：

```bash
docker compose --env-file .env.docker-host config        # 改 compose 后先核对 bind mount 的 source
docker compose --env-file .env.docker-host up -d --build
docker compose --env-file .env.docker-host ps
docker compose --env-file .env.docker-host logs -f browser-worker
docker compose --env-file .env.docker-host exec -T backend python -   # 跑测试脚本
docker compose --env-file .env.docker-host exec -T db psql -U matrix
```

- 源码热更新：backend 的 uvicorn `--reload`、两个 worker 的 `watchfiles`、前端 Vite 都开了轮询（VirtIOFS 文件事件不可靠），改代码一般不用重启。改了 `requirements*.txt`、Dockerfile 或 compose 才需要 `up -d --build`。browser-worker 镜像构建很慢（amd64 仿真 + 下载 Chrome），没必要别重建。
- 在虚拟机里打开前端：

  ```bash
  ssh -N -L 15173:127.0.0.1:5173 qiangzi@192.168.64.1
  ```

  然后访问 http://127.0.0.1:15173 。Vite 轮询偶尔会漏掉新改的文件（2026-11-03 遇到过，浏览器一直拿到旧代码），这时 `docker compose --env-file .env.docker-host restart frontend`。后端在宿主机 127.0.0.1:8000，测试 API 通常直接在 backend 容器里用 httpx 请求 `http://localhost:8000`。
- 在测试脚本里拿登录令牌：`app.security.create_access_token(user_id)`。

### 测试方式

目前没有自动化测试套件，验证方式是：

1. 在 backend 容器里用 httpx 脚本覆盖接口（正常流程 + 参数校验 + **跨租户访问返回 404**）。
2. 浏览器自动化相关逻辑：在 browser-worker 容器里写探查脚本，直接调用平台模块的内部函数（如 `channels._open_upload_page` / `_set_schedule`）**做到「点发表」之前为止**，截图到 `/data/debug/` 再 `docker cp` 出来查看。
3. 前端用浏览器面板通过 SSH 隧道实际点一遍。

开发库里的测试数据：

- 测试登录账号见 `README.md`（公司「演示公司」）。
- 该租户下有**用户本人的真实账号**：视频号 IamAdy（`accounts.id = 5`，2026-11-02 登录态已失效，需重新扫码）、抖音 IamAdy（`accounts.id = 6`，2026-11-03 检测有效），以及测试公众号 GoliveShowE（`accounts.id = 7`，模拟授权）。
- 其他租户（如 `tenant_id = 4`「客户A」）里是接口测试时建的假账号和内容，可用来验证跨租户隔离。
- 两条定时测试作品「平台测试请忽略」：视频号 2026-11-04 21:30、抖音 2026-11-05 21:30，已提醒用户到期前在平台后台手动删除（本平台还不支持删除/撤回）。
- 测试视频在 media 卷的 `/data/test/sample.mp4`（12 秒竖屏彩条）。

## 安全红线

- **不要擅自用真实账号发布、删除或修改平台上的内容**。会对外可见或不可撤销的操作（立即发布、删除作品等）必须先征得用户同意。用定时发表做测试相对安全，但也要告诉用户需要删除。
- 不要在聊天、日志或提交中输出 `.env` 里的密钥、平台 cookie / token 明文。
- `.env`、`.env.docker-host` 不提交。

## Git

- 主分支 `main`，没有配置远程仓库。只在用户要求时提交。
- 提交信息用中文：第一行概括，空一行后列要点；末尾按会话提示加 `Co-Authored-By`。

## 待办 / 下一步

### 待用户确认的问题

- 2026-11-02 下午用户是否自己登录过视频号助手？（确认视频号是否只允许一个网页登录，决定产品里要不要提示客户）
- 客户发的内容是否包含 AI 生成内容？（决定「AI 内容声明」是否列为上线必做）
- 下一步先做哪个：A. 把视频号/抖音补完整做成可试用；B. 先部署到服务器，再把公众号从本地模拟切到真实第三方平台。（2026-11-02 已向用户给出两个方向，尚未选择；之后先做了公众号本地联调和内容审核）

### 视频号 / 抖音：还要补的

上线前建议必做：

1. 两个平台的**立即发布**各用真实账号验证一次（需用户同意，会立刻公开）。
2. **自定义封面**：抖音竖/横封面已完成并实测（做到上传封面为止，未真实发布过）；视频号竖封面按上游选择器写好**未实测**（账号 5 登录态已失效，需用户重新扫码后验证）。视频号也有 4:3 横封面（「视频号动态」），还没做。
3. **AI 内容声明 / 自主声明**（抖音「自主声明」、视频号「视频标注」；若客户发 AI 内容则关系到平台合规）。不要照搬上游的强制勾选，做成发布时可选。
4. **登录失效主动通知客户**（现在只在账号列表标「需重新登录」）。
5. **视频格式预检查**（大小、时长、比例），不合规的提交时就拒绝。

可以上线后按需做：

- 视频号「声明原创」、可见范围、合集、位置、商品链接、背景音乐等发布选项。
- 图文（图集）发布。
- 在本平台撤回/删除已提交的定时作品；跟踪审核结果（审核中/通过/未通过）；同步播放等数据。
- 发布中的短信验证（抖音）尚未在真实发布中遇到，代码已写好未验证。
- 视频号「实名验证」弹窗目前直接报错，可改成把验证二维码推给客户。
- 登录态保活频率（现在每 6 小时）需观察实际失效时间后调整。
- 规模化：多 browser-worker、按账号代理 IP；平台改版监控（某平台连续发布失败时告警）。

### 部署（接公众号的前提）

- 生产 compose：不挂源码、Nginx + HTTPS、在 amd64 服务器上构建镜像（服务器上 Chrome 原生运行，比开发机仿真快）。
- 任务卡在 `running`（worker 崩溃）时的超时回收；数据库和 `CREDENTIALS_KEY` 备份。
- 需要用户提供：已备案域名（A 记录指向服务器固定 IP）、服务器 SSH 访问（放好公钥）。
- 部署后验证：抖音/视频号在服务器 IP 下的登录（可能再要求短信验证）、登录态保持时长。

### 微信公众号（第三方平台）

已完成（本地模拟）：授权全流程、授权事件接收（ticket、取消授权）、refresh_token 换 token、存草稿、发表（轮询 `freepublish/get` 拿文章链接，2026-11-03 实测通过）、图文编辑（`contenteditable` 简易编辑器，在内容管理的抽屉里）。
测试公众号 GoliveShowE 的 AppID/AppSecret 在 `.env`；2026-11-03 联调在它的草稿箱里留了 2 篇「平台测试请忽略」草稿，并经用户要求发表了 1 篇「矩阵平台发布测试」（发表不推送粉丝，但有链接即可访问），均已提醒用户在公众号后台删除。
还没做：授权方「消息与事件接收 URL」（`PUBLISHJOBFINISH` 发表结果推送）、多图文、富文本编辑器、正文外链图片处理、公众号未认证时的提示。

切到真实第三方平台（部署后）：
- 微信每 10 分钟往授权事件接收 URL 推 `component_verify_ticket`，这个 URL 需要公网 HTTPS + 已备案域名，所以只能部署后联调。
- 开放平台后台的开发配置（授权事件接收 URL、授权发起页域名、IP 白名单）要等域名确定后告诉用户填写；`.env` 填真实的 `WECHAT_COMPONENT_*`，关掉 `WECHAT_MP_MOCK`。
- 客户的公众号必须是**已认证的企业主体**才能调用发表接口。

### 快手

等权限批下来后接 OAuth 和三步上传。
