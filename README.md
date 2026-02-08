# AutoClicker

A lightweight, always-on-top autoclicker with a compact dark UI. Supports left, right, and middle mouse buttons, configurable click intervals, and a global hotkey toggle.

## Requirements

- Python 3.8+
- Windows OS

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/Autoclicker.git
   cd Autoclicker
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `pyautogui` — programmatic mouse clicking
   - `keyboard` — global hotkey detection

   > `tkinter` is included with Python by default and does not need to be installed separately.

## Usage

Run the app:

```bash
pythonw autoclicker.pyw
```

Or double-click `autoclicker.pyw` in your file explorer.

### Controls

| Control | Description |
|---|---|
| **Type** | Choose Left, Right, or Middle click |
| **Interval (s)** | Seconds between clicks (0.01 – 60) |
| **Set Hotkey** | Press any key to assign a global toggle hotkey |
| **▶ Start** | Begin auto-clicking |
| **■ Stop** | Stop auto-clicking |

### Tips

- The window stays on top of other windows so you can always see the status.
- Move your mouse to a screen corner to trigger the PyAutoGUI fail-safe and emergency-stop clicking.
- The hotkey works globally — you can toggle clicking even when the window is not focused.

## License

MIT
