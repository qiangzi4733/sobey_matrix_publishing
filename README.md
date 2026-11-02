# 新媒体矩阵分发平台

面向客户的多租户 SaaS：客户授权自己的微信公众号、快手号，扫码登录抖音、视频号，统一管理并分发内容。

| 平台 | 接入方式 | 状态 |
|---|---|---|
| 视频号 | 扫码登录 + 浏览器自动化（Chrome） | 已完成：扫码登录、登录检测、发布、定时发表 |
| 微信公众号 | 微信开放平台第三方平台授权，草稿 + 发表（非群发） | 待开发 |
| 抖音 | 扫码登录 + 浏览器自动化 | 待开发 |
| 快手 | 快手开放平台 OAuth（`user_video_publish`） | 等待权限审批 |

开发约定、环境注意事项和待办见 [AGENTS.md](AGENTS.md)。

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
ssh -N -L 15173:127.0.0.1:5173 qiangzi@172.16.192.6
```

然后打开 http://127.0.0.1:15173 。

开发库里已有一个测试账号：`demo-ui@example.com` / `demopass123`（公司"演示公司"）。

## 说明

- 数据库表目前在启动时自动创建；模型稳定后改用 Alembic 迁移。
- 平台凭证用 `CREDENTIALS_KEY`（Fernet）加密存储，生产环境必须单独生成并妥善保管，丢失后已授权账号需全部重新授权。
- 开发机是 arm64，生产服务器（Ubuntu 20.04）大概率是 amd64，部署时在服务器上构建镜像。
