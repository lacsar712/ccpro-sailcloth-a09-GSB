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
| `worker` | `123456` | 操作工 |

登录页已预填 `admin` / `123456`。后端 entrypoint 执行 migrate + seed。

## 业务规则

1. 布卷状态不可设为「已固化」（`cured`），除非该卷**最近一条** `DipRun` 的 `cureHours` 已记录且 **≥ 12**。口令牌不参与固化判定。
2. 布卷改为「浸渍中」（`dipping`）前，其所属帆布间必须持有一张**覆盖当前时刻、未作废**的口令牌（`PassToken`）；否则返回中文 400 挡住，前端原样提示。
3. 口令牌失效时刻必须晚于生效时刻；同一帆布间不允许两张**未作废且时段重叠**的口令（端点相接不算重叠）；事务内行锁 + 复查保证两名管理员交叉签发时只许一张入库。
4. 口令牌签发与作废**仅管理员**；任何登录用户可查看。

规则实现：`backend/core/rules.py`、`backend/core/models.py::PassToken`。

## 快速启动

```bash
cd d:\work\document\bytecode\claudeCodePro\SailCloth\SailCloth-01
docker compose up --build
```

浏览器打开 http://localhost:3740

## SPA 信息架构

- **登录** → 进入主工作面
- **`/` 帆布间晾晒架（主）**：按帆布间挂布卷芯片（挂签状态 `raw` / `dipping` / `cured`）；点击打开右侧面板登记 `DipRun`、切换状态；架下为浸渍流水次要信息流
- **`/tokens` 口令牌（主）**：有效/未作废/全部列表、管理员签发与作废；改浸渍中被挡时按此页口令为准
- **`/rolls` · `/dips`（次要台账）**：保留列表/表单 CRUD，侧栏降级为「台账」入口，非主路径

API 契约：JWT，`/api/lofts|rolls|dips|dashboard/`；新增 `/api/pass-tokens/`（GET 列表，支持 `?state=active|valid`、`?loftId=`；POST 签发，管理员）与 `/api/pass-tokens/{id}/revoke/`（POST 作废，管理员）。

## 配色

海军蓝（navy）+ 帆布米色（canvas），与温室绿主题区分。
