# 新媒体矩阵分发平台

面向客户的多租户 SaaS：客户授权自己的微信公众号、快手号，扫码登录抖音、视频号，统一管理并分发内容。

客户只需用浏览器访问本网站。抖音、视频号由**服务器上的无窗口 Chrome** 替所有客户登录和发布（登录态加密保存在服务器），公众号、快手走官方 API。

| 平台 | 接入方式 | 状态 |
|---|---|---|
| 视频号 | 扫码登录 + 浏览器自动化（Chrome） | 核心链路已跑通：扫码登录、登录检测、发布、定时发表；封面、AI 声明等待补 |
| 微信公众号 | 微信开放平台第三方平台授权，草稿 + 发表（非群发） | 本地已跑通：开放平台一侧用模拟服务代替，存草稿、发表走真实接口；接真实第三方平台要等域名和部署 |
| 抖音 | 扫码登录 + 浏览器自动化（Chrome） | 核心链路已跑通：扫码登录（含短信验证）、登录检测、发布、定时发布；封面、AI 声明等待补 |
| 快手 | 快手开放平台 OAuth（`user_video_publish`） | 等待权限审批 |

主要功能：

- **账号管理**：授权 / 扫码添加矩阵账号，定期检测登录状态，失效时提醒重新登录。
- **内容管理**：发布视频（视频号、抖音）和图文（公众号），一条内容发一个账号。提交后先审核，通过后手动点「发布」；支持定时发布、修改、退回、复制到其他账号；内容可以按多级分类归档和筛选。
- **发布记录**：查看每次发布的状态，失败可看现场截图、重试；平台要求短信验证码时在这里输入。

运行方式与约束、开发约定、环境注意事项、待办和待确认的问题见 [AGENTS.md](AGENTS.md)。

## 目录

- `backend/`：FastAPI + SQLAlchemy + Celery
- `frontend/`：Vue 3 + Element Plus（Vite）
- `compose.yaml`：开发环境（PostgreSQL、Redis、backend、worker、browser-worker、beat、frontend）

## 本地开发（VirtualBuddy 虚拟机 + 宿主机 Docker）

Docker Engine 跑在 Mac 宿主机上，源码挂载必须用宿主机路径。两个本机文件不提交：

- `.env.docker-host`：`HOST_PROJECT_DIR`（宿主机上的项目路径）和可选的 `IMAGE_MIRROR`（镜像站前缀，例如 `docker.m.daocloud.io/library/`）
- `.env`：应用配置，从 `.env.example` 复制后填写

```bash
docker compose --env-file .env.docker-host config   # 先核对挂载路径
docker compose --env-file .env.docker-host up -d --build
docker compose --env-file .env.docker-host logs -f backend
```

如果镜像站在构建时返回 401，先单独 `docker pull` 对应的基础镜像再构建。

端口只绑定在宿主机的 127.0.0.1：前端 5173、后端 8000。在虚拟机里访问前端需要开 SSH 隧道：

```bash
ssh -N -L 15173:127.0.0.1:5173 qiangzi@192.168.64.1
```

然后打开 http://127.0.0.1:15173 。

开发库里已有一个测试账号：`demo-ui@example.com` / `demopass123`（公司"演示公司"）。

## 说明

- 数据库用 Alembic 迁移，backend 启动时自动升级到最新版本（见 AGENTS.md）。
- 公众号联调：`.env` 里设 `WECHAT_MP_MOCK=true` 并填一个已认证测试公众号的 AppID/AppSecret，平台会在本地模拟微信开放平台（见 `.env.example`）。**生产必须关闭。**
- 平台凭证用 `CREDENTIALS_KEY`（Fernet）加密存储，生产环境必须单独生成并妥善保管，丢失后已授权账号需全部重新授权。
- 开发机是 arm64，生产服务器（Ubuntu 20.04）大概率是 amd64，部署时在服务器上构建镜像。
