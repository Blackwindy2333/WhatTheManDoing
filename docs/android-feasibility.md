# 安卓端可行性报告

> 范围：本迭代**仅调研**，不交付 Android App。协议与 Windows Agent 对齐，便于后续侧载 demo 接入。

## 1. 目标回顾

在安卓设备上采集**当前前台应用**，按与 Windows Agent 相同的 JSON 协议上报到后端，供只读网页展示。

## 2. 技术路径对比

| 路径 | 关键 API | 需要的用户授权 | 精度 | 实现复杂度 | 上架可行性 |
|------|---------|----------------|------|------------|------------|
| A. UsageStats | `UsageStatsManager.queryEvents` / `queryUsageStats` | 设置 →「使用情况访问权限」 | 高（包名 + 切换事件） | 中 | 个人/侧载可；Play 风险高 |
| B. AccessibilityService | `TYPE_WINDOW_STATE_CHANGED` | 设置 →「无障碍」 | 高（包名，部分机型含标题） | 中高 | Play **几乎禁止**非无障碍用途 |
| C. 轮询 `ActivityManager` | 过时/受限 | — | 低 | 低 | 现代系统不可用 |
| D. ADB / root | `dumpsys activity` | 开发者或 root | 高 | 中 | 不适合普通用户 |

**推荐路径 A**（UsageStats + 前台服务），必要时用 B 增强（demo 可只做 A）。

## 3. 权限与系统约束（必须知晓）

1. **无法静默读取前台应用**  
   必须引导用户手动打开「使用情况访问」或「无障碍」。安装后首次启动必须做权限引导页。

2. **前台服务（Android 8+）**  
   后台采样必须用 `ForegroundService` + 通知栏常驻，否则进程会被杀。

3. **`foregroundServiceType`（Android 10+ / 14+ 更严）**  
   合理候选：`specialUse` / `connectedDevice` / `dataSync`。Android 14+ 需在 Manifest 声明类型并可能在 Play Console 说明用途。

4. **厂商杀后台**  
   小米/华为/OPPO/vivo/三星等需用户加入「电池白名单 / 自启动」。文档与首次引导必须写明。

5. **包名可见性（Android 11+）**  
   `QUERY_ALL_PACKAGES` 受限；UsageStats 在已授权时仍可读到使用事件，但应用图标/名称解析可能需要 `<queries>` 或改为显示包名。

6. **隐私**  
   窗口标题在安卓侧基本拿不到（除非无障碍）；默认只上报 **package + label**。与 Windows 相同：黑名单、隐私暂停在设备端完成。

7. **Play 商店政策**  
   「监控他人/设备使用」类能力极易被判 **Stalkerware / 间谍软件**。本项目定位为**本人自愿分享自己的前台应用**，即便如此，**侧载 APK 是唯一务实分发方式**。

## 4. 建议架构（与现协议兼容）

```text
[Foreground Service] → UsageStatsManager 采样
        ↓ 组装 JSON（device_id / status / app）
[OkHttp / HttpURLConnection] POST {api_base_url}/report
        Header: Authorization: Bearer {device_token}
```

与 `agent/reporter.py` 的 `build_payload` 字段一致：

```json
{
  "device_id": "pixel-7",
  "device_name": "Pixel 7",
  "status": "active",
  "timestamp": "2026-01-01T12:00:00Z",
  "app": {
    "process_name": "com.spotify.music",
    "display_name": "Spotify",
    "window_title": null
  }
}
```

说明：
- `process_name` 在安卓侧填 **package name**。
- `window_title` 恒为 `null`（除非未来做无障碍增强）。
- `status`: `active` | `paused`（通知栏开关）| `idle`。

## 5. 权限矩阵

| 能力 | Manifest | 用户授权 | 备注 |
|------|----------|----------|------|
| UsageStats | `PACKAGE_USAGE_STATS` | 是（设置页） | 不可运行时弹窗静默授予 |
| 前台服务 | `FOREGROUND_SERVICE` + type | 通知权限（13+） | 必须常驻通知 |
| 网络 | `INTERNET` | — | 上报 |
| 无障碍（可选） | `BIND_ACCESSIBILITY_SERVICE` | 是 | 更准的前台事件，政策风险更高 |

## 6. 复杂度评估

| 工作项 | 估时 |
|--------|------|
| Kotlin 空壳 + 引导权限 + 前台服务 | 1–2 d |
| UsageStats 轮询/事件 → 统一 payload | 1 d |
| 上报、重试、隐私暂停通知栏 | 1 d |
| 厂商适配说明 + 简单设置页（device_id/token/API URL） | 1 d |
| 多机型抽测 | 1–2 d |
| **合计** | **约 4–8 人日** |

对比 Windows Python Agent（约 1 人日）：**安卓明显更贵**，故本迭代只保留本报告。

## 7. 风险清单

| 风险 | 等级 | 缓解 |
|------|------|------|
| 用户未授权导致空数据 | 高 | 首启动引导 + 通知栏「未授权」状态 |
| 厂商杀进程 | 高 | 引导白名单；心跳超时网页显示离线 |
| Play 拒绝/下架 | 高 | 仅侧载；不宣称「监控」 |
| 省电策略导致采样漂移 | 中 | 2s 轮询 + 事件修正 |
| 包名无法映射友名 | 低 | 允许本地 display_name_map |

## 8. 后续若实现：最小里程碑

1. **M1** 设置页（API URL / device_id / token）+ 使用情况访问引导  
2. **M2** 前台服务 + 每 2s 采样 + POST `/report`  
3. **M3** 通知栏隐私暂停 + 离线重试  
4. **M4**（可选）无障碍增强窗口标题 / 更快事件  

## 9. 结论

- **技术可行**，协议可与现有后端无缝对接。  
- **产品化成本高**：授权摩擦、厂商碎片、分发政策。  
- **建议**：先交付 Windows + 网页；安卓在真实需求出现后再按 M1–M3 做侧载 demo。  
