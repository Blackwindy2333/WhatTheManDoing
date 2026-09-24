# WhatTheManDoing — 可行性研究与实施计划

> 状态：**研究阶段（未写业务代码）**。Browser Use/IAB 与外网文档抓取本次不可用，以下结论基于稳定的 Win32 / Android 公开 API 能力（长期一致，非易变特性）。

---

## 1. 目标拆解

| 目标 | 说明 | 本迭代范围 |
|------|------|-----------|
| Windows 端监控 | 轮询/钩子读取前台应用（进程名 + 可选窗口标题） | **必须实现** |
| 后端 | 接收上报、存储状态/历史、向网页提供只读 API | **必须实现** |
| 网页查看端 | 部署到任意静态服务器，通过配置连后端；**只读** | **必须实现** |
| 安卓端 | 研究可行性与权限模型 | **调研报告**（是否落地待确认） |
| 配置持久化 | 启动检测配置，缺失则写默认；配置**不**进 `.gitignore` | **必须实现** |
| 提交规范 | 每个文件编辑完成后 `feat./fix./bug.…` 提交 | **全程遵守** |
| 测试 | 全部代码完成前仅 pytest，不启动应用做联调 | **全程遵守** |

隐私边界：网页**不能**修改任何涉及隐私的配置；只能展示“在干什么”。

---

## 2. 推荐总体架构

```text
┌──────────────────┐  HTTPS POST/WS   ┌────────────────────┐  HTTPS GET/WS  ┌─────────────────┐
│  Windows Agent   │ ───────────────► │      Backend       │ ◄───────────── │  Web Viewer     │
│  (本机监控)       │   设备身份+心跳   │  FastAPI + SQLite  │   只读 API      │  (可独立部署)    │
└──────────────────┘                  │  /api/devices/...  │                │  config.json    │
┌──────────────────┐                  └────────────────────┘                └─────────────────┘
│  Android Agent   │  （调研/可选）           │
│  Accessibility / │ ────────────────────────┘
│  UsageStats      │
└──────────────────┘
```

- **前后端分离**：Viewer 为纯静态站（`index.html` + css/js），任意静态托管（Nginx / GitHub Pages / 对象存储）均可；仅改 `config.json` 中的 `apiBaseUrl` 等即可指向不同后端。
- **Agent 只上报**，不对外开监听端口（隐私与穿透成本都更低）。
- **Viewer 只读**：只 `GET` / 订阅状态，无任何写配置/控制接口。

---

## 3. Windows 端 — 可行性

### 3.1 技术路径（推荐排序）

| 方案 | 前台窗口 API | 复杂度 | 备注 |
|------|-------------|--------|------|
| **A. Python + ctypes/pywin32**（推荐） | `GetForegroundWindow` + `GetWindowThreadProcessId` + `QueryFullProcessImageName` / `GetWindowTextW` | **低** | 易测、易配、与 pytest 同栈；可后期打包 exe |
| B. C# WinForms/WPF/Worker | 同上 P/Invoke 或 `Process` | 中 | 单 exe 体验好，测试栈不同 |
| C. Tauri / Rust | winapi / windows-rs | 中高 | 体积小，开发成本高 |
| D. Electron | 原生模块 | 高 | 过重，不推荐 |

**结论：方案 A 可行，复杂度低。** 核心 Win32 调用稳定、无需驱动/管理员权限（读自身会话前台窗口）。

### 3.2 采集方式

| 方式 | 复杂度 | 优劣 |
|------|--------|------|
| **轮询**（500ms–2s） | 低 | 实现简单，延迟可接受，推荐默认 |
| `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` | 中 | 几乎实时，但需消息泵（控制台可用隐藏窗口/`GetMessage` 线程） |

建议：**先做轮询**，钩子作为可选优化（配置项 `poll_interval_ms`）。

### 3.3 可采集字段（隐私相关）

| 字段 | API | 隐私敏感度 | 默认建议 |
|------|-----|-----------|---------|
| 进程名 / exe 名 | `QueryFullProcessImageName` | 低 | **上报** |
| 进程路径 | 同上 | 中 | 默认不上报或仅存本地 |
| 窗口标题 | `GetWindowTextW` | **高** | **默认关闭**，可配置且网页侧可再脱敏 |
| 应用显示名/图标 | 文件属性 / 图标缓存 | 低 | 可选美化 |

锁屏/空闲：`GetForegroundWindow` 为桌面壳或 `GetLastInputInfo` 可近似判断 idle。

### 3.4 客户端形态

- 控制台/托盘常驻 + JSON 配置（`agent.json`：`api_base_url`、`device_id`、`device_token`、`poll_interval_ms`、`report_window_title`、`blacklist`…）
- 可选「隐私暂停」本地开关（暂停时上报 `paused`，网页显示暂停而非具体应用）
- 打包：`pyinstaller` 可作后续 `feat`，非首版必须

**复杂度评级：低–中（首版约 1–2 人日）**

---

## 4. 安卓端 — 可行性（研究结论）

### 4.1 技术路径

| 路径 | 权限 | 复杂度 | 现实约束 |
|------|------|--------|---------|
| **UsageStatsManager** | `PACKAGE_USAGE_STATS`（用户去「使用情况访问权限」手动开） | 中 | 可拿前台包名/事件；厂商后台限制严格 |
| **AccessibilityService** | 无障碍服务开启 | 中高 | `TYPE_WINDOW_STATE_CHANGED` 最准；Play 商店对非无障碍用途限制极严 |
| AppOps / ADB 轮询 | adb 或 root | 高 | 不适合普通用户安装 |

### 4.2 限制（必须写入研究结论）

1. **无法静默获取前台应用**——必须用户显式授予使用情况访问或无障碍。
2. **前台服务类型**：Android 10+ 需 `foregroundServiceType`（如 `specialUse` / `connectedDevice` / `dataSync`），Android 14+ 审核更严。
3. **厂商杀后台**（小米/华为/OPPO 等）需用户加白名单，文档必须说明。
4. **Play 上架几乎不可行**（易被判监控/间谍软件）；侧载/个人使用可接受。
5. 与 Windows 相比：**权限摩擦大、机型碎片、电量策略**是主要成本。

**结论：技术可行，产品化成本高。** 建议：
- **本迭代：只交付《安卓端可行性报告》**（权限矩阵、API、类清单、伪代码）
- **可选后续**：Kotlin 侧载 demo（UsageStats 轮询 + 前台服务 + 与 Windows 相同上报协议）

**复杂度评级：中高（完整 App 约 4–8 人日 + 机型适配）；仅调研约 0.5 人日**

---

## 5. 后端 — 可行性

| 组件 | 推荐 | 复杂度 |
|------|------|--------|
| 框架 | FastAPI（async + WS）或 Starlette | 低 |
| 存储 | SQLite（单文件、易部署）；状态内存 + 历史落库 | 低 |
| 实时 | WebSocket 优先，SSE/轮询降级 | 中 |
| 鉴权 | Agent：`device_token`；Viewer：可选只读 `viewer_token`（见待确认） | 中 |
| API | `POST /api/v1/report`（Agent）；`GET /api/v1/devices`、`GET /api/v1/devices/{id}`、`GET /api/v1/devices/{id}/history`；`WS /api/v1/ws` | 低 |

**复杂度评级：中（约 1.5–2 人日）**

---

## 6. 网页查看端 — 可行性

- 纯静态：`index.html` + `app.js` + `styles.css` + `config.json`
- 配置示例：
  ```json
  {
    "apiBaseUrl": "https://example.com/api/v1",
    "viewerToken": "",
    "refreshMode": "websocket",
    "pollIntervalMs": 3000,
    "showWindowTitle": false
  }
  ```
- UI 风格：按 `UIDevelopInstructions.md`（Apple fluid design）——半透明材质、弹簧感过渡、系统字体、reduced-motion 降级。完整手势/抛掷动效可降级为「轻量 spring/fade」（指南允许降级）。
- **只读约束**：无表单提交到隐私配置；无设备控制按钮；暂停/黑名单等仅存在于 Agent 本地配置。

**复杂度评级：中（基础低，Apple 级动效可选）（约 1–2 人日）**

---

## 7. 配置与仓库

| 文件 | 是否进 Git | 说明 |
|------|-----------|------|
| `agent/config.example.json` / 默认模板 | ✅ | 示例与默认 |
| `agent/config.json` | ✅（**不**写入 `.gitignore`） | 按你的要求：配置不被 ignore；实现时用不含密钥的开发配置或占位 token |
| `server/config.example.json` | ✅ | 端口、DB 路径、token 开关 |
| `web/config.json` | ✅ | 后端地址等，部署时改 |
| `.gitignore` | ✅ | **不得**包含 `*.json` 配置、`config.json` 等；只忽略 venv、`__pycache__`、`.pytest_cache`、`*.db`、`dist/`、密钥类（如 `*.pem`、`.env`）——若你坚持密钥也入库，再放宽 |

启动逻辑（Agent / Server）：
1. 找配置 → 有则读取  
2. 无则按**默认设置**创建并持久化  
3. 校验字段，非法则报错退出（pytest 覆盖）

---

## 8. 测试策略（遵守“不启动应用”）

- 单元测试：配置加载/默认创建/回写、隐私过滤、上报 payload 构造、API schema、历史窗口逻辑
- 模拟 Win32：mock `GetForegroundWindow` 等（pytest + monkeypatch）
- FastAPI：`TestClient` / `httpx` 测 REST；WS 可用测试客户端
- Web：逻辑函数纯测（若抽离）；**不做**浏览器 E2E 直到代码齐
- **禁止**在全部代码完成前启动 agent/server 做真机联调

---

## 9. 实施阶段与复杂度总表

| 阶段 | 内容 | 复杂度 | 预估 |
|------|------|--------|------|
| P0 | 仓库骨架、`.gitignore`、配置层 + pytest | 低 | 0.5d |
| P1 | Windows Agent 采集 + 上报客户端 + pytest | 低中 | 1d |
| P2 | Backend API + SQLite + 鉴权 + pytest | 中 | 1.5d |
| P3 | Web Viewer（只读 + config + Apple 风 UI） | 中 | 1–1.5d |
| P4 | 安卓可行性报告（文档） | 低 | 0.5d |
| P5 | README + 使用指南；可选：托盘/图标/打包 | 低中 | 0.5d |
| 可选 | Android demo | **高** | 4–8d |

**首版（P0–P5）总复杂度：中，约 5–7 人日。**

---

## 10. 额外功能候选（供取舍）

### 对核心有加成（建议考虑）
1. **多设备列表** — 网页同时看多台（电脑/手机）当前状态  
2. **在线/离线心跳** — 超时未上报显示离线  
3. **应用友好名映射** — `Code.exe` → `Visual Studio Code`（配置或内置表）  
4. **隐私暂停** — Agent 一键 pause，网页只显示「已暂停」  
5. **进程黑名单** — 本地不上报特定应用（密码管理器等）  
6. **最近时间线** — 近 N 条前台切换（滚动条/列表）  
7. **只读分享链接** — `viewer_token` 区分公开/半公开  

### 体验向
8. 应用图标展示（Agent 上传或前端图标集）  
9. 空闲/锁屏显示「离开」  
10. 全屏游戏/视频角标  
11. 当日使用时长汇总（后续）  
12. 深色/浅色跟随系统（reduced-transparency 降级）  

### 明确不建议做（隐私/范围）
- 键盘记录、截屏、聊天内容、摄像头  
- 网页端改配置、远程暂停他人监控  
- 伪装进程/对抗杀软  

---

## 11. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 窗口标题泄露隐私 | 高 | 默认关；Agent/Viewer 双端可关 |
| token 进 Git（你要求配置入库） | 中 | 提供 `config.example` 与占位 token；README 说明生产环境改 token；可选忽略 `*local*` |
| WebSocket 部署（反代） | 中 | 支持轮询降级，静态站仍可用 |
| 安卓碎片化 | 高 | 本迭代不交付成品，只交付报告 |
| 误报 UWP/应用容器 | 低 | 记录 window class / process 源，测试覆盖 |
| 杀软误报常驻采集 | 中 | 代码签名可选；README 说明仅本机前台窗口 |

---

## 12. 目录规划（拟）

```text
WhatTheManDoing/
├── README.md
├── LICENSE
├── .gitignore
├── agent/                 # Windows 监控客户端
│   ├── config.json        # 持久化设置（入库，无真实密钥）
│   ├── main.py
│   ├── foreground.py
│   ├── config.py
│   └── tests/
├── server/                # 后端
│   ├── config.json
│   ├── app/
│   └── tests/
├── web/                   # 只读查看页（可独立部署）
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── config.json
├── docs/
│   └── android-feasibility.md
└── tests/                 # 可选：跨模块
```

---

## 13. 已确认决策（2026 对话）

| 项 | 决定 |
|----|------|
| 隐私字段 | **应用/进程名 + 可选窗口标题**；标题 **默认关闭**（`report_window_title: false`），Agent 可开；网页 `showWindowTitle` 再闸一道 |
| 访问控制 | **可选只读 `viewerToken`**；为空 = 公开只读；非空则 Viewer 请求需带 token |
| 设备规模 | **多设备列表**（卡片：设备名、在线状态、当前应用） |
| Windows 栈 | **Python**（ctypes / 可选 pywin32）+ pytest |
| 安卓 | **仅交付可行性报告**（`docs/android-feasibility.md`），本迭代不写 App |
| 历史（默认取舍） | 实时状态为主 + **最近前台切换时间线**（可配置条数，默认 50）；不做完整时长统计（可作 extra 后续） |

---

## 14. 锁定后的交付物

1. `agent/`：Windows Python 监控端 + 配置持久化 + 单元测试  
2. `server/`：FastAPI 后端（上报/只读 API/WS/SQLite）+ 单元测试  
3. `web/`：只读多设备查看页（Apple 风，可独立部署，`config.json` 连后端）  
4. `docs/android-feasibility.md`：安卓可行性报告  
5. `README.md`：部署与使用指南  
6. `.gitignore`：**忽略 venv/缓存/DB/密钥物；不忽略配置 JSON**  

每个文件编辑完成后立即 `feat./fix./…` 提交。全部代码完成前仅 pytest，不启动应用联调。
