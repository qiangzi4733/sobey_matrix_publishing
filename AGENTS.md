# AGENTS.md

给接手本项目的 AI 编码助手（Claude Code 等）看的工作说明。用中文和用户沟通。

## 项目是什么

新媒体矩阵分发平台，**面向客户的多租户 SaaS**：

- 客户注册后成为一个租户（公司），在平台里管理自己名下的多个矩阵账号，一条内容可同时发到多个账号。
- 微信公众号、快手：客户**授权**自己的账号（官方 API）。
- 抖音、微信视频号：客户**扫码登录**，平台保存登录态并定期检测，失效后提醒重新扫码（浏览器自动化）。
- 公众号用「发表」（草稿 `draft/add` → `freepublish/submit`），**不是群发**。
- 部署目标：Ubuntu 20.04 云服务器（固定 IP），全部跑在 Docker Compose 里。

### 平台进度

| 平台 | 方式 | 状态 |
|---|---|---|
| 视频号 | 扫码登录 + Playwright（patchright + Google Chrome） | **已完成**：扫码登录、登录检测、发布、平台原生定时发表。定时发表已用真实账号验证；立即发布由用户自行测试 |
| 微信公众号 | 微信开放平台**第三方平台**（平台型）授权，用户的资质已申请下来 | 未开始 |
| 抖音 | 扫码登录 + 浏览器自动化，参考 social-auto-upload 的 `uploader/douyin_uploader` | 未开始 |
| 快手 | 快手开放平台 OAuth，scope `user_video_publish`，三步上传发布 | **等待权限审批，暂不做** |

## 架构

```
frontend (Vue3 + Element Plus, Vite)
   │ /api 代理
backend (FastAPI)  ── PostgreSQL（业务数据）
   │                └ Redis（Celery broker + 扫码登录会话）
   ├─ worker          Celery 默认队列 `celery`：定时分发、批量检测（以后公众号 API 发布也放这里）
   ├─ browser-worker  Celery `browser` 队列：扫码登录、登录检测、视频号/抖音发布（amd64 + Chrome）
   └─ beat            每分钟分发到点的定时任务；每 6 小时检测扫码类账号
```

关键文件：

- `backend/app/models.py`：`Tenant` / `User` / `Account`（矩阵账号，凭证加密存 `credentials_encrypted`）/ `Post`（一次发布的内容）/ `PublishTask`（每个账号一条）。
- `backend/app/tasks.py`：所有 Celery 任务；`PUBLISHABLE`、`BROWSER_PLATFORMS` 控制平台能力；`enqueue_publish` 按平台选队列。
- `backend/app/platforms/`：每个平台一个模块。`base.py` 定义 `LoginExpired` / `PublishError(message, screenshot)`；`scheduling.py` 定义哪些平台用**平台原生定时**；`channels.py` 是视频号实现。
- `backend/app/login_sessions.py`：扫码登录会话（Redis，15 分钟过期），worker 写二维码和进度，前端每 2 秒轮询。
- `backend/app/routers/`：`auth`（注册/登录/JWT）、`accounts`（账号、扫码登录、检测）、`posts`（上传视频创建发布、任务列表、重试、失败截图）。
- `frontend/src/platforms.js`：前端的平台名称和能力列表，接入新平台时同步修改。

### 必须遵守的设计约定

- **租户隔离**：所有查询都按 `user.tenant_id` 过滤；访问其他租户的资源一律返回 404，不要返回 403（避免泄露存在性）。
- **凭证**：平台 token / cookie 一律用 `app.security.encrypt_credentials` 加密后存库，不落明文文件。扫码类平台存 `{"storage_state": ...}`。`CREDENTIALS_KEY` 丢失后所有账号需重新授权。
- **浏览器依赖隔离**：`patchright` 只装在 browser-worker 镜像里。平台模块（如 `channels.py`）只能在任务函数**内部**导入；backend 需要用到的规则（如定时范围）放到不依赖浏览器的模块（如 `scheduling.py`）。
- **发布不可重复**：`run_publish_task` 用 `acks_late=False`，并用 `UPDATE ... WHERE status='queued'` 抢占任务。宁可漏发不可重发。
- **定时发布两种模式**：`scheduling.NATIVE_SCHEDULE` 里的平台在提交时就把定时时间交给平台（视频号：10 分钟后～30 天内，北京时间）；其他平台建任务时状态为 `scheduled`，由 beat 到点改为 `queued`。不要用 Celery 的 `eta` 做长延时（Redis visibility timeout 会导致重复投递）。
- **平台模块的写法**（参考 `channels.py`）：
  - 用同步 API（`patchright.sync_api`），登录态作为 dict 传入/传出；
  - 发布、检测成功后返回刷新后的 `storage_state`，由任务写回数据库；
  - 登录失效抛 `LoginExpired`，可预期的失败抛 `PublishError` 并附 `_screenshot(...)` 现场截图；
  - 页面选择器写明实测日期，平台改版时最先坏的就是这里。
- 数据库表目前由 `Base.metadata.create_all` 在启动时创建，**不会修改已有表**。改已有表的字段前，先引入 Alembic（这是待办），不要手改生产库。
- 代码风格：中文注释，只写「为什么」；跟随周围代码的命名和写法；不加无用的抽象。

### 已踩过的坑（视频号，2026-11 实测）

- 视频号上传必须用 **Google Chrome**（Chromium 不支持 H.264）。Chrome 只有 linux/amd64，所以 browser-worker 固定 `platform: linux/amd64`，在 Apple Silicon 开发机上走仿真，速度偏慢（扫码登录全程约 85 秒，发布约 75 秒）。
- 登录二维码在 `open.weixin.qq.com/connect/qrconnect` 的 iframe 里，可见的是 `img.web_qrcode_img`，同一 iframe 里还有一个**隐藏的** `img.qrcode`，必须按 `:visible` 过滤。
- 登录后账号信息从 `auth/auth_data` 接口响应的 `data.finderUser`（`nickname` / `uniqId` / `headImgUrl`）获取，以 `uniqId`（`sph...`）作为 `external_id` 去重。
- 不能直接打开 `/platform/post/create`（表单不挂载），要先进 `/platform` 首页再点「发表视频」。
- 定时发表日历会停在上次查看的月份，需要能前后翻；超过 30 天的日期是 disabled。
- 微信头像有防盗链，前端 `<img>` 要加 `referrerpolicy="no-referrer"`。
- 视频号流程移植自 social-auto-upload（MIT），见 `THIRD_PARTY_NOTICES.md`。上游源码可 `git clone --depth 1 https://github.com/dreammis/social-auto-upload` 到临时目录**只读参考**，不要整体引入为依赖（它在重构，且依赖全局配置和 cookie 文件）。

## 开发环境（非常重要）

开发机是 **VirtualBuddy 里的 macOS 虚拟机**，Docker Engine 在 **Mac 宿主机**上，通过 SSH Docker Context `mac-host` 访问。完整规则见用户提供的
`/Users/qiangzi/Desktop/VirtualBuddyShared/VM-share/VirtualBuddy_Claude_Remote_Docker_Guide.md`，开始 Docker 工作前先读。要点：

- **不要安装或重新配置 Docker**、SSH、Docker Context。Bash 里可能需要先 `export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"`。
- 第一次连接偶尔会报 `No route to host`，先重试，不要急着排障。
- 项目在共享目录：虚拟机路径 `/Users/qiangzi/Desktop/VirtualBuddyShared/VM-share/projects/matrix-publishing` = 宿主机路径 `/Users/qiangzi/VM-share/projects/matrix-publishing`。**运行时 bind mount 必须用宿主机路径**，由 `.env.docker-host` 的 `HOST_PROJECT_DIR` 提供。
- 端口发布在**宿主机**的 127.0.0.1 上，不在虚拟机里。虚拟机里访问前端要开 SSH 隧道（见下）。
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
  ssh -N -L 15173:127.0.0.1:5173 qiangzi@172.16.192.6
  ```

  然后访问 http://127.0.0.1:15173 。后端在宿主机 127.0.0.1:8000，测试 API 通常直接在 backend 容器里用 httpx 请求 `http://localhost:8000`。
- 在测试脚本里拿登录令牌：`app.security.create_access_token(user_id)`。

### 测试方式

目前没有自动化测试套件，验证方式是：

1. 在 backend 容器里用 httpx 脚本覆盖接口（正常流程 + 参数校验 + **跨租户访问返回 404**）。
2. 浏览器自动化相关逻辑：在 browser-worker 容器里写探查脚本，直接调用平台模块的内部函数（如 `channels._open_upload_page` / `_set_schedule`）**做到「点发表」之前为止**，截图到 `/data/debug/` 再 `docker cp` 出来查看。
3. 前端用浏览器面板通过 SSH 隧道实际点一遍。

开发库里的测试数据：

- 测试登录账号见 `README.md`（公司「演示公司」）。
- 该租户下有一个**用户本人的真实视频号账号**（IamAdy，`accounts.id = 5`），登录态有效。
- 测试视频在 media 卷的 `/data/test/sample.mp4`（12 秒竖屏彩条）。

## 安全红线

- **不要擅自用真实账号发布、删除或修改平台上的内容**。会对外可见或不可撤销的操作（立即发布、删除作品等）必须先征得用户同意。用定时发表做测试相对安全，但也要告诉用户需要删除。
- 不要在聊天、日志或提交中输出 `.env` 里的密钥、平台 cookie / token 明文。
- `.env`、`.env.docker-host` 不提交。

## Git

- 主分支 `main`，没有配置远程仓库。只在用户要求时提交。
- 提交信息用中文：第一行概括，空一行后列要点；末尾按会话提示加 `Co-Authored-By`。

## 待办 / 下一步

1. **微信公众号（第三方平台）**：接收 `component_verify_ticket`（授权事件接收 URL，需要公网 HTTPS + 已备案域名，本地开发需要部署或内网穿透）、`component_access_token`、预授权码与授权回调、`authorizer_refresh_token` 刷新；发表流程：上传正文图片（`uploadimg`）和封面（永久素材）→ `draft/add` → `freepublish/submit` → 结果通过事件推送或 `freepublish/get` 确认。客户的公众号必须是**已认证的企业主体**才能调用发表接口。需要新的「图文」内容类型，`Post` 目前只有视频字段。
2. **抖音**：参照 `channels.py` 的模式实现扫码登录、检测、发布；把 `Platform.douyin` 加入 `accounts.LOGIN_TASKS`、`tasks.PUBLISHABLE`、`check_account`，以及前端 `platforms.js`。
3. **快手**：等权限批下来后接 OAuth 和三步上传。
4. 基础设施：引入 Alembic；任务卡在 `running`（worker 崩溃）时的超时回收；视频号「实名验证」弹窗目前直接报错，以后可以把验证二维码推给客户；生产部署用的 compose（不挂源码、Nginx + HTTPS、在 amd64 服务器上构建镜像）。
