import tkinter as tk
from tkinter import messagebox, ttk
from threading import Thread, Event, Lock
import time
import logging
from typing import Optional
import sys
import ctypes
from ctypes import wintypes

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

# Color scheme
COLORS = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "accent": "#007acc",
    "accent_hover": "#005a9e",
    "success": "#4ec9b0",
    "warning": "#dcdcaa",
    "error": "#f48771",
    "inactive": "#505050",
    "card_bg": "#2d2d2d",
}

class AutoClicker:
    def __init__(self, master):
        self.master = master
        self.master.title("AutoClicker")
        self.master.configure(bg=COLORS["bg"])
        self.master.resizable(False, False)
        self.master.attributes("-topmost", True)

        self.clicking = False
        self.stop_event = Event()
        self.hotkey: Optional[str] = None
        self.thread_lock = Lock()
        self.click_thread: Optional[Thread] = None
        self.clicks_performed = 0
        self.session_start_time: Optional[float] = None
        self.click_type = "left"  # left, right, or middle
        self.shutdown_event = Event()
        self.hotkey_vk: Optional[int] = None
        self.hotkey_pressed_last = False
        self.hotkey_capture_active = False
        self.user32 = ctypes.windll.user32

        # Configure style
        self._setup_styles()

        # Create main container
        main = tk.Frame(master, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Row 1: Click type + Interval side by side
        row1 = tk.Frame(main, bg=COLORS["bg"])
        row1.pack(fill=tk.X, pady=(0, 6))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        # Click type (left half)
        type_frame = tk.Frame(row1, bg=COLORS["bg"])
        type_frame.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        tk.Label(type_frame, text="Type", bg=COLORS["bg"], fg=COLORS["inactive"],
                font=("Segoe UI", 8)).pack(anchor="w")
        self.click_type_var = tk.StringVar(value="Left")
        self.click_type_combo = ttk.Combobox(type_frame, textvariable=self.click_type_var,
                                            values=["Left", "Right", "Middle"],
                                            state="readonly", font=("Segoe UI", 9),
                                            width=8, justify="center")
        self.click_type_combo.pack(fill=tk.X, ipady=1)
        self.click_type_combo.bind("<<ComboboxSelected>>", self._on_click_type_change)

        # Interval (right half)
        int_frame = tk.Frame(row1, bg=COLORS["bg"])
        int_frame.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        tk.Label(int_frame, text="Interval (s)", bg=COLORS["bg"], fg=COLORS["inactive"],
                font=("Segoe UI", 8)).pack(anchor="w")
        self.interval_entry = tk.Entry(int_frame, font=("Segoe UI", 9), width=8,
                                       bg=COLORS["card_bg"], fg=COLORS["fg"], relief=tk.FLAT,
                                       bd=0, justify="center", insertbackground=COLORS["fg"])
        self.interval_entry.insert(0, "0.01")
        self.interval_entry.pack(fill=tk.X, ipady=3)

        # Row 2: Hotkey inline
        row2 = tk.Frame(main, bg=COLORS["bg"])
        row2.pack(fill=tk.X, pady=(0, 6))

        self.hotkey_label_text = tk.StringVar(value="Not Set")
        tk.Label(row2, text="Hotkey:", bg=COLORS["bg"], fg=COLORS["inactive"],
                font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.hotkey_label = tk.Label(row2, textvariable=self.hotkey_label_text,
                                     bg=COLORS["bg"], fg=COLORS["accent"],
                                     font=("Segoe UI", 8, "bold"))
        self.hotkey_label.pack(side=tk.LEFT, padx=(2, 0))

        self.set_hotkey_btn = tk.Button(row2, text="Set", command=self.set_hotkey,
                                       font=("Segoe UI", 8), bg=COLORS["card_bg"],
                                       fg=COLORS["fg"], relief=tk.FLAT, bd=0, padx=8, pady=1,
                                       cursor="hand2", activebackground=COLORS["inactive"],
                                       activeforeground=COLORS["fg"])
        self.set_hotkey_btn.pack(side=tk.RIGHT)

        # Row 3: Start / Stop buttons
        row3 = tk.Frame(main, bg=COLORS["bg"])
        row3.pack(fill=tk.X, pady=(0, 4))

        self.start_btn = tk.Button(row3, text="\u25B6 Start", command=self.start_clicking,
                                  font=("Segoe UI", 9, "bold"), bg=COLORS["success"],
                                  fg="white", relief=tk.FLAT, bd=0, pady=5,
                                  cursor="hand2", activebackground="#3db896",
                                  activeforeground="white")
        self.start_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        self.stop_btn = tk.Button(row3, text="\u25A0 Stop", command=self.stop_clicking,
                                 font=("Segoe UI", 9, "bold"), bg=COLORS["error"],
                                 fg="white", relief=tk.FLAT, bd=0, pady=5,
                                 cursor="hand2", activebackground="#d97060",
                                 activeforeground="white", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))

        # Row 4: Status bar
        self.status_label = tk.Label(main, text="Ready", font=("Segoe UI", 8),
                                    fg=COLORS["inactive"], bg=COLORS["bg"], anchor="w")
        self.status_label.pack(fill=tk.X)

        # Fit window to content with comfortable width
        self.master.update_idletasks()
        self.master.geometry("")
        self.master.minsize(280, 0)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start the hotkey listener thread
        self.listener_thread = Thread(target=self.hotkey_listener, daemon=True)
        self.listener_thread.start()

        logger.info("AutoClicker initialized")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("TFrame", background=COLORS["bg"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
        style.configure("TButton", background=COLORS["accent"], foreground=COLORS["fg"])
        style.map("TButton",
                  background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"])])

        style.configure("TCombobox",
                       fieldbackground=COLORS["card_bg"],
                       background=COLORS["card_bg"],
                       foreground=COLORS["fg"],
                       arrowcolor=COLORS["fg"],
                       borderwidth=0,
                       relief="flat")
        style.map("TCombobox",
                 fieldbackground=[("readonly", COLORS["card_bg"])],
                 selectbackground=[("readonly", COLORS["card_bg"])],
                 selectforeground=[("readonly", COLORS["fg"])])

    def _on_click_type_change(self, event=None):
        selection = self.click_type_var.get()
        type_map = {"Left": "left", "Right": "right", "Middle": "middle"}
        self.click_type = type_map.get(selection, "left")
        logger.info(f"Click type changed to: {self.click_type}")

    def set_hotkey(self):
        if self.hotkey_capture_active:
            return

        self.hotkey_capture_active = True
        self.status_label.config(text="Press any key...", fg=COLORS["warning"])
        self.master.update()
        self.master.focus_force()
        self.master.bind("<KeyPress>", self._capture_hotkey)

    def _capture_hotkey(self, event):
        try:
            if not self.hotkey_capture_active:
                return

            vk_code, display_name = self._event_to_vk(event)
            if vk_code is None or display_name is None:
                self.status_label.config(text="Unsupported key, try another", fg=COLORS["error"])
                return

            self.hotkey = display_name
            self.hotkey_vk = vk_code
            self.hotkey_pressed_last = False
            self.hotkey_label_text.set(display_name.upper())
            self.status_label.config(text=f"Hotkey set: {display_name.upper()}", fg=COLORS["success"])
            logger.info(f"Hotkey set to: {display_name} (VK={vk_code})")
        except Exception as e:
            logger.error(f"Error setting hotkey: {e}")
            self.status_label.config(text=f"Error: {e}", fg=COLORS["error"])
            messagebox.showerror("Error", f"Failed to set hotkey: {e}")
        finally:
            self.hotkey_capture_active = False
            self.master.unbind("<KeyPress>")

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
            self.status_label.config(text=f"Error: {e}", fg="red")

    def start_clicking(self):
        try:
            interval_str = self.interval_entry.get().strip()
            if not interval_str:
                self.status_label.config(text="Enter an interval", fg=COLORS["error"])
                return
                
            interval = float(interval_str)
            
            # Validate interval range
            if interval < 0.01:
                self.status_label.config(text="Min: 0.01 seconds", fg=COLORS["error"])
                return
            if interval > 60:
                self.status_label.config(text="Max: 60 seconds", fg=COLORS["error"])
                return
                
        except ValueError:
            self.status_label.config(text="Invalid number", fg=COLORS["error"])
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
            self.status_label.config(text="Clicking...", fg=COLORS["success"])
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
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
            self.status_label.config(text="Stopped", fg=COLORS["warning"])
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.session_start_time = None
            logger.info("Clicking stopped")

    def click_loop(self, interval):
        try:
            while not self.stop_event.is_set():
                try:
                    if self._is_cursor_in_corner():
                        logger.warning("FailSafe triggered - mouse at corner")
                        self.master.after(0, self.stop_clicking)
                        self.master.after(0, lambda: self.status_label.config(text="Emergency stop", fg=COLORS["error"]))
                        break

                    self._native_click(self.click_type)
                    self.clicks_performed += 1
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Error during click: {e}")
                    self.master.after(0, self.stop_clicking)
                    break
            
            logger.info(f"Click loop ended. Total clicks: {self.clicks_performed}")
        except Exception as e:
            logger.error(f"Click loop crashed: {e}")
            self.status_label.config(text=f"Error: {e}", fg=COLORS["error"])
            self.clicking = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def hotkey_listener(self):
        try:
            while not self.shutdown_event.is_set():
                try:
                    if self.hotkey_vk is not None:
                        key_state = self.user32.GetAsyncKeyState(self.hotkey_vk)
                        is_pressed = (key_state & 0x8000) != 0

                        if is_pressed and not self.hotkey_pressed_last:
                            self.master.after(0, self.toggle_clicking)

                        self.hotkey_pressed_last = is_pressed
                    else:
                        self.hotkey_pressed_last = False
                except Exception as e:
                    logger.error(f"Hotkey polling error: {e}")
                time.sleep(0.02)
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
            self.stop_clicking()
        finally:
            self.master.destroy()

# Run app
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = AutoClicker(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
