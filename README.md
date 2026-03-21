# PC Controller

**Control your PC from your Android phone — over WiFi, USB, or Mobile Hotspot.**

A personal project built to replace a physical mouse and keyboard when working from a distance. The phone acts as a wireless trackpad, media controller, and keyboard input device.

---

## Features

- **Touchpad** — single finger to move, tap to click, two-finger scroll
- **Mouse buttons** — left click, right click, drag lock
- **Media controls** — volume, mute, play/pause, skip
- **Keyboard input** — type text, Enter, Backspace, Esc, Win key
- **Modifier keys** — Ctrl, Alt (toggle and hold)
- **Three connection modes:**
  - 📡 **WiFi** — scan QR code or enter IP manually
  - 🔌 **USB** — one-click setup via the server window, no terminal needed
  - 📶 **Hotspot** — phone creates a hotspot, PC connects to it

---

## How It Works

```
┌─────────────────────┐        WebSocket        ┌──────────────────────┐
│   Android App       │ ─────────────────────── │   PC Server          │
│   (Capacitor +      │    WiFi / USB / Hotspot  │   (Python + tkinter) │
│    HTML/CSS/JS)     │                          │   Controls mouse     │
└─────────────────────┘                          │   and keyboard via   │
                                                 │   pyautogui + pynput │
                                                 └──────────────────────┘
```

The phone app sends JSON commands over a WebSocket connection. The Python server receives them and translates them into real mouse movements, clicks, and key presses on the PC.

---

## Tech Stack

| Component | Technology |
|---|---|
| Mobile App | HTML5, CSS3, JavaScript, Capacitor |
| PC Server | Python, aiohttp, pyautogui, pynput, tkinter |
| Build Pipeline | GitHub Actions (APK + EXE auto-build) |
| Connection | WebSockets |

---

## Project Structure

```
Controller/
├── server.py              # PC server — run this or use the EXE
├── controller.html        # Browser fallback
└── ControllerApp2/
    ├── www/
    │   └── index.html     # Full app UI (single file)
    ├── package.json
    └── capacitor.config.json
```

---

## Setup

### PC Server

**Option A — Run the EXE (no Python needed)**
Download `PC Controller.exe` from [Releases](../../releases) and double-click it.

**Option B — Run from source**
```bash
pip install aiohttp pynput pyautogui pillow qrcode
python server.py
```

### Mobile App

Download the latest APK from [Actions → Build Android APK](../../actions) and install it on your Android phone.

> Allow "Install from unknown sources" if prompted — this is normal for sideloaded APKs.

---

## Connecting

### WiFi
1. Make sure phone and PC are on the same WiFi network
2. Open the app → tap **📡 WiFi**
3. Scan the QR code shown in the server window, or enter the IP manually

### USB
1. Connect phone to PC via USB cable
2. Enable **USB Debugging** on your phone (Settings → Developer Options)
3. Open the server → click **🔌 Setup USB** — it configures everything automatically
4. Open the app → tap **🔌 USB** → Connect

### Hotspot
1. Turn on **Mobile Hotspot** on your phone
2. Connect your PC to the phone's hotspot network
3. Open the server — note the new IP address shown
4. Open the app → tap **📶 Hotspot** → enter the IP → Connect

---

## Building from Source

Both the APK and EXE are built automatically by GitHub Actions on every push to `main`.

- **APK** → Actions → Build Android APK → Artifacts
- **EXE** → Actions → Build Windows EXE → Artifacts

---

## License

MIT — free to use and modify.
