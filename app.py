from __future__ import annotations

from collections import deque
import ctypes
from pathlib import Path
import queue
import subprocess
import threading
import tempfile
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import serial
from serial.tools import list_ports

from core import Telemetry, engine_reason, parse_packet
from device_config import BOARD_PROFILES, HelmetConfig, SafeRideConfig, VehicleConfig, load_config, save_config
from firmware_builder import render_firmware
from uploader import arduino_cli_path, upload_sketch
from updater import GitHubUpdater, ReleaseInfo, UpdateError, is_newer_version
from version import APP_VERSION


# Tk otherwise renders in virtual 96-DPI coordinates and Windows clips the
# fullscreen dashboard at common 125%/150% exhibition display scaling.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


COLORS = {
    "bg": "#f1f5f9",
    "panel": "#ffffff",
    "panel2": "#f8fafc",
    "line": "#cbd5e1",
    "text": "#0f172a",
    "muted": "#475569",
    "cyan": "#2563eb",
    "cyan2": "#004ac6",
    "green": "#15803d",
    "red": "#dc2626",
    "amber": "#d97706",
    "ink": "#ffffff",
    "navy": "#0f172a",
    "console": "#020617",
}


def set_font(widget: tk.Widget, size: int, weight: str = "normal", family: str = "Segoe UI") -> None:
    widget.configure(font=(family, size, weight))


def button(parent: tk.Widget, text: str, command: Callable, primary: bool = False, width: int | None = None) -> tk.Button:
    bg = COLORS["cyan"] if primary else COLORS["panel2"]
    fg = COLORS["ink"] if primary else COLORS["text"]
    active_bg = "#1d4ed8" if primary else "#e2e8f0"
    item = tk.Button(
        parent, text=text, command=command, relief="flat", bd=0,
        bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
        cursor="hand2", padx=20, pady=11, highlightthickness=0,
        width=width,
    )
    set_font(item, 10, "bold")
    return item


class SerialBridge:
    def __init__(self, helmet_port: str, vehicle_port: str, emit: Callable[[str, object], None]):
        self.emit = emit
        self.stop_event = threading.Event()
        self.helmet = serial.Serial(helmet_port, 9600, timeout=0.2, write_timeout=0.5)
        self.vehicle = serial.Serial(vehicle_port, 9600, timeout=0.2, write_timeout=0.5)
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        time.sleep(1.8)
        self.threads = [
            threading.Thread(target=self._helmet_loop, daemon=True, name="helmet-reader"),
            threading.Thread(target=self._vehicle_loop, daemon=True, name="vehicle-reader"),
        ]
        for thread in self.threads:
            thread.start()
        self.emit("system", "Serial bridge active")

    @staticmethod
    def _readline(port: serial.Serial) -> str:
        return port.readline().decode("utf-8", errors="replace").strip()

    def _helmet_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                line = self._readline(self.helmet)
                if not line:
                    continue
                self.emit("raw", ("HELMET", line))
                data = parse_packet(line)
                if data:
                    packet = data.helmet_packet()
                    self.vehicle.write((packet + "\n").encode("ascii"))
                    self.emit("helmet", data)
            except (serial.SerialException, OSError) as exc:
                self.emit("error", f"Helmet port: {exc}")
                return

    def _vehicle_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                line = self._readline(self.vehicle)
                if not line:
                    continue
                self.emit("raw", ("VEHICLE", line))
                data = parse_packet(line)
                if data:
                    self.emit("vehicle", data)
            except (serial.SerialException, OSError) as exc:
                self.emit("error", f"Vehicle port: {exc}")
                return

    def close(self) -> None:
        self.stop_event.set()
        for port in (self.helmet, self.vehicle):
            try:
                port.close()
            except Exception:
                pass


class StatusCard(tk.Frame):
    def __init__(self, parent: tk.Widget, kicker: str, title: str):
        super().__init__(parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        self.configure(padx=16, pady=13)
        top = tk.Frame(self, bg=COLORS["panel"])
        top.pack(fill="x")
        self.dot = tk.Canvas(top, width=12, height=12, bg=COLORS["panel"], highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(2, 2, 10, 10, fill=COLORS["muted"], outline="")
        label = tk.Label(top, text=kicker.upper(), bg=COLORS["panel"], fg=COLORS["muted"])
        set_font(label, 8, "bold")
        label.pack(side="left", padx=(7, 0))
        self.value = tk.Label(self, text=title, anchor="w", bg=COLORS["panel"], fg=COLORS["text"])
        set_font(self.value, 16, "bold")
        self.value.pack(fill="x", pady=(10, 2))
        self.detail = tk.Label(self, text="Waiting for telemetry", anchor="w", bg=COLORS["panel"], fg=COLORS["muted"])
        set_font(self.detail, 9)
        self.detail.pack(fill="x")

    def update_status(self, value: str, detail: str, ok: bool, warning: bool = False) -> None:
        color = COLORS["amber"] if warning else (COLORS["green"] if ok else COLORS["red"])
        self.configure(highlightbackground=color, highlightthickness=2)
        self.dot.itemconfigure(self.dot_id, fill=color)
        self.value.configure(text=value, fg=color)
        self.detail.configure(text=detail)


class TelemetryChart(tk.Canvas):
    def __init__(self, parent: tk.Widget, threshold: int = 400):
        super().__init__(parent, bg=COLORS["panel"], highlightthickness=0, width=1, height=220)
        self.threshold = threshold
        self.points: deque[int] = deque([0] * 90, maxlen=90)
        self.bind("<Configure>", lambda _event: self.draw())

    def push(self, value: int) -> None:
        self.points.append(value)
        self.draw()

    def draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        left, top, right, bottom = 48, 20, width - 18, height - 28
        threshold_y = bottom - (self.threshold / 1023) * (bottom - top)
        self.create_rectangle(left, threshold_y, right, bottom, fill="#f0fdf4", outline="")
        for level in (0, 250, 500, 750, 1000):
            y = bottom - (level / 1023) * (bottom - top)
            self.create_line(left, y, right, y, fill=COLORS["line"], width=1)
            self.create_text(left - 10, y, text=str(level), fill=COLORS["muted"], anchor="e", font=("Consolas", 8))
        self.create_line(left, threshold_y, right, threshold_y, fill=COLORS["red"], dash=(6, 4), width=2)
        self.create_text(right, threshold_y - 8, text=f"ALCOHOL LOCK THRESHOLD {self.threshold} ADC", fill=COLORS["red"], anchor="e", font=("Segoe UI", 8, "bold"))
        if len(self.points) < 2:
            return
        coords: list[float] = []
        values = list(self.points)
        for index, value in enumerate(values):
            x = left + index * (right - left) / max(1, len(values) - 1)
            y = bottom - (value / 1023) * (bottom - top)
            coords.extend([x, y])
        self.create_line(*coords, fill=COLORS["cyan"], width=2, smooth=True)
        self.create_oval(coords[-2] - 4, coords[-1] - 4, coords[-2] + 4, coords[-1] + 4, fill=COLORS["cyan"], outline="")


class LinkVisualizer(tk.Canvas):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent, bg=COLORS["panel"], highlightthickness=0, width=1, height=100)
        self.phase = 0
        self.active = False
        self.after(50, self._animate)

    def set_active(self, active: bool) -> None:
        self.active = active

    def _animate(self) -> None:
        self.phase = (self.phase + 0.018) % 1
        self.draw()
        self.after(50, self._animate)

    def draw(self) -> None:
        self.delete("all")
        w, h = max(200, self.winfo_width()), max(80, self.winfo_height())
        y = h / 2
        self.create_line(78, y, w - 78, y, fill=COLORS["line"], width=2, dash=(5, 7))
        for x, label in ((54, "HELMET"), (w - 54, "VEHICLE")):
            fill = COLORS["panel2"]
            outline = (COLORS["cyan"] if label == "HELMET" else COLORS["green"]) if self.active else COLORS["muted"]
            self.create_oval(x - 25, y - 25, x + 25, y + 25, fill=fill, outline=outline, width=2)
            self.create_text(x, y, text="H" if label == "HELMET" else "V", fill=COLORS["text"], font=("Segoe UI", 13, "bold"))
            self.create_text(x, y + 37, text=label, fill=COLORS["muted"], font=("Segoe UI", 7, "bold"))
        if self.active:
            span = max(1, w - 156)
            for offset in (0, .33, .66):
                p = (self.phase + offset) % 1
                x = 78 + span * p
                self.create_oval(x - 3, y - 3, x + 3, y + 3, fill=COLORS["cyan"], outline="")


class ConfigurationWizard(tk.Toplevel):
    def __init__(self, parent: "SafeRideApp", config: SafeRideConfig, on_saved: Callable[[SafeRideConfig], None]):
        super().__init__(parent)
        self.title("SafeRide hardware configuration wizard")
        self.geometry("980x690")
        self.minsize(900, 640)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self.on_saved = on_saved
        self.step = 0
        self.pages: list[tk.Frame] = []
        self.step_labels: list[tk.Label] = []
        self.vars = self._make_vars(config)
        self._build_shell()
        self.show_step(0)

    @staticmethod
    def _make_vars(config: SafeRideConfig) -> dict[str, tk.Variable]:
        h, v = config.helmet, config.vehicle
        values: dict[str, object] = {
            "helmet_board": h.board, "vehicle_board": v.board,
            "alcohol_pin": h.alcohol_pin, "helmet_ir_pin": str(h.helmet_ir_pin),
            "eye_ir_pin": str(h.eye_ir_pin), "helmet_led_pin": str(h.led_pin),
            "helmet_buzzer_pin": str(h.buzzer_pin), "alcohol_threshold": str(h.alcohol_threshold),
            "drowsy_limit_ms": str(h.drowsy_limit_ms), "helmet_send_interval_ms": str(h.send_interval_ms),
            "helmet_active_low": h.helmet_active_low, "eye_active_low": h.eye_active_low,
            "relay_pin": str(v.relay_pin), "vehicle_led_pin": str(v.led_pin),
            "vehicle_buzzer_pin": str(v.buzzer_pin), "link_timeout_ms": str(v.link_timeout_ms),
            "vehicle_send_interval_ms": str(v.send_interval_ms), "relay_active_high": v.relay_active_high,
        }
        return {key: (tk.BooleanVar(value=value) if isinstance(value, bool) else tk.StringVar(value=value)) for key, value in values.items()}

    def _build_shell(self) -> None:
        header = tk.Frame(self, bg=COLORS["navy"], padx=18, pady=12)
        header.pack(fill="x")
        title = tk.Label(header, text="SAFERIDE CONFIGURATION WIZARD", bg=COLORS["navy"], fg="#ffffff")
        set_font(title, 13, "bold")
        title.pack(anchor="w")
        sub = tk.Label(header, text="Board-aware pins, thresholds and signal polarity", bg=COLORS["navy"], fg="#94a3b8")
        set_font(sub, 8, family="Consolas")
        sub.pack(anchor="w")

        body = tk.Frame(self, bg=COLORS["bg"], padx=14, pady=14)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, width=220, padx=8, pady=8)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)
        for index, label in enumerate(("1  Board profiles", "2  Helmet sensors", "3  Vehicle interlock", "4  Review and save")):
            item = tk.Label(sidebar, text=label, bg=COLORS["panel"], fg=COLORS["muted"], anchor="w", padx=10, pady=10)
            set_font(item, 9, "bold")
            item.pack(fill="x", pady=2)
            self.step_labels.append(item)

        self.content = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=20, pady=18)
        self.content.pack(side="left", fill="both", expand=True)
        self.pages = [self._board_page(), self._helmet_page(), self._vehicle_page(), self._review_page()]

        footer = tk.Frame(self, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=14, pady=10)
        footer.pack(fill="x")
        button(footer, "CANCEL", self.destroy).pack(side="left")
        self.save_button = button(footer, "SAVE CONFIGURATION", self.save, primary=True)
        self.next_button = button(footer, "NEXT", self.next_step, primary=True)
        self.next_button.pack(side="right")
        self.back_button = button(footer, "BACK", self.previous_step)
        self.back_button.pack(side="right", padx=8)

    def _page(self, title: str, copy: str) -> tk.Frame:
        page = tk.Frame(self.content, bg=COLORS["panel"])
        heading = tk.Label(page, text=title, bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(heading, 17, "bold")
        heading.pack(fill="x")
        detail = tk.Label(page, text=copy, bg=COLORS["panel"], fg=COLORS["muted"], anchor="w", justify="left")
        set_font(detail, 9)
        detail.pack(fill="x", pady=(4, 16))
        return page

    def _field(self, page: tk.Widget, label: str, key: str, hint: str = "") -> None:
        row = tk.Frame(page, bg=COLORS["panel"])
        row.pack(fill="x", pady=5)
        words = tk.Frame(row, bg=COLORS["panel"])
        words.pack(side="left", fill="x", expand=True)
        name = tk.Label(words, text=label, bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(name, 9, "bold")
        name.pack(fill="x")
        if hint:
            helper = tk.Label(words, text=hint, bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
            set_font(helper, 7, family="Consolas")
            helper.pack(fill="x")
        entry = tk.Entry(row, textvariable=self.vars[key], bg=COLORS["panel2"], fg=COLORS["text"], relief="solid", bd=1, width=18)
        set_font(entry, 9, family="Consolas")
        entry.pack(side="right", ipady=7, padx=(12, 0))

    def _toggle(self, page: tk.Widget, label: str, key: str, hint: str) -> None:
        row = tk.Frame(page, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=10, pady=7)
        row.pack(fill="x", pady=5)
        words = tk.Frame(row, bg=COLORS["panel2"])
        words.pack(side="left", fill="x", expand=True)
        name = tk.Label(words, text=label, bg=COLORS["panel2"], fg=COLORS["text"], anchor="w")
        set_font(name, 9, "bold")
        name.pack(fill="x")
        helper = tk.Label(words, text=hint, bg=COLORS["panel2"], fg=COLORS["muted"], anchor="w")
        set_font(helper, 7, family="Consolas")
        helper.pack(fill="x")
        control = tk.Checkbutton(row, variable=self.vars[key], bg=COLORS["panel2"], activebackground=COLORS["panel2"], selectcolor="#dbeafe")
        control.pack(side="right")

    def _board_page(self) -> tk.Frame:
        page = self._page("Choose the controller boards", "Auto Detect tries known AVR profiles safely. Select an exact board to reduce upload time.")
        labels = [profile.label for profile in BOARD_PROFILES.values()]
        self.board_keys = {profile.label: profile.key for profile in BOARD_PROFILES.values()}
        for title, key in (("Helmet Arduino", "helmet_board"), ("Vehicle Arduino", "vehicle_board")):
            card = tk.Frame(page, bg=COLORS["panel2"], highlightbackground=COLORS["line"], highlightthickness=1, padx=12, pady=12)
            card.pack(fill="x", pady=7)
            name = tk.Label(card, text=title, bg=COLORS["panel2"], fg=COLORS["text"], anchor="w")
            set_font(name, 10, "bold")
            name.pack(fill="x", pady=(0, 6))
            current = BOARD_PROFILES[str(self.vars[key].get())].label
            display_var = tk.StringVar(value=current)
            combo = ttk.Combobox(card, values=labels, textvariable=display_var, state="readonly", style="SafeRide.TCombobox")
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda _event, k=key, v=display_var: self.vars[k].set(self.board_keys[v.get()]))
        note = tk.Label(page, text="Supported profiles: Uno, Nano new bootloader, Nano old bootloader and Mega 2560. D0/D1 remain reserved for USB serial.", bg="#eff6ff", fg=COLORS["cyan"], padx=10, pady=10, justify="left", anchor="w", wraplength=620)
        set_font(note, 8, "bold", "Consolas")
        note.pack(fill="x", pady=(12, 0))
        return page

    def _helmet_page(self) -> tk.Frame:
        page = self._page("Configure helmet sensors", "Pin names and thresholds are compiled into the helmet firmware when you flash.")
        grid = tk.Frame(page, bg=COLORS["panel"])
        grid.pack(fill="both", expand=True)
        left = tk.Frame(grid, bg=COLORS["panel"]); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = tk.Frame(grid, bg=COLORS["panel"]); right.pack(side="left", fill="both", expand=True)
        for target, label, key, hint in (
            (left, "MQ-3 analog pin", "alcohol_pin", "A0 to board analog maximum"),
            (left, "Helmet IR pin", "helmet_ir_pin", "Digital pin, not D0/D1"),
            (left, "Eye IR pin", "eye_ir_pin", "Digital pin, not D0/D1"),
            (left, "Status LED pin", "helmet_led_pin", "Unique digital pin"),
            (left, "Buzzer pin", "helmet_buzzer_pin", "Unique digital pin"),
            (right, "Alcohol threshold", "alcohol_threshold", "0 to 1023 ADC"),
            (right, "Drowsiness time", "drowsy_limit_ms", "250 to 30000 ms"),
            (right, "Packet interval", "helmet_send_interval_ms", "100 to 2000 ms"),
        ):
            self._field(target, label, key, hint)
        self._toggle(right, "Helmet sensor is active-low", "helmet_active_low", "Checked means LOW = helmet worn")
        self._toggle(right, "Eye sensor is active-low", "eye_active_low", "Checked means LOW = eye closed")
        return page

    def _vehicle_page(self) -> tk.Frame:
        page = self._page("Configure the vehicle interlock", "These settings control the physical relay, indicators and link fail-safe.")
        for label, key, hint in (
            ("Engine relay pin", "relay_pin", "Digital pin, not D0/D1"),
            ("Status LED pin", "vehicle_led_pin", "Unique digital pin"),
            ("Buzzer pin", "vehicle_buzzer_pin", "Unique digital pin"),
            ("Link timeout", "link_timeout_ms", "500 to 30000 ms"),
            ("Status packet interval", "vehicle_send_interval_ms", "100 to 2000 ms"),
        ):
            self._field(page, label, key, hint)
        self._toggle(page, "Relay is active-high", "relay_active_high", "Checked means HIGH unlocks the engine; clear for active-low relay modules")
        return page

    def _review_page(self) -> tk.Frame:
        page = self._page("Review and save", "SafeRide validates this configuration before it can reach the compiler or either board.")
        self.review_text = tk.Text(page, bg=COLORS["console"], fg="#cbd5e1", relief="flat", bd=0, padx=14, pady=12, state="disabled")
        set_font(self.review_text, 9, family="Consolas")
        self.review_text.pack(fill="both", expand=True)
        return page

    def build_config(self) -> SafeRideConfig:
        def number(key: str, label: str) -> int:
            try:
                return int(str(self.vars[key].get()).strip())
            except ValueError as exc:
                raise ValueError(f"{label} must be a whole number") from exc

        config = SafeRideConfig(
            helmet=HelmetConfig(
                board=str(self.vars["helmet_board"].get()), alcohol_pin=str(self.vars["alcohol_pin"].get()).strip().upper(),
                helmet_ir_pin=number("helmet_ir_pin", "Helmet IR pin"), eye_ir_pin=number("eye_ir_pin", "Eye IR pin"),
                led_pin=number("helmet_led_pin", "Helmet LED pin"), buzzer_pin=number("helmet_buzzer_pin", "Helmet buzzer pin"),
                alcohol_threshold=number("alcohol_threshold", "Alcohol threshold"), drowsy_limit_ms=number("drowsy_limit_ms", "Drowsiness time"),
                send_interval_ms=number("helmet_send_interval_ms", "Helmet packet interval"),
                helmet_active_low=bool(self.vars["helmet_active_low"].get()), eye_active_low=bool(self.vars["eye_active_low"].get()),
            ),
            vehicle=VehicleConfig(
                board=str(self.vars["vehicle_board"].get()), relay_pin=number("relay_pin", "Relay pin"),
                led_pin=number("vehicle_led_pin", "Vehicle LED pin"), buzzer_pin=number("vehicle_buzzer_pin", "Vehicle buzzer pin"),
                link_timeout_ms=number("link_timeout_ms", "Link timeout"), send_interval_ms=number("vehicle_send_interval_ms", "Vehicle packet interval"),
                relay_active_high=bool(self.vars["relay_active_high"].get()),
            ),
        )
        config.validate()
        return config

    def show_step(self, index: int) -> None:
        self.step = index
        for page in self.pages:
            page.pack_forget()
        self.pages[index].pack(fill="both", expand=True)
        for position, label in enumerate(self.step_labels):
            label.configure(bg="#eff6ff" if position == index else COLORS["panel"], fg=COLORS["cyan"] if position == index else COLORS["muted"])
        self.back_button.pack_forget()
        self.next_button.pack_forget()
        self.save_button.pack_forget()
        self.back_button.configure(state="normal" if index > 0 else "disabled")
        if index == len(self.pages) - 1:
            self._refresh_review()
            self.save_button.pack(side="right")
        else:
            self.next_button.pack(side="right")
        self.back_button.pack(side="right", padx=8)

    def next_step(self) -> None:
        try:
            if self.step >= 1:
                self.build_config()
        except ValueError as exc:
            messagebox.showerror("Configuration needs attention", str(exc), parent=self)
            return
        self.show_step(min(self.step + 1, len(self.pages) - 1))

    def previous_step(self) -> None:
        self.show_step(max(0, self.step - 1))

    def _refresh_review(self) -> None:
        try:
            config = self.build_config()
            h, v = config.helmet, config.vehicle
            text = (
                f"HELMET BOARD   {BOARD_PROFILES[h.board].label}\n"
                f"HELMET PINS    MQ-3={h.alcohol_pin}  PRESENCE=D{h.helmet_ir_pin}  EYE=D{h.eye_ir_pin}  LED=D{h.led_pin}  BUZZER=D{h.buzzer_pin}\n"
                f"THRESHOLDS     ALCOHOL={h.alcohol_threshold} ADC  DROWSY={h.drowsy_limit_ms} ms\n"
                f"SENSOR LOGIC   HELMET={'ACTIVE-LOW' if h.helmet_active_low else 'ACTIVE-HIGH'}  EYE={'ACTIVE-LOW' if h.eye_active_low else 'ACTIVE-HIGH'}\n\n"
                f"VEHICLE BOARD  {BOARD_PROFILES[v.board].label}\n"
                f"VEHICLE PINS   RELAY=D{v.relay_pin}  LED=D{v.led_pin}  BUZZER=D{v.buzzer_pin}\n"
                f"FAIL-SAFE      LINK TIMEOUT={v.link_timeout_ms} ms  RELAY={'ACTIVE-HIGH' if v.relay_active_high else 'ACTIVE-LOW'}\n\n"
                "VALIDATION      PASSED\n"
                "NEXT FLASH      SafeRide will generate both sketches from this configuration."
            )
        except ValueError as exc:
            text = f"VALIDATION FAILED\n\n{exc}"
        self.review_text.configure(state="normal")
        self.review_text.delete("1.0", "end")
        self.review_text.insert("1.0", text)
        self.review_text.configure(state="disabled")

    def save(self) -> None:
        try:
            config = self.build_config()
            save_config(config)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save configuration", str(exc), parent=self)
            return
        self.on_saved(config)
        self.destroy()


class SafeRideApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SafeRide")
        self.geometry("1440x900")
        self.minsize(1180, 760)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.configure(bg=COLORS["bg"])
        self._icon = tk.PhotoImage(width=32, height=32)
        self._icon.put(COLORS["cyan"], to=(0, 0, 32, 32))
        self._icon.put(COLORS["ink"], to=(7, 7, 25, 25))
        self._icon.put(COLORS["cyan"], to=(12, 11, 20, 21))
        self.iconphoto(True, self._icon)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.bridge: SerialBridge | None = None
        self.latest = Telemetry()
        self.last_state_key: tuple | None = None
        self.raw_count = 0
        self.port_map: dict[str, object] = {}
        self.device_config = load_config()
        self.updater = GitHubUpdater()
        self._update_busy = False
        self._configure_styles()
        self.show_setup()
        self.after(60, self._drain_events)
        self.after(1500, self._auto_check_for_updates)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("SafeRide.TCombobox", fieldbackground=COLORS["panel2"], background=COLORS["panel2"],
                        foreground=COLORS["text"], arrowcolor=COLORS["cyan"], bordercolor=COLORS["line"],
                        lightcolor=COLORS["line"], darkcolor=COLORS["line"], padding=9)
        style.map("SafeRide.TCombobox", fieldbackground=[("readonly", COLORS["panel2"])],
                  foreground=[("readonly", COLORS["text"])])

    def clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def show_setup(self) -> None:
        self.clear()
        root = tk.Frame(self, bg=COLORS["bg"], padx=16, pady=10)
        root.pack(fill="both", expand=True)

        system_bar = tk.Frame(root, bg=COLORS["navy"], padx=12, pady=5)
        system_bar.pack(fill="x")
        system_name = tk.Label(system_bar, text="SAFERIDE OS  /  EMBEDDED CONTROL ENVIRONMENT", bg=COLORS["navy"], fg="#e2e8f0")
        set_font(system_name, 8, "bold", "Consolas")
        system_name.pack(side="left")
        mode = tk.Label(system_bar, text=f"v{APP_VERSION}  /  HARDWARE SETUP + FLASH", bg=COLORS["navy"], fg="#60a5fa")
        set_font(mode, 8, "bold", "Consolas")
        mode.pack(side="right")

        hero = tk.Frame(root, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=14, pady=10)
        hero.pack(fill="x", pady=(0, 8))
        hero_left = tk.Frame(hero, bg=COLORS["panel"])
        hero_left.pack(side="left", fill="x", expand=True)
        badge = tk.Label(hero_left, text="EXHIBITION DEPLOYMENT WIZARD  /  REV 2.0", bg="#eff6ff", fg=COLORS["cyan"], padx=7, pady=2)
        set_font(badge, 7, "bold", "Consolas")
        badge.pack(anchor="w")
        heading = tk.Label(hero_left, text="SafeRide control hardware setup", bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(heading, 18, "bold")
        heading.pack(anchor="w", pady=(5, 1))
        copy = tk.Label(hero_left, text="Assign two physical USB channels. SafeRide compiles, flashes, verifies, then opens live telemetry.", bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
        set_font(copy, 9)
        copy.pack(anchor="w")
        metrics = tk.Frame(hero, bg=COLORS["panel"])
        metrics.pack(side="right")
        for label, value, color in (
            ("TARGET", "ARDUINO AVR", COLORS["text"]),
            ("TOPOLOGY", "DUAL USB", COLORS["cyan"]),
            ("DEFAULT", "RELAY LOCKED", COLORS["green"]),
        ):
            box = tk.Frame(metrics, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=10, pady=6)
            box.pack(side="left", padx=3)
            small = tk.Label(box, text=label, bg=COLORS["panel2"], fg=COLORS["muted"])
            set_font(small, 7, "bold", "Consolas")
            small.pack(anchor="w")
            val = tk.Label(box, text=value, bg=COLORS["panel2"], fg=color)
            set_font(val, 9, "bold", "Consolas")
            val.pack(anchor="w")

        body = tk.Frame(root, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=7)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=COLORS["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.helmet_combo = self._hardware_interface(
            left, "HELMET CONTROLLER INTERFACE  /  MCU-A", COLORS["cyan"],
            "MQ-3 A0  •  HELMET IR D2  •  EYE IR D3", "Reads real helmet safety sensors",
        )
        self.vehicle_combo = self._hardware_interface(
            left, "VEHICLE INTERLOCK CONTROLLER  /  ECU-B", COLORS["green"],
            "RELAY D4  •  STATUS LED D5  •  BUZZER D6", "Controls the engine interlock",
        )
        self._refresh_config_labels()
        self.helmet_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_port_guard())
        self.vehicle_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_port_guard())

        guard = tk.Frame(left, bg="#eff6ff", highlightbackground="#bfdbfe", highlightthickness=1, padx=10, pady=7)
        guard.pack(fill="x", pady=4)
        guard_title = tk.Label(guard, text="PORT COLLISION GUARD", bg="#eff6ff", fg=COLORS["cyan"])
        set_font(guard_title, 8, "bold", "Consolas")
        guard_title.pack(side="left")
        self.guard_label = tk.Label(guard, text="WAITING FOR TWO PORTS", bg="#eff6ff", fg=COLORS["muted"])
        set_font(self.guard_label, 8, "bold", "Consolas")
        self.guard_label.pack(side="right")

        controls = tk.Frame(left, bg=COLORS["bg"])
        controls.pack(fill="x", pady=(4, 0))
        button(controls, "RESCAN", self.scan_ports).pack(side="left", fill="x", expand=True, padx=(0, 3))
        button(controls, "CONFIGURE", self.open_configuration_wizard).pack(side="left", fill="x", expand=True, padx=3)
        self.update_button = button(controls, "CHECK UPDATE", self.check_for_updates)
        self.update_button.pack(side="left", fill="x", expand=True, padx=3)
        self.flash_button = button(controls, "FLASH + LAUNCH", self.begin_upload, primary=True)
        self.flash_button.pack(side="left", fill="x", expand=True, padx=(3, 0))

        policy = tk.Frame(left, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=10, pady=9)
        policy.pack(fill="both", expand=True, pady=(8, 0))
        policy_title = tk.Label(policy, text="ENGINE INTERLOCK POLICY  /  LOADED", bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(policy_title, 9, "bold", "Consolas")
        policy_title.pack(fill="x", pady=(0, 6))
        for signal, required, failure in (
            ("HELMET PRESENCE", "H = 1", "LOCK IF ABSENT"),
            ("ALCOHOL SENSOR", "A = 0", "LOCK IF DETECTED"),
            ("DROWSINESS", "D = 0", "LOCK IF DETECTED"),
            ("PACKET LINK", "LINK = 1", "LOCK ON TIMEOUT"),
        ):
            row = tk.Frame(policy, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=8, pady=6)
            row.pack(fill="x", pady=2)
            name = tk.Label(row, text=signal, bg=COLORS["panel2"], fg=COLORS["text"], width=22, anchor="w")
            set_font(name, 8, "bold", "Consolas")
            name.pack(side="left")
            target = tk.Label(row, text=required, bg=COLORS["panel2"], fg=COLORS["green"], width=12, anchor="w")
            set_font(target, 8, "bold", "Consolas")
            target.pack(side="left")
            result = tk.Label(row, text=failure, bg=COLORS["panel2"], fg=COLORS["red"], anchor="e")
            set_font(result, 8, "bold", "Consolas")
            result.pack(side="right")
        rule = tk.Label(policy, text="ENGINE ENABLED ONLY WHEN ALL FOUR CONDITIONS PASS", bg="#f0fdf4", fg=COLORS["green"], padx=8, pady=8)
        set_font(rule, 9, "bold", "Consolas")
        rule.pack(fill="x", side="bottom", pady=(8, 0))

        right = tk.Frame(body, bg=COLORS["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        pipeline = tk.Frame(right, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=10, pady=9)
        pipeline.pack(fill="x")
        pipe_title = tk.Label(pipeline, text="FOUR-STEP AUTOMATED PROVISIONING PIPELINE", bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(pipe_title, 9, "bold", "Consolas")
        pipe_title.pack(fill="x", pady=(0, 6))
        self.pipeline_rows: list[tuple[tk.Frame, tk.Label, tk.Label]] = []
        for index, (title, detail) in enumerate((
            ("Detecting USB boards", "Two distinct serial ports required"),
            ("Uploading helmet firmware", "Compile and flash helmet controller"),
            ("Uploading vehicle firmware", "Compile and flash relay controller"),
            ("Opening live dashboard", "Start the real serial bridge"),
        )):
            row = tk.Frame(pipeline, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=8, pady=5)
            row.pack(fill="x", pady=2)
            number = tk.Label(row, text=str(index + 1), width=3, bg="#e2e8f0", fg=COLORS["muted"])
            set_font(number, 9, "bold", "Consolas")
            number.pack(side="left", ipady=3)
            words = tk.Frame(row, bg=COLORS["panel2"])
            words.pack(side="left", fill="x", expand=True, padx=8)
            name = tk.Label(words, text=title, bg=COLORS["panel2"], fg=COLORS["text"], anchor="w")
            set_font(name, 9, "bold")
            name.pack(fill="x")
            detail_label = tk.Label(words, text=detail, bg=COLORS["panel2"], fg=COLORS["muted"], anchor="w")
            set_font(detail_label, 7, family="Consolas")
            detail_label.pack(fill="x")
            state = tk.Label(row, text="WAITING", bg=COLORS["panel2"], fg=COLORS["muted"], width=12)
            set_font(state, 8, "bold", "Consolas")
            state.pack(side="right")
            self.pipeline_rows.append((row, number, state))
        self.setup_progress = ttk.Progressbar(pipeline, maximum=100, value=0, mode="determinate")
        self.setup_progress.pack(fill="x", pady=(7, 0))

        cli_ok = arduino_cli_path() is not None
        console = tk.Frame(right, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=10, pady=9)
        console.pack(fill="both", expand=True, pady=(8, 0))
        console_title = tk.Label(console, text="TECHNICAL COMPILATION + FLASH LOG", bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(console_title, 9, "bold", "Consolas")
        console_title.pack(fill="x", pady=(0, 6))
        self.setup_log = tk.Text(console, width=1, height=7, bg=COLORS["console"], fg="#94a3b8", insertbackground="#60a5fa",
                                 relief="flat", bd=0, padx=12, pady=10, state="disabled", wrap="word")
        set_font(self.setup_log, 8, family="Consolas")
        self.setup_log.pack(fill="both", expand=True)
        self._setup_log("Arduino upload engine ready." if cli_ok else "Development mode: Arduino CLI not bundled yet. Run tools\\build.ps1.")
        self.scan_ports()

    def open_configuration_wizard(self) -> None:
        ConfigurationWizard(self, self.device_config, self._configuration_saved)

    def _configuration_saved(self, config: SafeRideConfig) -> None:
        self.device_config = config
        self._refresh_config_labels()
        h, v = config.helmet, config.vehicle
        self._setup_log(
            f"Configuration saved: helmet {BOARD_PROFILES[h.board].label}, vehicle {BOARD_PROFILES[v.board].label}, "
            f"alcohol threshold {h.alcohol_threshold} ADC, relay D{v.relay_pin}."
        )

    def _set_update_button(self, text: str, enabled: bool = True) -> None:
        if hasattr(self, "update_button") and self.update_button.winfo_exists():
            self.update_button.configure(text=text, state="normal" if enabled else "disabled")

    def _auto_check_for_updates(self) -> None:
        if not self._update_busy:
            self._start_update_check(interactive=False)

    def check_for_updates(self) -> None:
        if self._update_busy:
            return
        self._start_update_check(interactive=True)

    def _start_update_check(self, interactive: bool) -> None:
        self._update_busy = True
        self._set_update_button("CHECKING...", enabled=False)
        threading.Thread(target=self._update_check_worker, args=(interactive,), daemon=True).start()

    def _update_check_worker(self, interactive: bool) -> None:
        try:
            release = self.updater.latest_release()
            self.events.put(("update_checked", (release, interactive)))
        except UpdateError as exc:
            self.events.put(("update_error", (str(exc), interactive)))

    def _handle_update_checked(self, release: ReleaseInfo, interactive: bool) -> None:
        self._update_busy = False
        self._set_update_button("CHECK UPDATE")
        if not is_newer_version(release.version):
            if interactive:
                messagebox.showinfo(
                    "SafeRide is current",
                    f"SafeRide {APP_VERSION} is the latest private release.",
                    parent=self,
                )
            return
        notes = release.notes.strip()
        if len(notes) > 1200:
            notes = notes[:1200].rstrip() + "..."
        install = messagebox.askyesno(
            "SafeRide update available",
            f"Version {release.version} is available. You have {APP_VERSION}.\n\n{notes}\n\n"
            "Download and verify the update now?",
            parent=self,
        )
        if not install:
            return
        self._update_busy = True
        self._set_update_button("DOWNLOADING...", enabled=False)
        threading.Thread(target=self._update_download_worker, args=(release,), daemon=True).start()

    def _update_download_worker(self, release: ReleaseInfo) -> None:
        try:
            installer = self.updater.download_update(release)
            self.events.put(("update_ready", (release, installer)))
        except UpdateError as exc:
            self.events.put(("update_error", (str(exc), True)))

    def _handle_update_ready(self, release: ReleaseInfo, installer: Path) -> None:
        self._update_busy = False
        self._set_update_button("CHECK UPDATE")
        install = messagebox.askyesno(
            "Update verified",
            f"SafeRide {release.version} passed SHA-256 verification.\n\n"
            "Install it now? SafeRide will close and reopen after the upgrade.",
            parent=self,
        )
        if not install:
            return
        if self.bridge:
            self.bridge.close()
            self.bridge = None
        try:
            subprocess.Popen(
                [str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                cwd=str(installer.parent),
            )
        except OSError as exc:
            messagebox.showerror("Could not start installer", str(exc), parent=self)
            return
        self.after(400, self.destroy)

    def _hardware_interface(self, parent: tk.Widget, title: str, accent: str, hardware: str, detail: str) -> ttk.Combobox:
        card = tk.Frame(parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=10, pady=9)
        card.pack(fill="x", pady=(0, 8))
        header = tk.Frame(card, bg=COLORS["panel2"], padx=7, pady=5)
        header.pack(fill="x")
        dot = tk.Canvas(header, width=10, height=10, bg=COLORS["panel2"], highlightthickness=0)
        dot.create_rectangle(2, 2, 8, 8, fill=accent, outline="")
        dot.pack(side="left")
        title_label = tk.Label(header, text=title, bg=COLORS["panel2"], fg=COLORS["text"])
        set_font(title_label, 8, "bold", "Consolas")
        title_label.pack(side="left", padx=6)
        detail_label = tk.Label(card, text=detail, bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
        set_font(detail_label, 8)
        detail_label.pack(fill="x", pady=(8, 3))
        combo = ttk.Combobox(card, state="readonly", style="SafeRide.TCombobox")
        combo.pack(fill="x")
        hardware_label = tk.Label(card, text=hardware, bg=COLORS["panel2"], fg=COLORS["muted"], anchor="w", padx=8, pady=6)
        set_font(hardware_label, 8, "bold", "Consolas")
        hardware_label.pack(fill="x", pady=(7, 0))
        if "HELMET" in title:
            self.helmet_config_label = hardware_label
        else:
            self.vehicle_config_label = hardware_label
        return combo

    def _refresh_config_labels(self) -> None:
        if not hasattr(self, "helmet_config_label"):
            return
        h, v = self.device_config.helmet, self.device_config.vehicle
        self.helmet_config_label.configure(
            text=f"MQ-3 {h.alcohol_pin}  •  HELMET IR D{h.helmet_ir_pin}  •  EYE IR D{h.eye_ir_pin}  •  LIMIT {h.alcohol_threshold}"
        )
        self.vehicle_config_label.configure(
            text=f"RELAY D{v.relay_pin}  •  LED D{v.led_pin}  •  BUZZER D{v.buzzer_pin}  •  TIMEOUT {v.link_timeout_ms} ms"
        )

    def _set_pipeline(self, index: int, state: str, progress: int | None = None) -> None:
        if not hasattr(self, "pipeline_rows") or index >= len(self.pipeline_rows):
            return
        row, number, state_label = self.pipeline_rows[index]
        palette = {
            "waiting": (COLORS["panel2"], "#e2e8f0", COLORS["muted"], "WAITING"),
            "active": ("#eff6ff", COLORS["cyan"], COLORS["cyan"], "IN PROGRESS"),
            "complete": ("#f0fdf4", COLORS["green"], COLORS["green"], "COMPLETE"),
            "failed": ("#fef2f2", COLORS["red"], COLORS["red"], "FAILED"),
        }
        background, number_bg, color, text = palette[state]
        row.configure(bg=background, highlightbackground=number_bg)
        number.configure(bg=number_bg, fg="#ffffff" if state != "waiting" else COLORS["muted"])
        state_label.configure(bg=background, fg=color, text=text)
        for child in row.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=background)
                for label in child.winfo_children():
                    label.configure(bg=background)
        if progress is not None:
            self.setup_progress["value"] = progress

    def _brand_bar(self, parent: tk.Widget, setup: bool = False) -> None:
        bar = tk.Frame(parent, bg=COLORS["bg"])
        bar.pack(fill="x")
        mark = tk.Label(bar, text="SR", width=3, bg=COLORS["cyan"], fg=COLORS["ink"])
        set_font(mark, 15, "bold")
        mark.pack(side="left", ipady=5)
        brand = tk.Frame(bar, bg=COLORS["bg"])
        brand.pack(side="left", padx=12)
        name = tk.Label(brand, text="SAFERIDE", bg=COLORS["bg"], fg=COLORS["text"], anchor="w")
        set_font(name, 14, "bold")
        name.pack(anchor="w")
        product = tk.Label(brand, text="SMART HELMET SAFETY SYSTEM / EXHIBITION BUILD", bg=COLORS["bg"], fg=COLORS["muted"])
        set_font(product, 7, "bold")
        product.pack(anchor="w")
        if setup:
            badge = tk.Label(bar, text="SETUP CONSOLE", bg=COLORS["panel2"], fg=COLORS["cyan"], padx=13, pady=7)
            set_font(badge, 8, "bold")
            badge.pack(side="right")

    def _port_field(self, parent: tk.Widget, label: str, detail: str) -> ttk.Combobox:
        label_widget = tk.Label(parent, text=label, bg=COLORS["panel"], fg=COLORS["text"], anchor="w")
        set_font(label_widget, 9, "bold")
        label_widget.pack(fill="x", pady=(0, 4))
        detail_widget = tk.Label(parent, text=detail, bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
        set_font(detail_widget, 8)
        detail_widget.pack(fill="x", pady=(0, 7))
        combo = ttk.Combobox(parent, state="readonly", style="SafeRide.TCombobox")
        combo.pack(fill="x", pady=(0, 20))
        return combo

    def _setup_log(self, text: str) -> None:
        if not hasattr(self, "setup_log"):
            return
        self.setup_log.configure(state="normal")
        self.setup_log.insert("end", f"> {text}\n")
        self.setup_log.see("end")
        self.setup_log.configure(state="disabled")

    def scan_ports(self) -> None:
        detected = list(list_ports.comports())
        ports = [port for port in detected if "bluetooth" not in port.description.lower()]
        values: list[str] = []
        self.port_map.clear()
        for port in ports:
            label = f"{port.device}  |  {port.description}"
            values.append(label)
            self.port_map[label] = port
        self.helmet_combo["values"] = values
        self.vehicle_combo["values"] = values
        if values:
            self.helmet_combo.current(0)
            self.vehicle_combo.current(1 if len(values) > 1 else 0)
            self._setup_log(f"Found {len(values)} serial port(s).")
            if len(values) >= 2:
                self._set_pipeline(0, "complete", 25)
            else:
                self._set_pipeline(0, "failed", 0)
        else:
            self._setup_log(
                "No serial ports found. Connect both Arduinos with USB data cables and scan again. "
                "If a connected clone board is missing, install its signed CH340/CH341 USB driver."
            )
            self._set_pipeline(0, "waiting", 0)
        skipped = len(detected) - len(ports)
        if skipped:
            self._setup_log(f"Ignored {skipped} Bluetooth virtual port(s); only USB boards are shown.")
        self._update_port_guard()

    def _update_port_guard(self) -> None:
        if not hasattr(self, "guard_label"):
            return
        helmet = self.helmet_combo.get()
        vehicle = self.vehicle_combo.get()
        if not helmet or not vehicle:
            self.guard_label.configure(text="WAITING FOR TWO PORTS", fg=COLORS["muted"])
        elif helmet == vehicle:
            self.guard_label.configure(text="COLLISION: SELECT DIFFERENT PORTS", fg=COLORS["red"])
        else:
            h_port = helmet.split("|")[0].strip()
            v_port = vehicle.split("|")[0].strip()
            self.guard_label.configure(text=f"ACTIVE  /  {h_port} != {v_port}", fg=COLORS["green"])

    def begin_upload(self) -> None:
        helmet_label = self.helmet_combo.get()
        vehicle_label = self.vehicle_combo.get()
        if not helmet_label or not vehicle_label:
            messagebox.showwarning("Select both boards", "Choose a helmet port and a vehicle port first.")
            return
        helmet = self.port_map[helmet_label]
        vehicle = self.port_map[vehicle_label]
        if helmet.device == vehicle.device:
            messagebox.showwarning("Two ports required", "The helmet and vehicle must use different COM ports.")
            return
        if arduino_cli_path() is None:
            messagebox.showerror("Upload engine missing", "Build the complete distribution with tools\\build.ps1 first.")
            return
        try:
            self.device_config.validate()
        except ValueError as exc:
            messagebox.showerror("Configuration needs attention", str(exc))
            self.open_configuration_wizard()
            return
        self._setup_log("Starting automatic firmware upload...")
        self.flash_button.configure(state="disabled", text="FLASHING...")
        self._set_pipeline(0, "complete", 25)
        self._set_pipeline(1, "active", 35)
        threading.Thread(target=self._upload_worker, args=(helmet, vehicle, self.device_config), daemon=True).start()

    def _upload_worker(self, helmet, vehicle, config: SafeRideConfig) -> None:
        active_step = 1
        try:
            with tempfile.TemporaryDirectory(prefix="saferide-firmware-") as folder:
                helmet_sketch, vehicle_sketch = render_firmware(config, Path(folder))
                self.events.put(("setup_log", "Generated firmware from the saved pin and threshold configuration."))
                self.events.put(("setup_log", "Uploading helmet firmware..."))
                upload_sketch(
                    helmet.device, "helmet", lambda line: self.events.put(("setup_log", line)), helmet.description,
                    config.helmet.board, helmet.vid, helmet.pid, helmet_sketch,
                )
                self.events.put(("pipeline", (1, "complete", 50)))
                self.events.put(("pipeline", (2, "active", 60)))
                active_step = 2
                self.events.put(("setup_log", "Uploading vehicle firmware..."))
                upload_sketch(
                    vehicle.device, "vehicle", lambda line: self.events.put(("setup_log", line)), vehicle.description,
                    config.vehicle.board, vehicle.vid, vehicle.pid, vehicle_sketch,
                )
            self.events.put(("pipeline", (2, "complete", 75)))
            self.events.put(("pipeline", (3, "active", 90)))
            self.events.put(("launch_hardware", (helmet.device, vehicle.device)))
        except Exception as exc:
            self.events.put(("pipeline", (active_step, "failed", None)))
            self.events.put(("upload_error", str(exc)))

    def launch_hardware(self, helmet_port: str, vehicle_port: str) -> None:
        try:
            self.bridge = SerialBridge(helmet_port, vehicle_port, lambda kind, payload: self.events.put((kind, payload)))
            self._set_pipeline(3, "complete", 100)
            self.show_dashboard(f"{helmet_port} → {vehicle_port}")
            threading.Thread(target=self.bridge.start, daemon=True).start()
        except Exception as exc:
            messagebox.showerror("Serial connection failed", str(exc))
            self.show_setup()

    def show_dashboard(self, route: str) -> None:
        self.clear()
        self.last_state_key = None
        root = tk.Frame(self, bg=COLORS["bg"], padx=16, pady=10)
        root.pack(fill="both", expand=True)

        system_bar = tk.Frame(root, bg=COLORS["navy"], padx=12, pady=5)
        system_bar.pack(fill="x")
        system_name = tk.Label(system_bar, text="SAFERIDE OS  /  EMBEDDED CONTROL ENVIRONMENT", bg=COLORS["navy"], fg="#e2e8f0")
        set_font(system_name, 8, "bold", "Consolas")
        system_name.pack(side="left")
        self.sync_label = tk.Label(system_bar, text="●  TELEMETRY SYNCHRONIZING", bg=COLORS["navy"], fg="#60a5fa")
        set_font(self.sync_label, 8, "bold", "Consolas")
        self.sync_label.pack(side="right")

        top = tk.Frame(root, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=12, pady=8)
        top.pack(fill="x", pady=(0, 8))
        mark = tk.Label(top, text="SR", width=3, bg=COLORS["cyan"], fg=COLORS["ink"])
        set_font(mark, 12, "bold")
        mark.pack(side="left", ipady=4)
        title_box = tk.Frame(top, bg=COLORS["panel"])
        title_box.pack(side="left", padx=12)
        title = tk.Label(title_box, text="SAFERIDE / LIVE RIDE CONTROL", bg=COLORS["panel"], fg=COLORS["text"])
        set_font(title, 13, "bold")
        title.pack(anchor="w")
        self.route_label = tk.Label(title_box, text=f"HELMET {route} VEHICLE  /  9600 BPS", bg=COLORS["panel"], fg=COLORS["muted"])
        set_font(self.route_label, 7, "bold")
        self.route_label.pack(anchor="w")
        self.clock_label = tk.Label(top, text="", bg=COLORS["panel"], fg=COLORS["text"])
        set_font(self.clock_label, 12, "bold", "Consolas")
        self.clock_label.pack(side="right")
        live = tk.Label(top, text="● LIVE TELEMETRY", bg="#eff6ff", fg=COLORS["cyan"], padx=13, pady=7)
        set_font(live, 8, "bold")
        live.pack(side="right", padx=16)

        cards = tk.Frame(root, bg=COLORS["bg"])
        cards.pack(fill="x")
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform="status")
        self.helmet_card = StatusCard(cards, "Helmet", "Waiting")
        self.alcohol_card = StatusCard(cards, "Alcohol", "Waiting")
        self.drowsy_card = StatusCard(cards, "Rider alertness", "Waiting")
        self.engine_card = StatusCard(cards, "Engine interlock", "Locked")
        for index, item in enumerate((self.helmet_card, self.alcohol_card, self.drowsy_card, self.engine_card)):
            item.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0 if index == 3 else 6))

        content = tk.Frame(root, bg=COLORS["bg"])
        content.pack(fill="both", expand=True, pady=(8, 0))
        content.grid_columnconfigure(0, weight=7)
        content.grid_columnconfigure(1, weight=4)
        content.grid_rowconfigure(0, weight=1)

        left = tk.Frame(content, bg=COLORS["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        left.grid_rowconfigure(0, weight=3)
        left.grid_rowconfigure(1, weight=2)
        left.grid_columnconfigure(0, weight=1)

        threshold = self.device_config.helmet.alcohol_threshold
        chart_card = self._panel(left, "PANEL A  /  ROLLING MQ-3 SENSOR TELEMETRY", f"CHANNEL {self.device_config.helmet.alcohol_pin}  /  RAW ANALOG VALUE  /  LOCK THRESHOLD {threshold} ADC")
        chart_card.grid(row=0, column=0, sticky="nsew", pady=(0, 7))
        chart_inner = chart_card.winfo_children()[-1]
        self.chart = TelemetryChart(chart_inner, threshold)
        self.chart.pack(fill="both", expand=True)
        self.mq_label = tk.Label(chart_inner, text="000", bg=COLORS["panel"], fg=COLORS["cyan"])
        set_font(self.mq_label, 25, "bold", "Consolas")
        self.mq_label.place(relx=0.98, y=0, anchor="ne")

        decision_card = self._panel(left, "PANEL C  /  SAFETY-DECISION INTERLOCK MATRIX", "VEHICLE-SIDE RELAY AUTHORITY")
        decision_card.grid(row=1, column=0, sticky="nsew", pady=(7, 0))
        decision_inner = decision_card.winfo_children()[-1]
        self.decision_title = tk.Label(decision_inner, text="WAITING FOR SENSOR PACKET", bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
        set_font(self.decision_title, 21, "bold")
        self.decision_title.pack(fill="x", pady=(8, 5))
        self.decision_detail = tk.Label(decision_inner, text="The relay stays locked until all checks pass.", bg=COLORS["panel"], fg=COLORS["muted"], anchor="w")
        set_font(self.decision_detail, 10)
        self.decision_detail.pack(fill="x")
        checks = tk.Frame(decision_inner, bg=COLORS["panel"])
        checks.pack(fill="x", pady=(10, 0))
        self.check_labels: dict[str, tk.Label] = {}
        for key, label in (
            ("helmet", "Helmet presence verified"),
            ("alcohol", f"MQ-3 value below {threshold} ADC"),
            ("drowsy", "Rider alertness within limit"),
            ("link", "Helmet to vehicle packet link"),
        ):
            row = tk.Frame(checks, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=8, pady=3)
            row.pack(fill="x", pady=1)
            name = tk.Label(row, text=label, bg=COLORS["panel2"], fg=COLORS["text"], anchor="w")
            set_font(name, 8)
            name.pack(side="left")
            result = tk.Label(row, text="WAIT", bg=COLORS["panel2"], fg=COLORS["muted"], anchor="e")
            set_font(result, 8, "bold", "Consolas")
            result.pack(side="right")
            self.check_labels[key] = result
        self.timeline = tk.Label(decision_inner, text="SYSTEM ARMED  •  FAIL-SAFE DEFAULT: LOCKED", bg=COLORS["panel2"], fg=COLORS["muted"], anchor="w", padx=12, pady=9)
        set_font(self.timeline, 8, "bold", "Consolas")
        self.timeline.pack(fill="x", side="bottom", pady=(10, 0))

        right = tk.Frame(content, bg=COLORS["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right.grid_rowconfigure(0, weight=2)
        right.grid_rowconfigure(1, weight=3)
        right.grid_columnconfigure(0, weight=1)

        link_card = self._panel(right, "PANEL B  /  HELMET → VEHICLE LINK", "LIVE BIDIRECTIONAL SAFETY PACKET CHANNEL")
        link_card.grid(row=0, column=0, sticky="nsew", pady=(0, 7))
        link_inner = link_card.winfo_children()[-1]
        self.link_visual = LinkVisualizer(link_inner)
        self.link_visual.pack(fill="both", expand=True)
        log_card = self._panel(right, "PANEL D  /  RAW SERIAL PACKET STREAM", "HELMET AND VEHICLE DATA  /  AUTO-SCROLL")
        log_card.grid(row=1, column=0, sticky="nsew", pady=(7, 0))
        log_inner = log_card.winfo_children()[-1]
        self.raw_log = tk.Text(log_inner, width=1, height=1, bg=COLORS["console"], fg="#cbd5e1", relief="flat", bd=0, padx=10, pady=8,
                               state="disabled", wrap="none", selectbackground=COLORS["cyan2"])
        set_font(self.raw_log, 8, family="Consolas")
        self.raw_log.pack(fill="both", expand=True)
        self.raw_log.tag_configure("helmet", foreground="#60a5fa")
        self.raw_log.tag_configure("vehicle", foreground="#4ade80")
        self.raw_log.tag_configure("time", foreground="#64748b")
        self.raw_log.tag_configure("danger", foreground="#f87171")
        self._update_clock()

    def _panel(self, parent: tk.Widget, title: str, subtitle: str) -> tk.Frame:
        panel = tk.Frame(parent, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1, padx=12, pady=9)
        header = tk.Frame(panel, bg=COLORS["panel2"], highlightbackground="#e2e8f0", highlightthickness=1, padx=8, pady=5)
        header.pack(fill="x")
        title_widget = tk.Label(header, text=title, bg=COLORS["panel2"], fg=COLORS["text"], anchor="w")
        set_font(title_widget, 9, "bold")
        title_widget.pack(anchor="w")
        subtitle_widget = tk.Label(header, text=subtitle, bg=COLORS["panel2"], fg=COLORS["muted"], anchor="w")
        set_font(subtitle_widget, 7, "bold")
        subtitle_widget.pack(anchor="w", pady=(2, 0))
        inner = tk.Frame(panel, bg=COLORS["panel"])
        inner.pack(fill="both", expand=True)
        return panel

    def _update_clock(self) -> None:
        if hasattr(self, "clock_label") and self.clock_label.winfo_exists():
            self.clock_label.configure(text=time.strftime("%H:%M:%S"))
            self.after(1000, self._update_clock)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "setup_log":
                    self._setup_log(str(payload))
                elif kind == "pipeline":
                    index, state, progress = payload
                    self._set_pipeline(index, state, progress)
                elif kind == "launch_hardware":
                    self.launch_hardware(*payload)
                elif kind == "upload_error":
                    self._setup_log(f"ERROR: {payload}")
                    if hasattr(self, "flash_button") and self.flash_button.winfo_exists():
                        self.flash_button.configure(state="normal", text="FLASH + LAUNCH")
                    messagebox.showerror("Firmware upload failed", str(payload))
                elif kind == "update_checked":
                    self._handle_update_checked(*payload)
                elif kind == "update_ready":
                    self._handle_update_ready(*payload)
                elif kind == "update_error":
                    text, interactive = payload
                    self._update_busy = False
                    self._set_update_button("CHECK UPDATE")
                    if interactive:
                        messagebox.showerror("SafeRide update failed", text, parent=self)
                elif kind == "raw" and hasattr(self, "raw_log") and self.raw_log.winfo_exists():
                    source, line = payload
                    self._append_raw(source, line)
                elif kind in ("helmet", "vehicle") and hasattr(self, "chart") and self.chart.winfo_exists():
                    self._apply_telemetry(payload, authoritative=(kind == "vehicle"))
                elif kind == "error":
                    if hasattr(self, "raw_log") and self.raw_log.winfo_exists():
                        self._append_raw("ERROR", str(payload))
        except queue.Empty:
            pass
        self.after(60, self._drain_events)

    def _append_raw(self, source: str, line: str) -> None:
        self.raw_count += 1
        self.raw_log.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.raw_log.insert("end", timestamp + "  ", "time")
        tag = "helmet" if source == "HELMET" else ("vehicle" if source == "VEHICLE" else "danger")
        self.raw_log.insert("end", f"{source:<7} ", tag)
        self.raw_log.insert("end", line + "\n")
        if int(self.raw_log.index("end-1c").split(".")[0]) > 140:
            self.raw_log.delete("1.0", "20.0")
        self.raw_log.see("end")
        self.raw_log.configure(state="disabled")

    def _apply_telemetry(self, data: Telemetry, authoritative: bool) -> None:
        if authoritative or data.engine is None:
            self.latest = data
        self.chart.push(data.mq3)
        self.mq_label.configure(text=f"{data.mq3:03d}")
        self.helmet_card.update_status("WORN" if data.helmet else "NOT WORN", f"Presence sensor D{self.device_config.helmet.helmet_ir_pin}", data.helmet)
        self.alcohol_card.update_status("DETECTED" if data.alcohol else "CLEAR", f"MQ-3 value {data.mq3} / {self.device_config.helmet.alcohol_threshold}", not data.alcohol)
        self.drowsy_card.update_status(
            "DROWSY" if data.drowsy else "ALERT",
            f"Eye-close window {self.device_config.helmet.drowsy_limit_ms / 1000:g} s",
            not data.drowsy,
        )
        engine = data.engine if data.engine is not None else (data.helmet and not data.alcohol and not data.drowsy)
        self.engine_card.update_status("UNLOCKED" if engine else "LOCKED", f"Relay output D{self.device_config.vehicle.relay_pin}", bool(engine))
        self.link_visual.set_active(data.link is not False)
        if hasattr(self, "sync_label"):
            online = data.link is not False
            self.sync_label.configure(
                text="●  TELEMETRY SYNCHRONIZED" if online else "●  TELEMETRY LINK LOST",
                fg="#4ade80" if online else "#f87171",
            )
        check_states = {
            "helmet": (data.helmet, "PASS" if data.helmet else "FAIL"),
            "alcohol": (not data.alcohol, f"{data.mq3} ADC  /  " + ("PASS" if not data.alcohol else "FAIL")),
            "drowsy": (not data.drowsy, "PASS" if not data.drowsy else "FAIL"),
            "link": (data.link is not False, "ONLINE" if data.link is not False else "OFFLINE"),
        }
        for key, (passed, text) in check_states.items():
            self.check_labels[key].configure(text=("[✓] " if passed else "[X] ") + text, fg=COLORS["green"] if passed else COLORS["red"])
        reason = engine_reason(data)
        self.decision_title.configure(text="ENGINE ENABLED" if engine else "ENGINE LOCKED", fg=COLORS["green"] if engine else COLORS["red"])
        self.decision_detail.configure(text=reason + "." if not reason.endswith(".") else reason)
        state_key = (data.helmet, data.alcohol, data.drowsy, engine, data.link)
        if state_key != self.last_state_key:
            stamp = time.strftime("%H:%M:%S")
            action = "RELAY ON" if engine else "RELAY OFF"
            self.timeline.configure(text=f"{stamp}  •  {action}  •  {reason.upper()}", fg=COLORS["green"] if engine else COLORS["red"])
            self.last_state_key = state_key

    def close(self) -> None:
        if self.bridge:
            self.bridge.close()
        self.destroy()


if __name__ == "__main__":
    SafeRideApp().mainloop()

