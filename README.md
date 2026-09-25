# WhatTheManDoing · 在干什么

监控本机（Windows）**当前前台应用**，并提供一个**只读网页**，让其他人看到「他现在在干什么」。  
前后端分离：网页可部署到任意静态服务器，通过 `web/config.json` 连接后端。  
**网页只能查看，不能修改任何涉及隐私的配置。**

```text
Windows Agent（含本地 GUI 控制台）──上报──► Backend (FastAPI) ◄──只读── Web Viewer（可独立部署）
Android（仅可行性报告，见 docs/android-feasibility.md）
```

## 功能一览

| 能力 | 说明 |
|------|------|
| 前台应用监控 | 进程名 + 友好显示名；窗口标题**默认关闭** |
| 本地控制台 GUI | Apple 风界面：配置、启停服务、实时状态、开机自启 |
| 多设备列表 | 网页展示多台设备的在线状态与当前应用 |
| 在线/离线 | 超过 `offline_after_seconds` 未上报视为离线 |
| 最近切换 | 每设备保留最近历史（可配置上限） |
| 隐私暂停 | Agent 本地 `privacy_pause`，网页只显示「已暂停」 |
| 进程黑名单 | 本地不上报指定进程，显示为 Redacted |
| 可选只读 Token | 后端 `viewer_token` 非空时，网页需带 Token |
| 配置持久化 | 启动检测配置，缺失则以默认设置创建并写回 |
| 开机自动启动 | 写入 HKCU Run，登录后打开本地控制台 |

## 目录结构

```text
agent/          Windows 监控客户端 + 本地控制台 GUI（纯标准库）
  gui/          Apple 风控制面板（配置 / 启停 / 状态 / 自启）
server/         FastAPI 后端 + SQLite
web/            只读查看页（静态，可独立部署）
docs/           安卓端可行性报告等
tests/          见 agent/tests、server/tests（pytest）
PLAN.md         可行性研究与实施计划
```

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
| 设备与连接 | `device_id`、名称、API 地址、Token、采样间隔 |
| 隐私 | 窗口标题开关、隐私暂停、进程黑名单 |
| 底部按钮 | **启动服务** / **停止** / **保存设置** |
| 开机自动启动 | 写入 `HKCU\...\Run`，登录后自动打开控制台 |

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

### `web/config.json`（部署到服务器时主要改这里）

| 字段 | 默认 | 说明 |
|------|------|------|
| `apiBaseUrl` | `http://127.0.0.1:8765/api/v1` | 后端 API |
| `viewerToken` | `""` | 与后端 `viewer_token` 对应 |
| `refreshMode` | `"poll"` | `poll` 或 `websocket`（失败会回退轮询） |
| `pollIntervalMs` | `3000` | 轮询间隔 |
| `showWindowTitle` | `false` | 展示层是否显示标题（后端默认已剥离标题） |

## API（只读）

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

## 测试

```bash
python -m pytest
```

覆盖：配置默认创建与校验、隐私字段（标题/黑名单/暂停）、存储历史、API 鉴权与只读约束、GUI 表单映射与服务启停、开机自启（mock 注册表）。  
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

## 许可

MIT，见 [LICENSE](LICENSE)。
