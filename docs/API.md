# WhatTheManDoing 客户端 API 参考（v1）

面向**客户端开发者**：网页、桌面、移动端、脚本均可按本文对接。  
本项目（含本地控制台 GUI）**仅作为服务端**；客户端只读调用 JSON API。

- 默认基础地址：`http://127.0.0.1:8765`
- 路径前缀：`/api/v1`
- 请求/响应均为 **UTF-8 JSON**
- 所有业务响应使用统一 envelope

---

## 1. 统一响应格式（Envelope）

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | integer | `0` 成功；非 `0` 为业务错误码 |
| `message` | string | 人类可读说明 |
| `data` | object \| array \| null | 成功时的数据；失败时常为 `null` |

### 业务错误码

| code | HTTP | 含义 |
|------|------|------|
| `0` | 200 | 成功 |
| `40000` | 400 | 请求参数错误 |
| `40100` | 401 | 未授权 / Token 无效 |
| `40300` | 403 | 禁止访问 |
| `40400` | 404 | 资源不存在 |
| `42900` | 429 | 触发限流 |
| `50000` | 500 | 服务端错误 |

**约定：** 先看 HTTP 状态码，再看 `code` 与 `message`。成功时 `code` 恒为 `0`。

### 响应头（限流）

| 头 | 说明 |
|----|------|
| `X-RateLimit-Limit` | 全局每分钟最大请求数 |
| `X-RateLimit-Remaining` | 本窗口剩余次数 |
| `Retry-After` | 被拒时建议等待秒数（仅 429） |

限流为**全局**（所有客户端共享额度），可由服务端 GUI 调整，默认 `120` 次/分钟。

---

## 2. 鉴权

| 接口 | 鉴权 |
|------|------|
| `GET /health`、`GET /status`、`GET /status/history` | 默认无鉴权（本机/内网） |
| `GET /devices*` | 若配置了 `viewer_token` 则需 `Authorization: Bearer <token>` |
| `POST /report` | 必须 `Authorization: Bearer <device_token>` |

```http
Authorization: Bearer <token>
```

未配置 `viewer_token`（空字符串）时，查询类接口为公开只读。

---

## 3. 核心端点（客户端优先使用）

### 3.1 `GET /api/v1/health`

健康检查与当前限流额度。

**响应 `data`**

```json
{
  "status": "ok",
  "rate_limit_per_minute": 120
}
```

**curl**

```bash
curl -s http://127.0.0.1:8765/api/v1/health
```

**示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": { "status": "ok", "rate_limit_per_minute": 120 }
}
```

---

### 3.2 `GET /api/v1/status` ★

返回**本机当前前台应用**（隐私过滤后）。

**响应 `data`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `device_id` | string | 设备 ID |
| `device_name` | string | 显示名 |
| `status` | string | `active` \| `paused` \| `idle` \| `stopped` |
| `app` | object \| null | 当前应用；`paused`/`idle` 时为 `null` |
| `app.process_name` | string | 进程名（黑名单显示为 `redacted`） |
| `app.display_name` | string | 友好名称 |
| `app.window_title` | string \| null | 窗口标题；**默认不返回** |
| `timestamp` | string | ISO-8601 UTC，如 `2026-01-01T12:00:00Z` |

**示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "device_id": "my-pc",
    "device_name": "My PC",
    "status": "active",
    "app": {
      "process_name": "Code.exe",
      "display_name": "Visual Studio Code",
      "window_title": null
    },
    "timestamp": "2026-01-01T12:00:00Z"
  }
}
```

**curl**

```bash
curl -s http://127.0.0.1:8765/api/v1/status | jq .
```

**轮询建议：** 3–10 秒一次；请遵守 `X-RateLimit-*`，收到 `42900` 时按 `Retry-After` 退避。

---

### 3.3 `GET /api/v1/status/history`

本机最近前台切换（由监控服务写入）。

**Query**

| 参数 | 默认 | 范围 | 说明 |
|------|------|------|------|
| `limit` | 50 | 1–1000 | 返回条数 |

**响应 `data`**

```json
{
  "device_id": "my-pc",
  "history": [
    {
      "id": 12,
      "device_id": "my-pc",
      "status": "active",
      "process_name": "Code.exe",
      "display_name": "Visual Studio Code",
      "window_title": null,
      "timestamp": "2026-01-01T12:00:00Z"
    }
  ]
}
```

---

## 4. 设备上报与多设备（可选）

用于其它机器上的 Agent 上报，或客户端聚合多设备。鉴权见 §2。

### 4.1 `POST /api/v1/report`

**Headers：** `Content-Type: application/json`，`Authorization: Bearer <device_token>`

**Body**

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

**成功 `data`：** `{ "ok": true }`

### 4.2 `GET /api/v1/devices`

**成功 `data`：** `{ "devices": [ /* 同 status 结构，另含 online */ ] }`

| 字段 | 说明 |
|------|------|
| `online` | boolean，超过 `offline_after_seconds` 未上报为 `false` |

### 4.3 `GET /api/v1/devices/{device_id}`

单设备；不存在时 `code=40400`。

### 4.4 `GET /api/v1/devices/{device_id}/history?limit=50`

字段同 §3.3 的 `history[]`。

### 4.5 `WS /api/v1/ws?token=<viewer_token>`

推送：`{"type":"device","data":{...设备对象...}}`。可选，客户端可用轮询代替。

---

## 5. 错误处理

**429 限流**

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 7
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 0
```

```json
{
  "code": 42900,
  "message": "rate limit exceeded, try again later",
  "data": null
}
```

**401**

```json
{
  "code": 40100,
  "message": "invalid viewer token",
  "data": null
}
```

**客户端推荐策略**

1. 成功：`code == 0` 且 HTTP 2xx  
2. `40100`：检查 Token，勿盲目重试  
3. `42900`：等待 `Retry-After` 秒后重试（指数退避更佳）  
4. `50000`：有限次重试  

---

## 6. 完整示例

### JavaScript（fetch）

```javascript
const BASE = "http://127.0.0.1:8765/api/v1";

async function getStatus() {
  const res = await fetch(`${BASE}/status`);
  const body = await res.json();
  if (body.code !== 0) {
    throw new Error(`${body.code}: ${body.message}`);
  }
  return body.data;
}

// 轮询（注意限流）
setInterval(() => {
  getStatus()
    .then((s) => console.log(s.status, s.app?.display_name))
    .catch((e) => console.error(e));
}, 5000);
```

### Python

```python
import time, requests

BASE = "http://127.0.0.1:8765/api/v1"

while True:
    r = requests.get(f"{BASE}/status", timeout=5)
    body = r.json()
    if body["code"] != 0:
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)))
            continue
        raise RuntimeError(body["message"])
    data = body["data"]
    print(data["status"], data.get("app"))
    time.sleep(5)
```

### curl

```bash
curl -s http://127.0.0.1:8765/api/v1/status
curl -s -H "Authorization: Bearer read-token" http://127.0.0.1:8765/api/v1/devices
```

---

## 7. 隐私与安全（客户端须知）

1. `window_title` 默认不下发；请勿假设存在。  
2. 进程黑名单在服务端脱敏为 `redacted`。  
3. `status=paused` 时 `app` 为 `null`，请展示「已暂停」而非猜测应用。  
4. 将服务暴露到公网前：配置 `viewer_token`、收紧 `cors_origins`、置于 HTTPS 反向代理之后。  
5. 限流为全局额度，多客户端请分摊轮询频率。  

---

## 8. 版本

- 当前：`v1`（路径 `/api/v1`）  
- 破坏性变更将提升路径主版本；envelope 字段保持向后兼容扩展  

服务实现：`server/app/main.py`；错误码：`server/app/envelope.py`。
