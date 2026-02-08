import tkinter as tk
from tkinter import messagebox, ttk
from threading import Thread, Event, Lock
import pyautogui
import keyboard
import time
import logging
from typing import Optional
import sys
import os

# Debug mode configuration - set to False to hide console
DEBUG_MODE = False

# Hide console window in production mode (Windows only)
if not DEBUG_MODE and sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# Configure logging
if DEBUG_MODE:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable PyAutoGUI fail-safe by default (user can still move mouse to corner to stop)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01  # Add small delay between commands

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
        self.master.geometry("320x330")
        self.master.configure(bg=COLORS["bg"])
        self.master.resizable(False, False)

        self.clicking = False
        self.stop_event = Event()
        self.hotkey: Optional[str] = None
        self.thread_lock = Lock()
        self.click_thread: Optional[Thread] = None
        self.clicks_performed = 0
        self.session_start_time: Optional[float] = None
        self.click_type = "left"  # left, right, or middle

        # Configure style
        self._setup_styles()

        # Create main container
        main_frame = tk.Frame(master, bg=COLORS["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Click type section
        self._create_click_type_section(main_frame)

        # Interval section
        self._create_interval_section(main_frame)

        # Hotkey section
        self._create_hotkey_section(main_frame)

        # Control buttons section
        self._create_control_section(main_frame)

        # Status section
        self._create_status_section(main_frame)

        # Start the hotkey listener thread
        self.listener_thread = Thread(target=self.hotkey_listener, daemon=True)
        self.listener_thread.start()
        
        logger.info("AutoClicker initialized")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
        style.configure("TButton", background=COLORS["accent"], foreground=COLORS["fg"])
        style.map("TButton", 
                  background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"])])
        
        # Configure Combobox
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

    def _create_click_type_section(self, parent):
        section = tk.Frame(parent, bg=COLORS["bg"])
        section.pack(fill=tk.X, pady=(0, 16))
        
        tk.Label(section, text="Click Type", bg=COLORS["bg"], fg=COLORS["fg"], 
                font=("Segoe UI", 10)).pack(pady=(0, 6))
        
        self.click_type_var = tk.StringVar(value="Left Click")
        self.click_type_combo = ttk.Combobox(section, textvariable=self.click_type_var,
                                            values=["Left Click", "Right Click", "Middle Click"],
                                            state="readonly", font=("Segoe UI", 11),
                                            width=15, justify="center")
        self.click_type_combo.pack()
        self.click_type_combo.bind("<<ComboboxSelected>>", self._on_click_type_change)

    def _on_click_type_change(self, event=None):
        selection = self.click_type_var.get()
        if selection == "Left Click":
            self.click_type = "left"
        elif selection == "Right Click":
            self.click_type = "right"
        elif selection == "Middle Click":
            self.click_type = "middle"
        logger.info(f"Click type changed to: {self.click_type}")

    def _create_interval_section(self, parent):
        section = tk.Frame(parent, bg=COLORS["bg"])
        section.pack(fill=tk.X, pady=(0, 16))
        
        # Input frame
        input_frame = tk.Frame(section, bg=COLORS["bg"])
        input_frame.pack()
        
        tk.Label(input_frame, text="Interval (seconds)", bg=COLORS["bg"], fg=COLORS["fg"], 
                font=("Segoe UI", 10)).pack(pady=(0, 6))
        
        self.interval_entry = tk.Entry(input_frame, font=("Segoe UI", 14), width=10,
                                       bg=COLORS["card_bg"], fg=COLORS["fg"], relief=tk.FLAT, 
                                       bd=0, justify="center", insertbackground=COLORS["fg"])
        self.interval_entry.insert(0, "0.01")
        self.interval_entry.pack(ipady=6)

    def _create_hotkey_section(self, parent):
        section = tk.Frame(parent, bg=COLORS["bg"])
        section.pack(fill=tk.X, pady=(0, 16))
        
        # Hotkey display
        display_frame = tk.Frame(section, bg=COLORS["bg"])
        display_frame.pack()
        
        tk.Label(display_frame, text="Hotkey (toggle): ", bg=COLORS["bg"], 
                fg=COLORS["inactive"], font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        self.hotkey_label_text = tk.StringVar(value="Not Set")
        self.hotkey_label = tk.Label(display_frame, textvariable=self.hotkey_label_text, 
                                     bg=COLORS["bg"], fg=COLORS["accent"], font=("Segoe UI", 9, "bold"))
        self.hotkey_label.pack(side=tk.LEFT)
        
        # Button
        self.set_hotkey_btn = tk.Button(section, text="Set Hotkey", command=self.set_hotkey,
                                       font=("Segoe UI", 9), bg=COLORS["card_bg"], 
                                       fg=COLORS["fg"], relief=tk.FLAT, bd=0, padx=16, pady=6,
                                       cursor="hand2", activebackground=COLORS["inactive"],
                                       activeforeground=COLORS["fg"])
        self.set_hotkey_btn.pack(pady=(6, 0))

    def _create_control_section(self, parent):
        section = tk.Frame(parent, bg=COLORS["bg"])
        section.pack(fill=tk.X, pady=(0, 16))
        
        # Start/Stop buttons side by side
        button_frame = tk.Frame(section, bg=COLORS["bg"])
        button_frame.pack(fill=tk.X)
        
        self.start_btn = tk.Button(button_frame, text="Start", command=self.start_clicking,
                                  font=("Segoe UI", 10), bg=COLORS["success"], 
                                  fg="white", relief=tk.FLAT, bd=0, padx=20, pady=10,
                                  cursor="hand2", activebackground="#3db896",
                                  activeforeground="white")
        self.start_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        
        self.stop_btn = tk.Button(button_frame, text="Stop", command=self.stop_clicking,
                                 font=("Segoe UI", 10), bg=COLORS["error"], 
                                 fg="white", relief=tk.FLAT, bd=0, padx=20, pady=10,
                                 cursor="hand2", activebackground="#d97060",
                                 activeforeground="white", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))

    def _create_status_section(self, parent):
        section = tk.Frame(parent, bg=COLORS["bg"])
        section.pack(fill=tk.X)
        
        self.status_label = tk.Label(section, text="Ready", font=("Segoe UI", 9), 
                                    fg=COLORS["inactive"], bg=COLORS["bg"])
        self.status_label.pack()

    def set_hotkey(self):
        self.status_label.config(text="Press any key...", fg=COLORS["warning"])
        self.master.update()
        self.master.focus_force()
        
        try:
            keyboard.unhook_all()
        except Exception as e:
            logger.warning(f"Error unhooking: {e}")

        def on_key(event):
            try:
                self.hotkey = event.name
                if self.hotkey:
                    self.hotkey_label_text.set(self.hotkey.upper())
                    self.status_label.config(text=f"Hotkey set: {self.hotkey.upper()}", fg=COLORS["success"])
                    keyboard.unhook_all()
                    keyboard.add_hotkey(self.hotkey, self.toggle_clicking)
                    logger.info(f"Hotkey set to: {self.hotkey}")
                else:
                    raise ValueError("Invalid hotkey")
            except Exception as e:
                logger.error(f"Error setting hotkey: {e}")
                self.status_label.config(text=f"Error: {e}", fg=COLORS["error"])
                keyboard.unhook_all()

        try:
            Thread(target=lambda: keyboard.hook(on_key), daemon=True).start()
        except Exception as e:
            logger.error(f"Error starting hotkey listener: {e}")
            messagebox.showerror("Error", f"Failed to set hotkey: {e}")

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
                    if self.click_type == "left":
                        pyautogui.click()
                    elif self.click_type == "right":
                        pyautogui.rightClick()
                    elif self.click_type == "middle":
                        pyautogui.middleClick()
                    self.clicks_performed += 1
                    time.sleep(interval)
                except pyautogui.FailSafeException:
                    logger.warning("FailSafe triggered - mouse at corner")
                    self.stop_clicking()
                    self.status_label.config(text="Emergency stop", fg=COLORS["error"])
                    break
                except Exception as e:
                    logger.error(f"Error during click: {e}")
                    self.stop_clicking()
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
            while True:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Hotkey listener error: {e}")

# Run app
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = AutoClicker(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise
