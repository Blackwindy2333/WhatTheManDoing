# WhatTheManDoing · 在干什么

**服务端**项目：在本机监控前台应用，并通过**标准化 JSON API** 供客户端查询。  
本地 GUI 控制台属于服务端管理界面（配置 / 启停 / 托盘保活 / 限流）。  
**客户端**（网页、桌面、移动端、脚本）只消费 API，详见 **[docs/API.md](docs/API.md)**。

```text
┌──────────────── 服务端（本仓库） ────────────────┐
│  GUI 控制台 · 监控采集 · JSON API · 全局 RPM 限流  │
└──────────────────────┬───────────────────────────┘
                       │ HTTPS / HTTP + JSON
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       网页客户端    移动端       脚本 / 其它 Agent
```

## 功能一览

| 能力 | 说明 |
|------|------|
| 前台应用监控 | 进程名 + 友好显示名；窗口标题**默认关闭** |
| 标准化 JSON API | 统一 envelope `{code,message,data}`，见 `docs/API.md` |
| 本机状态查询 | `GET /api/v1/status` 返回当前前台应用 |
| 全局限流 | 每分钟最大请求数，**GUI 可改**（默认 120） |
| 本地控制台 GUI | 配置、启停服务、实时状态、开机自启、托盘保活 |
| 多设备列表 | `GET /api/v1/devices` 等（可选上报） |
| 在线/离线 | 超过 `offline_after_seconds` 未上报视为离线 |
| 最近切换 | `GET /api/v1/status/history` |
| 隐私暂停 / 黑名单 | 本地脱敏后才进入 API |
| 可选只读 Token | `viewer_token` 非空时查询需 Bearer |
| 配置持久化 | 缺失则默认创建；配置 JSON 入库 |
| 开机自动启动 | HKCU Run，登录后打开控制台 |

## 目录结构

```text
agent/          监控采集 + 本地控制台 GUI（服务端组成）
  gui/          Apple 风控制面板（配置 / 启停 / 托盘 / 限流）
server/         JSON API 服务（envelope + 全局 RPM + SQLite）
web/            示例客户端（只读查看页，非服务端核心）
docs/API.md     客户端 API 详档 ★
docs/android-feasibility.md
PLAN.md
```

## API 标准（摘要）

完整约定见 **[docs/API.md](docs/API.md)**。要点：

1. **统一 envelope**：`{"code":0,"message":"ok","data":...}`，错误同样结构  
2. **`code`**：`0` 成功；`4xxxx` 客户端错误；`5xxxx` 服务端错误  
3. **限流**：全局 RPM，响应头 `X-RateLimit-*`，拒绝时 HTTP 429 + `code=42900`  
4. **本机状态**：`GET /api/v1/status`  

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康与限流额度 |
| GET | `/api/v1/status` | **本机当前前台应用** |
| GET | `/api/v1/status/history` | 最近切换 |
| POST | `/api/v1/report` | 设备上报（可选） |
| GET | `/api/v1/devices` | 设备列表（可选） |
| GET | `/api/v1/devices/{id}` | 单设备 |
| GET | `/api/v1/devices/{id}/history` | 设备历史 |

## 环境要求

- Windows 10/11（Agent 采集前台窗口）
- Python 3.10+（推荐 3.12）
- 后端依赖：`pip install -r requirements.txt`（或使用已含 FastAPI/uvicorn/pytest 的环境）

验证测试（**不要**在开发中期启动应用联调，仅用 pytest）：

```bash
python -m pytest
```

## 快速开始

### 1. 启动后端

```bash
python -m server.app.main
# 默认监听 http://127.0.0.1:8765
```

首次运行会创建/读取 `server/config.json`（缺失则写入默认值）。

### 2. 启动 Windows Agent

**推荐：本地控制台 GUI（配置 / 启停 / 实时状态 / 开机自启）**

```bash
python -m agent.gui
```

界面说明（Apple 风）：

| 区域 | 作用 |
|------|------|
| 顶部状态胶囊 | 已停止 / 运行中 / 已暂停 / 设置已保存 |
| 实时状态卡片 | 当前前台应用、进程名、成功/失败计数、最近错误 |
| 设备与连接 | `device_id`、名称、API 地址、Token、采样间隔、**API 限流（次/分钟）** |
| 隐私 | 窗口标题开关、隐私暂停、进程黑名单 |
| 底部按钮 | **启动服务** / **停止** / **保存设置** |
| 开机自动启动 | 写入 `HKCU\...\Run`，登录后自动打开控制台 |
| 关闭按钮 | 询问：**最小化到托盘**（后台保活）/ **直接退出** / 取消 |
| 系统托盘 | 左键打开主页面；右键菜单：打开主页面 / 重启服务 / 退出 |

设置写回 `agent/config.json`；网页端仍为**只读**，无法修改上述隐私项。

也可用命令行 Agent（无界面）：

```bash
python -m agent.main
# 只采样一帧：
python -m agent.main --once
# 指定配置路径：
python -m agent.main --config path\to\agent\config.json
```

首次运行会创建/读取 `agent/config.json`。

### 3. 打开只读网页

用任意静态服务器托管 `web/`，例如：

```bash
python -m http.server 8080 --directory web
```

浏览器打开 `http://127.0.0.1:8080/`。  
部署到服务器时，只需修改 `web/config.json` 指向你的后端 API。

## 配置说明

配置文件**会**保存在仓库中（有意不进 `.gitignore`），便于持久化与同步。  
**请把生产环境的真实 token 换掉，不要把真实密钥提交到公开仓库。**

### `agent/config.json`

| 字段 | 默认 | 说明 |
|------|------|------|
| `api_base_url` | `http://127.0.0.1:8765/api/v1` | 后端 API 根地址 |
| `device_id` | `my-pc` | 设备唯一 ID |
| `device_name` | `My PC` | 网页展示名 |
| `device_token` | `change-me` | 与后端 `agent_tokens[device_id]` 一致 |
| `poll_interval_ms` | `1000` | 采样间隔（≥100） |
| `report_window_title` | `false` | **是否上报窗口标题（隐私）** |
| `app_name_blacklist` | `[]` | 本地脱敏列表，如 `["KeePass.exe"]` |
| `history_limit` | `50` | 建议历史条数提示 |
| `privacy_pause` | `false` | `true` 时上报 status=paused，不带应用信息 |
| `display_name_map` | 内置常见映射 | 进程名 → 友好名 |

### `server/config.json`

| 字段 | 默认 | 说明 |
|------|------|------|
| `host` / `port` | `127.0.0.1` / `8765` | 监听地址 |
| `db_path` | `server/data/monitor.db` | SQLite 路径（**不**入库） |
| `viewer_token` | `""` | 空=公开只读；非空则网页需 Bearer |
| `agent_tokens` | `{"my-pc":"change-me"}` | 每台设备的上报 token |
| `offline_after_seconds` | `30` | 超时判离线 |
| `history_limit` | `50` | 查询历史上限相关 |
| `cors_origins` | `["*"]` | 网页跨域来源 |
| `rate_limit_per_minute` | `120` | **全局**每分钟最大请求数（GUI 可改） |

### `web/config.json`（部署到服务器时主要改这里）

| 字段 | 默认 | 说明 |
|------|------|------|
| `apiBaseUrl` | `http://127.0.0.1:8765/api/v1` | 后端 API |
| `viewerToken` | `""` | 与后端 `viewer_token` 对应 |
| `refreshMode` | `"poll"` | `poll` 或 `websocket`（失败会回退轮询） |
| `pollIntervalMs` | `3000` | 轮询间隔 |
| `showWindowTitle` | `false` | 展示层是否显示标题（后端默认已剥离标题） |

## API 文档

请阅读 **[docs/API.md](docs/API.md)**（鉴权、端点、字段、限流、错误码、curl / JS / Python 示例）。  
以下为历史端点索引（均返回 envelope）：

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| `POST` | `/api/v1/report` | Agent Bearer `device_token` | 设备上报（唯一写入口） |
| `GET` | `/api/v1/health` | 无 | 健康检查 |
| `GET` | `/api/v1/devices` | Viewer（若配置） | 设备列表 |
| `GET` | `/api/v1/devices/{id}` | Viewer（若配置） | 单设备状态 |
| `GET` | `/api/v1/devices/{id}/history` | Viewer（若配置） | 最近历史 |
| `WS` | `/api/v1/ws` | Viewer（若配置） | 实时推送 |

Viewer **没有**任何修改配置或控制设备的接口。

上报体示例：

```json
{
  "device_id": "my-pc",
  "device_name": "My PC",
  "status": "active",
  "timestamp": "2026-01-01T12:00:00Z",
  "app": {
    "process_name": "Code.exe",
    "display_name": "Visual Studio Code",
    "window_title": null
  }
}
```

## 隐私与安全

1. **窗口标题默认不上报**；即使开启，Viewer API 仍默认剥离标题。  
2. **黑名单**与**隐私暂停**在 Agent 本地完成，后端无法还原被脱敏内容。  
3. 网页为**只读**，不能改 token、黑名单、标题开关等；**本地 GUI 控制台**仅供设备所有者使用。  
4. 配置入库便于你管理设置；生产环境请更换 `device_token` / `viewer_token`，避免公开仓库泄露。  
5. 建议生产部署：反向代理 + HTTPS，限制 `cors_origins`，`viewer_token` 使用长随机串。

## 部署到服务器（网页）

1. 上传 `web/` 目录到任意静态托管（Nginx / 对象存储 / Pages）。  
2. 编辑服务器上的 `web/config.json`：  
   - `apiBaseUrl` → `https://your-domain/api/v1`  
   - `viewerToken` → 若后端设置了 token  
3. 后端用 systemd / nssm / 容器常驻：`python -m server.app.main`  
4. 反代示例（Nginx）：把 `/api/` 转到 `127.0.0.1:8765`，静态托管 `web/`。

## 日志

应用使用统一模块 `logconfig.py`，日志目录 **`logs/`**（滚动：2MB × 5 份）：

| 文件 | 来源 |
|------|------|
| `logs/gui.log` | 本地控制台 |
| `logs/agent.log` | 命令行 Agent |
| `logs/server.log` | API 服务 |

内容包括：启动/停止、设置保存、上报成功/失败**具体原因**（连接拒绝、401 Token、429 限流、超时等）。  
GUI 页脚会显示当前日志文件路径。

**关于「最近错误：report failed」**  
常见原因是**尚未启动 API 服务**（`python -m server.app.main`），Agent 无法 POST 到 `api_base_url`。  
现在会显示可操作的错误文案（如「无法连接服务端…请确认已启动 API 服务」），并写入日志。

## 测试

```bash
python -m pytest
```

覆盖：配置默认创建与校验、隐私字段（标题/黑名单/暂停）、存储历史、API 鉴权与只读约束、GUI 表单映射与服务启停、开机自启（mock 注册表）、托盘菜单与关闭对话框。  
Win32 真实调用与 GUI 主循环不在单元测试中启动，仅测纯逻辑与注入缝。

## 安卓端

见 **[docs/android-feasibility.md](docs/android-feasibility.md)**（权限矩阵、协议对齐、复杂度 4–8 人日、侧载限制）。  
本仓库**不包含** Android 实现。

## 故障排查

| 现象 | 处理 |
|------|------|
| 网页一直「连接失败」 | 检查 `apiBaseUrl`、后端是否启动、CORS |
| 401 | 核对 `device_token` ↔ `agent_tokens`，或 `viewerToken` |
| 网页无设备 | Agent/GUI 服务是否在跑、`device_id` 是否注册到 `agent_tokens` |
| 标题不显示 | `report_window_title=false`（默认）或后端剥离 |
| 想临时不分享 | GUI 打开「隐私暂停」，或配置 `privacy_pause: true` |
| 开机启动未生效 | 确认注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 中 `WhatTheManDoingAgent`；或重新打开 GUI 中的开关 |
| GUI 字体/配色异常 | 跟随系统浅色/深色（`AppsUseLightTheme`）；高对比度下组件会自动偏实心 |
| GUI 高分屏字体模糊 | 已内置 Per-Monitor DPI 感知（`agent/gui/dpi.py`）；请用 `python -m agent.gui` 启动。若仍模糊，确认系统缩放与显卡缩放一致，不要用兼容模式运行 |
| **最近错误：无法连接服务端 / report failed** | **未先启动 API 服务**。请运行 `python -m server.app.main` 后再启动监控。也请核对 `api_base_url`。详细原因见 `logs/gui.log` / `logs/agent.log` |
| **最近错误：鉴权失败 (401)** | Agent 的 `device_token` 与 `server/config.json` 中 `agent_tokens[device_id]` 不一致 |
| 日志在哪 | 项目根目录 `logs/`：`gui.log`、`agent.log`、`server.log`（滚动 2MB×5） |
| 关闭后仍在后台 | 点了「最小化到托盘」。托盘右键 → 退出，或托盘打开主页面后再选直接退出 |
| 找不到托盘图标 | 看任务栏溢出区（`^`）；确认系统托盘未隐藏该图标 |

## 许可

MIT，见 [LICENSE](LICENSE)。
