# AutoClicker

A lightweight, always-on-top autoclicker built entirely with standard Python libraries, with a compact custom title bar, taskbar icon support, and dark UI. Supports left, right, and middle mouse buttons, configurable click intervals, and a global hotkey toggle.

## Requirements

- Python 3.8+
- Windows OS

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/Autoclicker.git
   cd Autoclicker
   ```

2. **Run the app:**

   ```bash
   pythonw autoclicker.pyw
   ```

No external packages are required.
The app uses only Python standard library modules, including built-in `tkinter` and `ctypes` for the UI and native Windows integration.

> `tkinter` is included with most standard Python installers on Windows and does not need separate installation.

## Usage

Run the app:

```bash
pythonw autoclicker.pyw
```

Or double-click `autoclicker.pyw` in your file explorer.

Replace those files with your own PNGs using the same filenames to update the title bar logo and taskbar icon.

### Controls

| Control | Description |
| --- | --- |
| **Type** | Choose Left, Right, or Middle click |
| **Interval (s)** | Seconds between clicks (0.001 – 60) |
| **Set Hotkey** | Press any key to assign a global toggle hotkey |
| **▶ Start** | Begin auto-clicking |
| **■ Stop** | Stop auto-clicking |

### Tips

- The window stays on top of other windows so you can always see the status.
- Move your mouse to any screen corner to trigger the built-in fail-safe and emergency-stop clicking.
- The hotkey works globally — you can toggle clicking even when the window is not focused.
- Out-of-range interval values are automatically clamped into the supported range.
- After assigning a hotkey, the app briefly ignores that key so the same press does not immediately toggle clicking.
- Hover the title status badge to see more detail for warnings, errors, and interval adjustments.

## License

MIT
