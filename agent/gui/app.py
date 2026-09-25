"""Main window: configure monitoring, start/stop service, live status, autostart."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

from agent import autostart
from agent.config import (
    DEFAULT_CONFIG_PATH,
    AgentConfig,
    ConfigError,
    ensure_config,
    save_config,
    validate_config_dict,
)
from agent.gui import widgets
from agent.gui.theme import FONT_BODY, FONT_TITLE, system_theme
from agent.service import AgentService


class ControlPanel:
    """Local-only privacy control plane. Not exposed on the read-only web viewer."""

    def __init__(self, root: tk.Tk, config_path=None) -> None:
        self.root = root
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.theme = system_theme()
        self.config = ensure_config(self.config_path)
        self.service = AgentService(self.config)

        root.title("在干什么 · 控制台")
        root.configure(bg=self.theme.bg)
        root.minsize(520, 640)
        root.geometry("560x760")

        self._build()
        self._load_form()
        self._refresh_autostart()
        self._tick()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----- UI construction -------------------------------------------------

    def _build(self) -> None:
        t = self.theme

        header = tk.Frame(self.root, bg=t.bg_elevated, pady=12, padx=16)
        header.pack(fill="x", side="top")
        brand = tk.Label(
            header,
            text="在干什么",
            bg=t.bg_elevated,
            fg=t.ink,
            font=FONT_TITLE,
        )
        brand.pack(side="left")
        sub = tk.Label(
            header,
            text="本地控制台 · 仅本机",
            bg=t.bg_elevated,
            fg=t.secondary,
            font=FONT_BODY,
        )
        sub.pack(side="left", padx=(10, 0))
        self.pill = widgets.Pill(header, t, "已停止")
        self.pill.pack(side="right")
        self.pill.set_state("已停止", t.secondary)

        # Scrollable body
        container = tk.Frame(self.root, bg=t.bg)
        container.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(container, bg=t.bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(self.canvas, bg=t.bg, padx=16, pady=16)
        self._body = body
        self._body_window = self.canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body_configure(_event=None) -> None:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.canvas.itemconfigure(self._body_window, width=self.canvas.winfo_width())

        body.bind("<Configure>", _on_body_configure)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._body_window, width=e.width),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Status card
        widgets.SectionLabel(body, t, "实时状态").pack(fill="x", pady=(0, 6))
        status_card = widgets.Card(body, t)
        status_card.pack(fill="x", pady=(0, 16))
        self.app_label = widgets.DisplayLabel(status_card, t, "未运行", size=20)
        self.app_label.pack(fill="x")
        self.proc_label = widgets.CaptionLabel(status_card, t, "启动服务后显示当前前台应用")
        self.proc_label.pack(fill="x", pady=(4, 10))
        self.stats = widgets.StatusPulse(status_card, t)
        self.stats.pack(fill="x")
        self.err_label = widgets.CaptionLabel(status_card, t, "")
        self.err_label.pack(fill="x", pady=(8, 0))

        # Connection card
        widgets.SectionLabel(body, t, "设备与连接").pack(fill="x", pady=(0, 6))
        conn = widgets.Card(body, t)
        conn.pack(fill="x", pady=(0, 16))
        self.f_device_id = widgets.LabeledEntry(conn, t, "设备 ID")
        self.f_device_id.pack(fill="x", pady=(0, 10))
        self.f_device_name = widgets.LabeledEntry(conn, t, "设备名称")
        self.f_device_name.pack(fill="x", pady=(0, 10))
        self.f_api = widgets.LabeledEntry(conn, t, "后端 API 地址")
        self.f_api.pack(fill="x", pady=(0, 10))
        self.f_token = widgets.LabeledEntry(conn, t, "设备 Token", show="•")
        self.f_token.pack(fill="x", pady=(0, 10))
        self.f_interval = widgets.LabeledEntry(conn, t, "采样间隔（毫秒）", width=12)
        self.f_interval.pack(fill="x")

        # Privacy card
        widgets.SectionLabel(body, t, "隐私").pack(fill="x", pady=(0, 6))
        priv = widgets.Card(body, t)
        priv.pack(fill="x", pady=(0, 16))

        row_title = tk.Frame(priv, bg=t.card)
        row_title.pack(fill="x", pady=4)
        left = tk.Frame(row_title, bg=t.card)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="上报窗口标题", bg=t.card, fg=t.ink, font=FONT_BODY, anchor="w").pack(fill="x")
        tk.Label(
            left,
            text="关闭更安全。标题可能含文档名、聊天内容。",
            bg=t.card,
            fg=t.secondary,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x")
        self.t_title = widgets.Toggle(row_title, t, on=False)
        self.t_title.pack(side="right")

        row_pause = tk.Frame(priv, bg=t.card)
        row_pause.pack(fill="x", pady=4)
        left2 = tk.Frame(row_pause, bg=t.card)
        left2.pack(side="left", fill="x", expand=True)
        tk.Label(left2, text="隐私暂停", bg=t.card, fg=t.ink, font=FONT_BODY, anchor="w").pack(fill="x")
        tk.Label(
            left2,
            text="开启后网页只显示「已暂停」，不暴露应用。",
            bg=t.card,
            fg=t.secondary,
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x")
        self.t_pause = widgets.Toggle(row_pause, t, on=False)
        self.t_pause.pack(side="right")

        self.f_blacklist = widgets.LabeledEntry(priv, t, "进程黑名单（逗号分隔）")
        self.f_blacklist.pack(fill="x", pady=(10, 0))

        # Actions
        actions = tk.Frame(body, bg=t.bg)
        actions.pack(fill="x", pady=(4, 8))
        self.btn_start = widgets.AppleButton(actions, t, "启动服务", command=self._start_service)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.btn_stop = widgets.AppleButton(
            actions, t, "停止", kind="secondary", command=self._stop_service
        )
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.btn_save = widgets.AppleButton(
            actions, t, "保存设置", kind="secondary", command=self._save_form
        )
        self.btn_save.pack(side="left", expand=True, fill="x")
        self.btn_stop.set_enabled(False)

        # Autostart
        auto = widgets.Card(body, t)
        auto.pack(fill="x", pady=(12, 24))
        auto_row = tk.Frame(auto, bg=t.card)
        auto_row.pack(fill="x")
        auto_left = tk.Frame(auto_row, bg=t.card)
        auto_left.pack(side="left", fill="x", expand=True)
        tk.Label(auto_left, text="开机自动启动", bg=t.card, fg=t.ink, font=FONT_BODY, anchor="w").pack(fill="x")
        self.auto_caption = tk.Label(
            auto_left,
            text="登录 Windows 后自动打开本控制台",
            bg=t.card,
            fg=t.secondary,
            font=("Segoe UI", 8),
            anchor="w",
        )
        self.auto_caption.pack(fill="x")
        self.t_autostart = widgets.Toggle(auto_row, t, on=False, command=self._on_autostart_toggle)
        self.t_autostart.pack(side="right")

        self.footer = tk.Label(
            body,
            text="只读网页不能修改这些设置 · 配置保存在 agent/config.json",
            bg=t.bg,
            fg=t.secondary,
            font=("Segoe UI", 8),
        )
        self.footer.pack(fill="x", pady=(0, 8))

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ----- form <-> config -------------------------------------------------

    def _load_form(self) -> None:
        c = self.config
        self.f_device_id.set(c.device_id)
        self.f_device_name.set(c.device_name)
        self.f_api.set(c.api_base_url)
        self.f_token.set(c.device_token)
        self.f_interval.set(str(c.poll_interval_ms))
        self.t_title.set(c.report_window_title, fire=False)
        self.t_pause.set(c.privacy_pause, fire=False)
        self.f_blacklist.set(", ".join(c.app_name_blacklist))

    def _form_to_config(self) -> AgentConfig:
        interval_text = self.f_interval.get().strip() or "1000"
        blacklist_raw = self.f_blacklist.get().replace("，", ",")
        blacklist = [x.strip() for x in blacklist_raw.split(",") if x.strip()]
        data = {
            "api_base_url": self.f_api.get().strip(),
            "device_id": self.f_device_id.get().strip(),
            "device_name": self.f_device_name.get().strip() or self.f_device_id.get().strip(),
            "device_token": self.f_token.get(),
            "poll_interval_ms": int(interval_text),
            "report_window_title": self.t_title.get(),
            "app_name_blacklist": blacklist,
            "history_limit": self.config.history_limit,
            "privacy_pause": self.t_pause.get(),
            "display_name_map": self.config.display_name_map,
        }
        return validate_config_dict(data)

    def _save_form(self) -> bool:
        try:
            cfg = self._form_to_config()
        except (ConfigError, ValueError) as exc:
            messagebox.showerror("无法保存", str(exc), parent=self.root)
            return False
        try:
            save_config(cfg, self.config_path)
        except OSError as exc:
            messagebox.showerror("无法保存", str(exc), parent=self.root)
            return False
        self.config = cfg
        self.service.update_config(cfg)
        self.pill.set_state("设置已保存", self.theme.green)
        return True

    # ----- service --------------------------------------------------------

    def _start_service(self) -> None:
        if not self._save_form():
            return
        if self.service.start():
            self.btn_start.set_enabled(False)
            self.btn_stop.set_enabled(True)
            self.pill.set_state("运行中", self.theme.green)

    def _stop_service(self) -> None:
        self.service.stop()
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)
        self.pill.set_state("已停止", self.theme.secondary)

    def _tick(self) -> None:
        snap = self.service.snapshot()
        self._render_status(snap)
        self.root.after(500, self._tick)

    def _render_status(self, snap: dict[str, Any]) -> None:
        t = self.theme
        running = snap.get("running")
        status = snap.get("status") or ""
        if running and status == "paused":
            self.app_label.configure(text="已暂停分享")
            self.proc_label.configure(text="隐私模式 · 网页仅显示「已暂停」")
            self.pill.set_state("已暂停", t.orange)
        elif running and snap.get("current_app"):
            self.app_label.configure(text=str(snap.get("current_app")))
            proc = snap.get("current_process") or ""
            self.proc_label.configure(text=proc)
            self.pill.set_state("运行中", t.green)
        elif running:
            self.app_label.configure(text="采样中…")
            self.proc_label.configure(text="正在读取前台窗口")
            self.pill.set_state("运行中", t.green)
        else:
            self.app_label.configure(text="未运行")
            self.proc_label.configure(text="启动服务后显示当前前台应用")
            self.pill.set_state("已停止", t.secondary)

        self.stats.update_stats(
            int(snap.get("ok_count") or 0),
            int(snap.get("fail_count") or 0),
            snap.get("last_report_at"),
        )
        err = snap.get("last_error") or ""
        self.err_label.configure(text=f"最近错误：{err}" if err else "")
        self.err_label.configure(fg=t.red if err else t.secondary)

        # Keep button state consistent if service stopped itself.
        if not running:
            self.btn_start.set_enabled(True)
            self.btn_stop.set_enabled(False)

    # ----- autostart ------------------------------------------------------

    def _refresh_autostart(self) -> None:
        try:
            enabled = autostart.is_enabled()
            self.t_autostart.set(enabled, fire=False)
            if enabled:
                cmd = autostart.current_command() or ""
                self.auto_caption.configure(text=f"已启用 · {cmd[:64]}")
            else:
                self.auto_caption.configure(text="登录 Windows 后自动打开本控制台")
        except autostart.AutostartError as exc:
            self.auto_caption.configure(text=f"无法读取自启状态：{exc}")

    def _on_autostart_toggle(self, on: bool) -> None:
        try:
            if on:
                cmd = autostart.enable()
                self.auto_caption.configure(text=f"已启用 · {cmd[:64]}")
            else:
                autostart.disable()
                self.auto_caption.configure(text="登录 Windows 后自动打开本控制台")
        except autostart.AutostartError as exc:
            self.t_autostart.set(False, fire=False)
            messagebox.showerror("开机启动", str(exc), parent=self.root)

    def _on_close(self) -> None:
        try:
            self.service.stop()
        except Exception:
            pass
        self.root.destroy()


def launch(config_path=None) -> int:
    root = tk.Tk()
    ControlPanel(root, config_path=config_path)
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="WhatTheManDoing local control panel")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args(argv)
    return launch(config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
