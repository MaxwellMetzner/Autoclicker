import tkinter as tk
from tkinter import messagebox
from threading import Thread, Event, Lock
import time
import logging
from typing import Dict, Optional
import sys
import ctypes
from ctypes import wintypes
from pathlib import Path

# Debug mode configuration - set to False to hide console
DEBUG_MODE = False

# Windows API constants
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# Hide console window in production mode (Windows only)
if not DEBUG_MODE and sys.platform == 'win32':
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# Configure logging
if DEBUG_MODE:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hotkey behavior
HOTKEY_ARM_DELAY = 0.35
HOTKEY_POLL_INTERVAL = 0.02
MIN_INTERVAL = 0.001
MAX_INTERVAL = 60.0
STATUS_TOOLTIP_DELAY_MS = 350

# Window integration
APP_ID = "MaxwellMetzner.AutoClicker"
ICON_FILES = ("logo_16x16.png", "logo_32x32.png", "logo_64x64.png")
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

# Color scheme
COLORS = {
    "bg": "#0b0f14",
    "panel": "#11161d",
    "panel_alt": "#171d26",
    "title_bar": "#0f141a",
    "border": "#263241",
    "entry_bg": "#0c1117",
    "button_idle": "#101720",
    "button_hover": "#1a2430",
    "pill_bg": "#14202b",
    "fg": "#f4f7fb",
    "muted": "#8a98ab",
    "accent": "#7dd3fc",
    "accent_hover": "#54b9e8",
    "success": "#2fbf71",
    "success_hover": "#25a260",
    "warning": "#f4b740",
    "error": "#f87171",
    "error_hover": "#df5e5e",
    "badge_muted": "#1a2330",
    "badge_success": "#163424",
    "badge_warning": "#3b2c12",
    "badge_error": "#3f1d1d",
}

STATUS_STYLES = {
    "muted": {"fg": COLORS["muted"], "bg": COLORS["badge_muted"]},
    "success": {"fg": COLORS["success"], "bg": COLORS["badge_success"]},
    "warning": {"fg": COLORS["warning"], "bg": COLORS["badge_warning"]},
    "error": {"fg": COLORS["error"], "bg": COLORS["badge_error"]},
}

class AutoClicker:
    def __init__(self, master):
        self.master = master
        self.master.title("AutoClicker")
        self.master.configure(bg=COLORS["border"])
        self.master.resizable(False, False)
        self.master.attributes("-topmost", True)

        self.clicking = False
        self.stop_event = Event()
        self.hotkey: Optional[str] = None
        self.thread_lock = Lock()
        self.click_thread: Optional[Thread] = None
        self.clicks_performed = 0
        self.session_start_time: Optional[float] = None
        self.click_type = "left"
        self.shutdown_event = Event()
        self.hotkey_vk: Optional[int] = None
        self.hotkey_pressed_last = False
        self.hotkey_capture_active = False
        self.hotkey_disabled_until = 0.0
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.click_type_buttons: Dict[str, tk.Button] = {}
        self.base_dir = Path(__file__).resolve().parent
        self.icon_images = []
        self.title_logo_image = None
        self.window_handle = None
        self.saved_geometry = ""
        self.restore_job = None
        self.status_tooltip_text = ""
        self.status_tooltip_window = None
        self.status_tooltip_label = None
        self.status_tooltip_after_id = None
        self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        self.get_window_long = getattr(self.user32, "GetWindowLongPtrW", self.user32.GetWindowLongW)
        self.set_window_long = getattr(self.user32, "SetWindowLongPtrW", self.user32.SetWindowLongW)

        self._configure_windows_api()
        self._load_logo_assets()

        self._build_window()
        self._bind_status_tooltip(self.title_badge)
        self._bind_status_tooltip(self.status_label)
        self._set_status("Ready", "muted", badge="READY")
        self._sync_control_card_heights()
        self._update_click_type_buttons()
        self._update_action_buttons()

        self.master.update_idletasks()
        width = max(340, self.window_frame.winfo_reqwidth() + 2)
        height = self.window_frame.winfo_reqheight() + 2
        self.master.geometry(f"{width}x{height}")
        self.master.minsize(width, height)
        self.saved_geometry = self.master.geometry()
        self.master.overrideredirect(True)
        self.master.bind("<Map>", self._on_map)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.master.after(0, self._force_taskbar_presence)

        self.listener_thread = Thread(target=self.hotkey_listener, daemon=True)
        self.listener_thread.start()

        logger.info("AutoClicker initialized")

    def _build_window(self):
        self.window_frame = tk.Frame(self.master, bg=COLORS["panel"])
        self.window_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        title_bar = tk.Frame(self.window_frame, bg=COLORS["title_bar"], height=34)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        title_left = tk.Frame(title_bar, bg=COLORS["title_bar"])
        title_left.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        if self.title_logo_image is not None:
            title_logo = tk.Label(
                title_left,
                image=self.title_logo_image,
                bg=COLORS["title_bar"],
                bd=0,
                highlightthickness=0,
            )
            title_logo.pack(side=tk.LEFT, pady=7, padx=(0, 8))
        else:
            title_logo = None

        title_label = tk.Label(
            title_left,
            text="AutoClicker",
            bg=COLORS["title_bar"],
            fg=COLORS["fg"],
            font=("Segoe UI", 9, "bold"),
        )
        title_label.pack(side=tk.LEFT, pady=7)

        self.title_badge = tk.Label(
            title_left,
            text="READY",
            bg=STATUS_STYLES["muted"]["bg"],
            fg=STATUS_STYLES["muted"]["fg"],
            font=("Segoe UI", 7, "bold"),
            padx=8,
            pady=3,
        )
        self.title_badge.pack(side=tk.LEFT, padx=(8, 0), pady=5)

        window_actions = tk.Frame(title_bar, bg=COLORS["title_bar"])
        window_actions.pack(side=tk.RIGHT, fill=tk.Y)

        self.minimize_btn = tk.Button(
            window_actions,
            text="_",
            command=self.minimize_window,
            width=4,
            bg=COLORS["title_bar"],
            fg=COLORS["muted"],
            relief=tk.FLAT,
            bd=0,
            padx=0,
            pady=0,
            cursor="hand2",
            font=("Segoe UI", 14, "bold"),
            activebackground=COLORS["button_hover"],
            activeforeground=COLORS["fg"],
            highlightthickness=0,
        )
        self.minimize_btn.pack(side=tk.LEFT, fill=tk.Y)

        self.close_btn = tk.Button(
            window_actions,
            text="X",
            command=self.on_close,
            width=4,
            bg=COLORS["title_bar"],
            fg=COLORS["muted"],
            relief=tk.FLAT,
            bd=0,
            padx=0,
            pady=0,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            activebackground=COLORS["error_hover"],
            activeforeground=COLORS["fg"],
            highlightthickness=0,
        )
        self.close_btn.pack(side=tk.LEFT, fill=tk.Y)

        for widget in (title_bar, title_left, title_logo, title_label, self.title_badge):
            if widget is None:
                continue
            self._bind_drag(widget)

        body = tk.Frame(self.window_frame, bg=COLORS["panel"])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 10))

        controls_row = tk.Frame(body, bg=COLORS["panel"])
        controls_row.pack(fill=tk.X)
        controls_row.columnconfigure(0, weight=3)
        controls_row.columnconfigure(1, weight=2)

        self.type_card = self._create_card(controls_row)
        self.type_card.grid(row=0, column=0, sticky="nsew", padx=(0, 3))

        tk.Label(
            self.type_card,
            text="Click Button",
            bg=COLORS["panel_alt"],
            fg=COLORS["fg"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        button_row = tk.Frame(self.type_card, bg=COLORS["panel_alt"])
        button_row.pack(fill=tk.X, expand=True, pady=(6, 0))

        for index, (label, value) in enumerate((("Left", "left"), ("Right", "right"), ("Middle", "middle"))):
            button = tk.Button(
                button_row,
                text=label,
                command=lambda selected=value: self._set_click_type(selected),
                bg=COLORS["button_idle"],
                fg=COLORS["muted"],
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=5,
                cursor="hand2",
                font=("Segoe UI", 8, "bold"),
                activebackground=COLORS["button_hover"],
                activeforeground=COLORS["fg"],
                highlightthickness=0,
            )
            button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0 if index == 0 else 4, 0))
            self.click_type_buttons[value] = button

        self.interval_card = self._create_card(controls_row)
        self.interval_card.grid(row=0, column=1, sticky="nsew", padx=(3, 0))

        tk.Label(
            self.interval_card,
            text="Interval",
            bg=COLORS["panel_alt"],
            fg=COLORS["fg"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        interval_shell = tk.Frame(
            self.interval_card,
            bg=COLORS["entry_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
        )
        interval_shell.pack(fill=tk.X, expand=True, pady=(6, 0), ipady=1)

        self.interval_entry = tk.Entry(
            interval_shell,
            font=("Segoe UI", 10),
            width=8,
            bg=COLORS["entry_bg"],
            fg=COLORS["fg"],
            relief=tk.FLAT,
            bd=0,
            justify="center",
            insertbackground=COLORS["fg"],
        )
        self.interval_entry.insert(0, "0.01")
        self.interval_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 4), pady=7)

        tk.Label(
            interval_shell,
            text="SEC",
            bg=COLORS["entry_bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 7, "bold"),
        ).pack(side=tk.RIGHT, padx=(0, 10), pady=7)

        hotkey_card = self._create_card(body)
        hotkey_card.pack(fill=tk.X, pady=(6, 6))

        tk.Label(
            hotkey_card,
            text="Toggle Hotkey",
            bg=COLORS["panel_alt"],
            fg=COLORS["fg"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        hotkey_row = tk.Frame(hotkey_card, bg=COLORS["panel_alt"])
        hotkey_row.pack(fill=tk.X, pady=(6, 0))

        self.hotkey_label_text = tk.StringVar(value="NOT SET")
        self.hotkey_label = tk.Label(
            hotkey_row,
            textvariable=self.hotkey_label_text,
            bg=COLORS["pill_bg"],
            fg=COLORS["accent"],
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=7,
            anchor="w",
        )
        self.hotkey_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.set_hotkey_btn = tk.Button(
            hotkey_row,
            text="Set Hotkey",
            command=self.set_hotkey,
            bg=COLORS["accent"],
            fg=COLORS["title_bar"],
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["title_bar"],
            highlightthickness=0,
        )
        self.set_hotkey_btn.pack(side=tk.LEFT, padx=(8, 0))

        action_row = tk.Frame(body, bg=COLORS["panel"])
        action_row.pack(fill=tk.X)

        self.start_btn = tk.Button(
            action_row,
            text="Start",
            command=self.start_clicking,
            bg=COLORS["success"],
            fg=COLORS["fg"],
            relief=tk.FLAT,
            bd=0,
            padx=0,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            activebackground=COLORS["success_hover"],
            activeforeground=COLORS["fg"],
            disabledforeground=COLORS["muted"],
            highlightthickness=0,
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.stop_btn = tk.Button(
            action_row,
            text="Stop",
            command=self.stop_clicking,
            bg=COLORS["button_idle"],
            fg=COLORS["muted"],
            relief=tk.FLAT,
            bd=0,
            padx=0,
            pady=8,
            cursor="arrow",
            font=("Segoe UI", 9, "bold"),
            activebackground=COLORS["error_hover"],
            activeforeground=COLORS["fg"],
            disabledforeground=COLORS["muted"],
            highlightthickness=0,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.status_label = tk.Label(
            body,
            text="Ready",
            font=("Segoe UI", 8),
            fg=COLORS["muted"],
            bg=COLORS["panel"],
            anchor="w",
        )

    def _create_card(self, parent):
        return tk.Frame(
            parent,
            bg=COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["border"],
            bd=0,
            padx=9,
            pady=9,
        )

    def _sync_control_card_heights(self):
        self.window_frame.update_idletasks()
        target_height = max(self.type_card.winfo_reqheight(), self.interval_card.winfo_reqheight())

        for card in (self.type_card, self.interval_card):
            card.grid_propagate(False)
            card.config(height=target_height)

    def _bind_status_tooltip(self, widget):
        widget.bind("<Enter>", self._schedule_status_tooltip)
        widget.bind("<Leave>", self._hide_status_tooltip)
        widget.bind("<ButtonPress-1>", self._hide_status_tooltip)
        widget.bind("<Motion>", self._move_status_tooltip)

    def _schedule_status_tooltip(self, event=None):
        self._cancel_status_tooltip()
        if not self.status_tooltip_text:
            return

        self.status_tooltip_after_id = self.master.after(STATUS_TOOLTIP_DELAY_MS, self._show_status_tooltip)

    def _cancel_status_tooltip(self):
        if self.status_tooltip_after_id is not None:
            self.master.after_cancel(self.status_tooltip_after_id)
            self.status_tooltip_after_id = None

    def _show_status_tooltip(self):
        self.status_tooltip_after_id = None
        if not self.status_tooltip_text:
            return

        if self.status_tooltip_window is None:
            self.status_tooltip_window = tk.Toplevel(self.master)
            self.status_tooltip_window.overrideredirect(True)
            self.status_tooltip_window.attributes("-topmost", True)
            self.status_tooltip_window.configure(bg=COLORS["border"])

            self.status_tooltip_label = tk.Label(
                self.status_tooltip_window,
                text=self.status_tooltip_text,
                bg=COLORS["panel_alt"],
                fg=COLORS["fg"],
                font=("Segoe UI", 8),
                justify=tk.LEFT,
                wraplength=260,
                padx=8,
                pady=6,
            )
            self.status_tooltip_label.pack(padx=1, pady=1)
        elif self.status_tooltip_label is not None:
            self.status_tooltip_label.config(text=self.status_tooltip_text)

        self._move_status_tooltip()

    def _move_status_tooltip(self, event=None):
        if self.status_tooltip_window is None:
            return

        if event is None:
            x_pos = self.master.winfo_pointerx() + 12
            y_pos = self.master.winfo_pointery() + 16
        else:
            x_pos = event.x_root + 12
            y_pos = event.y_root + 16

        self.status_tooltip_window.geometry(f"+{x_pos}+{y_pos}")

    def _hide_status_tooltip(self, event=None):
        self._cancel_status_tooltip()
        if self.status_tooltip_window is not None:
            self.status_tooltip_window.destroy()
            self.status_tooltip_window = None
            self.status_tooltip_label = None

    def _configure_windows_api(self):
        self.get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        self.get_window_long.restype = wintypes.LPARAM
        self.set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LPARAM]
        self.set_window_long.restype = wintypes.LPARAM
        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL
        self.shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
        self.shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long

    def _load_logo_assets(self):
        self.icon_images = []

        for icon_name in ICON_FILES:
            icon_path = self.base_dir / icon_name
            if not icon_path.exists():
                continue

            try:
                self.icon_images.append(tk.PhotoImage(file=str(icon_path)))
            except tk.TclError as error:
                logger.error(f"Failed to load icon {icon_name}: {error}")

        self.title_logo_image = self.icon_images[0] if self.icon_images else None

        if self.icon_images:
            try:
                self.master.iconphoto(True, *self.icon_images)
            except tk.TclError as error:
                logger.error(f"Failed to apply window icons: {error}")

    def _bind_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_window_move)
        widget.bind("<B1-Motion>", self._move_window)

    def _start_window_move(self, event):
        self.drag_offset_x = event.x_root
        self.drag_offset_y = event.y_root

    def _move_window(self, event):
        delta_x = event.x_root - self.drag_offset_x
        delta_y = event.y_root - self.drag_offset_y
        new_x = self.master.winfo_x() + delta_x
        new_y = self.master.winfo_y() + delta_y
        self.master.geometry(f"+{new_x}+{new_y}")
        self.drag_offset_x = event.x_root
        self.drag_offset_y = event.y_root

    def _hwnd(self):
        try:
            return int(self.master.wm_frame(), 0)
        except (TypeError, ValueError, tk.TclError):
            return self.master.winfo_id()

    def _force_taskbar_presence(self):
        self.master.update_idletasks()
        self.saved_geometry = self.master.geometry()
        self.window_handle = self._hwnd()

        try:
            self.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except OSError as error:
            logger.error(f"Failed to set app model ID: {error}")

        try:
            extended_style = self.get_window_long(self.window_handle, GWL_EXSTYLE)
            taskbar_style = (extended_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            if taskbar_style != extended_style:
                self.set_window_long(self.window_handle, GWL_EXSTYLE, taskbar_style)

            self.user32.SetWindowPos(
                self.window_handle,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
        except OSError as error:
            logger.error(f"Failed to apply taskbar window style: {error}")

        self.master.withdraw()
        self.master.after(10, self._restore_after_taskbar_refresh)

    def _restore_after_taskbar_refresh(self):
        if self.saved_geometry:
            self.master.geometry(self.saved_geometry)

        self.master.deiconify()

    def _on_map(self, event=None):
        if event is not None and event.widget is not self.master:
            return

        if self.master.state() != "normal":
            return

        if self.restore_job is not None:
            self.master.after_cancel(self.restore_job)

        self.restore_job = self.master.after(10, self._restore_borderless_mode)

    def _restore_borderless_mode(self):
        self.restore_job = None
        if self.master.state() != "normal":
            return

        current_geometry = self.saved_geometry or self.master.geometry()
        self.master.overrideredirect(True)
        if current_geometry:
            self.master.geometry(current_geometry)

        self.master.attributes("-topmost", True)
        self.master.update_idletasks()
        self._sync_control_card_heights()

    def minimize_window(self):
        self.saved_geometry = self.master.geometry()
        self.master.attributes("-topmost", True)
        self.master.overrideredirect(False)
        self.master.iconify()

    def _set_status(self, text, tone="muted", badge=None, detail=None):
        style = STATUS_STYLES.get(tone, STATUS_STYLES["muted"])
        badge_text = badge if badge is not None else tone.upper()
        self.title_badge.config(text=badge_text, fg=style["fg"], bg=style["bg"])

        show_detail = text.strip().lower() != "ready"
        self.status_label.config(text=text if show_detail else "", fg=style["fg"])
        self.status_tooltip_text = (detail or text) if show_detail else ""

        if show_detail:
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, pady=(6, 0))
        elif self.status_label.winfo_manager():
            self.status_label.pack_forget()

        if self.status_tooltip_window is not None:
            if self.status_tooltip_text and self.status_tooltip_label is not None:
                self.status_tooltip_label.config(text=self.status_tooltip_text)
                self._move_status_tooltip()
            else:
                self._hide_status_tooltip()

    def _format_interval(self, interval):
        return f"{interval:.3f}".rstrip("0").rstrip(".")

    def _set_interval_entry_value(self, interval):
        self.interval_entry.delete(0, tk.END)
        self.interval_entry.insert(0, self._format_interval(interval))

    def _normalize_interval(self, interval_text):
        interval = float(interval_text)
        detail = None

        if interval < MIN_INTERVAL:
            detail = (
                f"Requested interval {interval_text} seconds is below the supported minimum. "
                f"The app adjusted it to {self._format_interval(MIN_INTERVAL)} seconds."
            )
            interval = MIN_INTERVAL
        elif interval > MAX_INTERVAL:
            detail = (
                f"Requested interval {interval_text} seconds is above the supported maximum. "
                f"The app adjusted it to {self._format_interval(MAX_INTERVAL)} seconds."
            )
            interval = MAX_INTERVAL

        return interval, detail

    def _set_click_type(self, click_type):
        self.click_type = click_type
        self._update_click_type_buttons()
        logger.info(f"Click type changed to: {self.click_type}")

    def _update_click_type_buttons(self):
        for button_type, button in self.click_type_buttons.items():
            is_selected = button_type == self.click_type
            button.config(
                bg=COLORS["accent"] if is_selected else COLORS["button_idle"],
                fg=COLORS["title_bar"] if is_selected else COLORS["muted"],
                activebackground=COLORS["accent_hover"] if is_selected else COLORS["button_hover"],
                activeforeground=COLORS["title_bar"] if is_selected else COLORS["fg"],
            )

    def _update_action_buttons(self):
        if self.clicking:
            self.start_btn.config(
                state=tk.DISABLED,
                bg=COLORS["button_idle"],
                fg=COLORS["muted"],
                disabledforeground=COLORS["muted"],
                cursor="arrow",
            )
            self.stop_btn.config(
                state=tk.NORMAL,
                bg=COLORS["error"],
                fg=COLORS["fg"],
                activebackground=COLORS["error_hover"],
                activeforeground=COLORS["fg"],
                cursor="hand2",
            )
        else:
            self.start_btn.config(
                state=tk.NORMAL,
                bg=COLORS["success"],
                fg=COLORS["fg"],
                activebackground=COLORS["success_hover"],
                activeforeground=COLORS["fg"],
                cursor="hand2",
            )
            self.stop_btn.config(
                state=tk.DISABLED,
                bg=COLORS["button_idle"],
                fg=COLORS["muted"],
                disabledforeground=COLORS["muted"],
                cursor="arrow",
            )

    def set_hotkey(self):
        if self.hotkey_capture_active:
            return

        self.hotkey_capture_active = True
        self.hotkey_label_text.set("LISTENING")
        self.set_hotkey_btn.config(
            text="Press Key",
            state=tk.DISABLED,
            bg=COLORS["accent_hover"],
            fg=COLORS["title_bar"],
            cursor="arrow",
        )
        self._set_status("Press any supported key", "warning", badge="LISTEN")
        self.master.update_idletasks()
        self.master.focus_force()
        self.master.bind("<KeyPress>", self._capture_hotkey)

    def _finish_hotkey_capture(self):
        self.hotkey_capture_active = False
        self.master.unbind("<KeyPress>")
        self.set_hotkey_btn.config(
            text="Set Hotkey",
            state=tk.NORMAL,
            bg=COLORS["accent"],
            fg=COLORS["title_bar"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["title_bar"],
            cursor="hand2",
        )

    def _capture_hotkey(self, event):
        finish_capture = False

        try:
            if not self.hotkey_capture_active:
                return

            vk_code, display_name = self._event_to_vk(event)
            if vk_code is None or display_name is None:
                self._set_status("Unsupported key, try another", "error", badge="ERROR")
                return

            self.hotkey = display_name
            self.hotkey_vk = vk_code
            self.hotkey_disabled_until = time.monotonic() + HOTKEY_ARM_DELAY
            self.hotkey_pressed_last = True
            self.hotkey_label_text.set(display_name.upper())
            self._set_status(f"Hotkey armed: {display_name.upper()}", "success", badge="ARMED")
            logger.info(f"Hotkey set to: {display_name} (VK={vk_code})")
            finish_capture = True
        except Exception as e:
            logger.error(f"Error setting hotkey: {e}")
            self.hotkey_label_text.set(self.hotkey.upper() if self.hotkey else "NOT SET")
            self._set_status(f"Error: {e}", "error", badge="ERROR")
            messagebox.showerror("Error", f"Failed to set hotkey: {e}")
            finish_capture = True
        finally:
            if finish_capture:
                self._finish_hotkey_capture()

    def _event_to_vk(self, event):
        keysym = (event.keysym or "").strip()
        if not keysym:
            return None, None

        if len(keysym) == 1:
            key = keysym.upper()
            if "A" <= key <= "Z" or "0" <= key <= "9":
                return ord(key), key

        named_keys = {
            "space": (0x20, "Space"),
            "Tab": (0x09, "Tab"),
            "Return": (0x0D, "Enter"),
            "Escape": (0x1B, "Esc"),
            "BackSpace": (0x08, "Backspace"),
            "Up": (0x26, "Up"),
            "Down": (0x28, "Down"),
            "Left": (0x25, "Left"),
            "Right": (0x27, "Right"),
            "Insert": (0x2D, "Insert"),
            "Delete": (0x2E, "Delete"),
            "Home": (0x24, "Home"),
            "End": (0x23, "End"),
            "Prior": (0x21, "PageUp"),
            "Next": (0x22, "PageDown"),
        }

        if keysym in named_keys:
            return named_keys[keysym]

        if keysym.startswith("F") and keysym[1:].isdigit():
            fn_number = int(keysym[1:])
            if 1 <= fn_number <= 24:
                return 0x6F + fn_number, f"F{fn_number}"

        return None, None

    def toggle_clicking(self):
        try:
            if self.clicking:
                self.stop_clicking()
            else:
                self.start_clicking()
        except Exception as e:
            logger.error(f"Error toggling clicking: {e}")
            self._set_status(f"Error: {e}", "error", badge="ERROR")

    def start_clicking(self):
        try:
            interval_str = self.interval_entry.get().strip()
            if not interval_str:
                self._set_status(
                    "Enter an interval",
                    "error",
                    badge="ERROR",
                    detail=(
                        f"Interval is required. Enter a value between "
                        f"{self._format_interval(MIN_INTERVAL)} and {self._format_interval(MAX_INTERVAL)} seconds."
                    ),
                )
                return

            interval, interval_detail = self._normalize_interval(interval_str)
            if interval_detail:
                self._set_interval_entry_value(interval)
        except ValueError:
            self._set_status(
                "Invalid number",
                "error",
                badge="ERROR",
                detail=(
                    f"Interval must be a number between "
                    f"{self._format_interval(MIN_INTERVAL)} and {self._format_interval(MAX_INTERVAL)} seconds."
                ),
            )
            logger.error(f"Invalid interval entered: {self.interval_entry.get()}")
            return

        with self.thread_lock:
            if self.clicking:
                logger.warning("Already clicking")
                return

            self.clicking = True
            self.stop_event.clear()
            self.clicks_performed = 0
            self.session_start_time = time.time()
            status_text = f"Clicking... ({self._format_interval(interval)}s)" if interval_detail else "Clicking..."
            status_detail = interval_detail or f"Current interval: {self._format_interval(interval)} seconds."
            self._set_status(status_text, "success", badge="LIVE", detail=status_detail)
            self._update_action_buttons()
            self.click_thread = Thread(target=self.click_loop, args=(interval,), daemon=True)
            self.click_thread.start()
            logger.info(f"Clicking started with interval: {interval}s")

    def stop_clicking(self):
        with self.thread_lock:
            if not self.clicking:
                logger.warning("Not currently clicking")
                return

            self.clicking = False
            self.stop_event.set()
            self.session_start_time = None
            self._set_status("Stopped", "warning", badge="IDLE")
            self._update_action_buttons()
            logger.info("Clicking stopped")

    def _handle_click_loop_failure(self, error_text):
        with self.thread_lock:
            self.clicking = False
            self.stop_event.set()
            self.session_start_time = None

        self._update_action_buttons()
        self._set_status(f"Error: {error_text}", "error", badge="ERROR")

    def click_loop(self, interval):
        try:
            while not self.stop_event.is_set():
                try:
                    if self._is_cursor_in_corner():
                        logger.warning("FailSafe triggered - mouse at corner")
                        self.master.after(0, self.stop_clicking)
                        self.master.after(0, lambda: self._set_status("Emergency stop", "error", badge="SAFE"))
                        break

                    self._native_click(self.click_type)
                    self.clicks_performed += 1
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Error during click: {e}")
                    self.master.after(0, self.stop_clicking)
                    self.master.after(0, lambda error_text=str(e): self._set_status(f"Click error: {error_text}", "error", badge="ERROR"))
                    break

            logger.info(f"Click loop ended. Total clicks: {self.clicks_performed}")
        except Exception as e:
            logger.error(f"Click loop crashed: {e}")
            self.master.after(0, lambda error_text=str(e): self._handle_click_loop_failure(error_text))

    def hotkey_listener(self):
        try:
            while not self.shutdown_event.is_set():
                try:
                    if self.hotkey_capture_active:
                        self.hotkey_pressed_last = False
                    elif self.hotkey_vk is not None:
                        key_state = self.user32.GetAsyncKeyState(self.hotkey_vk)
                        is_pressed = (key_state & 0x8000) != 0

                        if time.monotonic() < self.hotkey_disabled_until:
                            self.hotkey_pressed_last = is_pressed
                        else:
                            if is_pressed and not self.hotkey_pressed_last:
                                self.master.after(0, self.toggle_clicking)

                            self.hotkey_pressed_last = is_pressed
                    else:
                        self.hotkey_pressed_last = False
                except Exception as e:
                    logger.error(f"Hotkey polling error: {e}")

                time.sleep(HOTKEY_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Hotkey listener error: {e}")

    def _native_click(self, click_type):
        if click_type == "left":
            flags = MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP
        elif click_type == "right":
            flags = MOUSEEVENTF_RIGHTDOWN | MOUSEEVENTF_RIGHTUP
        elif click_type == "middle":
            flags = MOUSEEVENTF_MIDDLEDOWN | MOUSEEVENTF_MIDDLEUP
        else:
            raise ValueError(f"Unsupported click type: {click_type}")

        if self.user32.mouse_event(flags, 0, 0, 0, 0) == 0:
            error_code = ctypes.GetLastError()
            raise OSError(f"mouse_event failed with error code {error_code}")

    def _is_cursor_in_corner(self):
        point = wintypes.POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            return False

        width = self.user32.GetSystemMetrics(0) - 1
        height = self.user32.GetSystemMetrics(1) - 1
        threshold = 1

        return (
            (point.x <= threshold and point.y <= threshold) or
            (point.x >= width - threshold and point.y <= threshold) or
            (point.x <= threshold and point.y >= height - threshold) or
            (point.x >= width - threshold and point.y >= height - threshold)
        )

    def on_close(self):
        try:
            self.shutdown_event.set()
            self.hotkey_capture_active = False
            self.master.unbind("<KeyPress>")
            self.stop_clicking()
        finally:
            self.master.destroy()

# Run app
if __name__ == "__main__":
    try:
        root = tk.Tk()
        root.withdraw()
        app = AutoClicker(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
