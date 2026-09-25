/**
 * Read-only viewer: loads config.json, polls/streams device state.
 * Never mutates server or privacy settings.
 */

const state = {
  config: {
    apiBaseUrl: "http://127.0.0.1:8765/api/v1",
    viewerToken: "",
    refreshMode: "poll",
    pollIntervalMs: 3000,
    showWindowTitle: false,
  },
  devices: [],
  selectedId: null,
  timer: null,
  ws: null,
};

const el = {
  connPill: document.getElementById("conn-pill"),
  connLabel: document.getElementById("conn-label"),
  hero: document.getElementById("hero"),
  heroApp: document.getElementById("hero-app"),
  heroMeta: document.getElementById("hero-meta"),
  deviceGrid: document.getElementById("device-grid"),
  deviceCount: document.getElementById("device-count"),
  devicesEmpty: document.getElementById("devices-empty"),
  timeline: document.getElementById("timeline"),
  historyEmpty: document.getElementById("history-empty"),
  historyDeviceLabel: document.getElementById("history-device-label"),
};

function setConn(mode, label) {
  el.connPill.dataset.state = mode;
  el.connLabel.textContent = label;
}

function authHeaders() {
  const headers = { Accept: "application/json" };
  if (state.config.viewerToken) {
    headers.Authorization = `Bearer ${state.config.viewerToken}`;
  }
  return headers;
}

async function loadConfig() {
  const res = await fetch("./config.json", { cache: "no-store" });
  if (!res.ok) throw new Error("无法加载 config.json");
  const data = await res.json();
  state.config = { ...state.config, ...data };
}

async function fetchJson(path) {
  const url = state.config.apiBaseUrl.replace(/\/$/, "") + path;
  const res = await fetch(url, { headers: authHeaders() });
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  // Standard envelope: { code, message, data }
  if (body && typeof body === "object" && "code" in body) {
    if (body.code === 0) {
      return body.data;
    }
    if (res.status === 401 || body.code === 40100) {
      setConn("error", "Token 无效");
      throw new Error(body.message || "unauthorized");
    }
    if (res.status === 429 || body.code === 42900) {
      setConn("degraded", "触发限流");
      throw new Error(body.message || "rate limited");
    }
    throw new Error(body.message || `code ${body.code}`);
  }

  if (res.status === 401) {
    setConn("error", "Token 无效");
    throw new Error("unauthorized");
  }
  if (res.status === 429) {
    setConn("degraded", "触发限流");
    throw new Error("rate limited");
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return body;
}

function formatTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function statusTone(device) {
  if (device.status === "paused") return "paused";
  return device.online ? "online" : "offline";
}

function statusLabel(device) {
  if (device.status === "paused") return "已暂停";
  return device.online ? "在线" : "离线";
}

function appLabel(device) {
  const app = device.app;
  if (!app) {
    if (device.status === "paused") return "已暂停分享";
    return "无前台应用";
  }
  return app.display_name || app.process_name || "未知应用";
}

function renderDevices() {
  const devices = state.devices;
  el.deviceCount.textContent = devices.length ? `${devices.length} 台` : "";
  el.devicesEmpty.hidden = devices.length > 0;
  el.deviceGrid.replaceChildren();

  for (const device of devices) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "device-card";
    card.setAttribute("aria-current", device.device_id === state.selectedId ? "true" : "false");

    const top = document.createElement("div");
    top.className = "device-card-top";

    const name = document.createElement("div");
    name.className = "device-name";
    name.textContent = device.device_name || device.device_id;

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.dataset.tone = statusTone(device);
    badge.textContent = statusLabel(device);

    top.append(name, badge);

    const app = document.createElement("p");
    app.className = "device-app";
    app.textContent = appLabel(device);

    const process = document.createElement("p");
    process.className = "device-process";
    const procName = device.app?.process_name;
    process.textContent = procName ? procName : device.status === "paused" ? "privacy pause" : "—";

    const time = document.createElement("p");
    time.className = "device-time";
    time.textContent = device.updated_at ? `更新于 ${formatTime(device.updated_at)}` : "尚无上报";

    card.append(top, app, process, time);
    card.addEventListener("click", () => selectDevice(device.device_id));
    el.deviceGrid.append(card);
  }

  renderHero();
}

function renderHero() {
  const devices = state.devices;
  if (!devices.length) {
    el.hero.hidden = true;
    return;
  }
  const selected =
    devices.find((d) => d.device_id === state.selectedId) || devices[0];
  el.hero.hidden = false;
  el.heroApp.textContent = appLabel(selected);
  const bits = [selected.device_name || selected.device_id];
  bits.push(statusLabel(selected));
  if (selected.app?.process_name) bits.push(selected.app.process_name);
  el.heroMeta.textContent = bits.join(" · ");
}

async function renderHistory() {
  const device =
    state.devices.find((d) => d.device_id === state.selectedId) || state.devices[0];
  if (!device) {
    el.timeline.replaceChildren();
    el.historyEmpty.hidden = false;
    el.historyDeviceLabel.textContent = "";
    return;
  }

  el.historyEmpty.hidden = true;
  el.historyDeviceLabel.textContent = device.device_name || device.device_id;

  try {
    const data = await fetchJson(
      `/devices/${encodeURIComponent(device.device_id)}/history?limit=20`
    );
    el.timeline.replaceChildren();
    for (const item of data.history || []) {
      const li = document.createElement("li");
      const time = document.createElement("time");
      time.dateTime = item.timestamp || "";
      time.textContent = formatTime(item.timestamp);

      const body = document.createElement("div");
      const title = document.createElement("span");
      title.className = "tl-app";
      title.textContent = item.display_name || item.process_name || item.status;

      const proc = document.createElement("span");
      proc.className = "tl-process";
      const titleText =
        state.config.showWindowTitle && item.window_title
          ? ` · ${item.window_title}`
          : "";
      proc.textContent = `${item.process_name || "—"}${titleText}`;

      body.append(title, proc);
      li.append(time, body);
      el.timeline.append(li);
    }
  } catch {
    el.timeline.replaceChildren();
  }
}

async function refresh() {
  try {
    const data = await fetchJson("/devices");
    state.devices = data.devices || [];
    if (!state.selectedId && state.devices.length) {
      state.selectedId = state.devices[0].device_id;
    }
    setConn("live", "实时");
    renderDevices();
    await renderHistory();
  } catch {
    setConn("degraded", "连接失败");
  }
}

function selectDevice(deviceId) {
  state.selectedId = deviceId;
  renderDevices();
  renderHistory();
}

function startPolling() {
  stopPolling();
  const ms = Math.max(1000, Number(state.config.pollIntervalMs) || 3000);
  state.timer = setInterval(refresh, ms);
}

function stopPolling() {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
}

function startWebSocket() {
  if (state.ws) {
    try {
      state.ws.close();
    } catch {
      /* ignore */
    }
    state.ws = null;
  }

  const base = state.config.apiBaseUrl.replace(/\/$/, "");
  const wsBase = base.replace(/^http/, "ws").replace(/\/api\/v1$/, "/api/v1/ws");
  const url = state.config.viewerToken
    ? `${wsBase}?token=${encodeURIComponent(state.config.viewerToken)}`
    : wsBase;

  try {
    const ws = new WebSocket(url);
    state.ws = ws;
    ws.addEventListener("message", (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "device" && msg.data) {
          const next = msg.data;
          const idx = state.devices.findIndex((d) => d.device_id === next.device_id);
          if (idx >= 0) state.devices[idx] = next;
          else state.devices.push(next);
          setConn("live", "实时");
          renderDevices();
          renderHistory();
        }
      } catch {
        /* ignore malformed frames */
      }
    });
    ws.addEventListener("open", () => {
      setConn("live", "实时");
      refresh();
    });
    ws.addEventListener("close", () => {
      setConn("degraded", "重连中…");
      // Fall back to polling while socket is down.
      startPolling();
    });
    ws.addEventListener("error", () => {
      setConn("degraded", "重连中…");
      startPolling();
    });
  } catch {
    startPolling();
  }
}

async function boot() {
  try {
    await loadConfig();
  } catch {
    setConn("error", "配置缺失");
    return;
  }

  await refresh();

  const mode = String(state.config.refreshMode || "poll").toLowerCase();
  if (mode === "websocket") {
    startWebSocket();
    // Safety net even with WS: refresh periodically for offline detection.
    startPolling();
  } else {
    startPolling();
  }
}

boot();
