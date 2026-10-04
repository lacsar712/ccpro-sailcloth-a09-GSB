# SailCloth-01 · 帆布浸渍防水台

帆布间布卷与浸渍固化台账基线项目（Django 5 + DRF + Vue 3 SPA）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Django 5 · DRF · SimpleJWT · django-cors-headers · Gunicorn |
| 前端 | Vue 3 · Vite · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 |
| 部署 | Docker Compose · Nginx（前端反代 `/api`） |

## 路径与端口

- **项目路径**：`d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01`
- **前端**：http://localhost:3740
- **API**：http://localhost:8740
- **PostgreSQL**：localhost:6140

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 管理员 |
| `admin2` | `123456` | 管理员（第二名值班，用于交叉签发） |
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。种子含一间帆布间、三卷布卷（原布 / 浸渍中 / 已固化），以及一张**已过期、未作废**的口令牌。

## 业务规则

- **浸渍口令牌**：布卷改标「浸渍中」（`dipping`）前，其所属帆布间必须存在一张**覆盖当前时刻、未作废**的口令牌；否则服务端以中文 400 拒绝。
- 口令牌字段：帆布间、口令明文、生效时刻、失效时刻、签发人、作废时刻（可空）。失效时刻必须晚于生效时刻；同一帆布间**未作废且时段重叠**的口令不得有两张（数据库排他约束兜底，并发交叉签发也只入库一张）。
- 仅管理员（`role=admin`）可**签发**与**作废**口令牌；任何登录用户可查看。
- 布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。固化只认时长，口令不参与固化判定。

规则实现：`backend/core/rules.py`、口令牌模型 `PassphraseToken`（含 `btree_gist` 部分排他约束，迁移 `0002_passphrasetoken.py`）。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换状态；改「浸渍中」由服务端按口令牌把关，面板只显示中文拦截，不另开口令绿灯；架下为浸渍流水次要信息流
- **`/tokens` 口令牌（主）**：当前有效口令列表、全部口令牌（生效中 / 未生效 / 已过期 / 已作废）、管理员签发与作废
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API：JWT、`/api/lofts|rolls|dips|tokens|dashboard/`；签发 `POST /api/tokens/`、作废 `POST /api/tokens/{id}/revoke/`、有效牌 `GET /api/tokens/?active=1`（可叠加 `loftId`）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
