# PC Controller

![Platform](https://img.shields.io/badge/platform-Windows-blue?logo=windows)
![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python)
![Android](https://img.shields.io/badge/android-8.0%2B-green?logo=android)
![License](https://img.shields.io/badge/license-MIT-green)
![Build](https://img.shields.io/badge/build-GitHub%20Actions-black?logo=github)

Control your Windows PC from your Android phone. The phone becomes a wireless trackpad, keyboard, and media remote — no internet required.

---

## Screenshots

<img src="https://github.com/user-attachments/assets/0f10f703-ae7d-41fe-8047-a1b21fb567c8" width="460"/>

<br/>

<img src="https://github.com/user-attachments/assets/52aec1d2-8c66-4181-9a59-80d2b73b5071" width="180"/>
<img src="https://github.com/user-attachments/assets/fcf4bad1-68e4-49f9-a232-67c4a2cc6415" width="180"/>
<img src="https://github.com/user-attachments/assets/767a2e24-ff2b-4caa-9f2c-d73de8617993" width="180"/>
<img src="https://github.com/user-attachments/assets/4d147e5a-41f3-4394-8bd9-def316aaeed5" width="150"/>

---

## Features

- **Trackpad** — single-finger move, tap to click, two-finger scroll
- **Mouse buttons** — left click, right click, drag lock
- **Keyboard** — type text, modifier keys (Ctrl, Alt), Enter, Backspace, Esc, Win
- **Media controls** — volume, mute, play/pause, skip
- **Three connection modes** — WiFi, USB (no network needed), Mobile Hotspot
- **Auto IP detection** — switch networks and the server updates automatically
- **Single-file server** — runs as a standalone `.exe`, no Python needed

---

## How It Works

```
┌──────────────────┐         WebSocket          ┌─────────────────────┐
│   Android App    │ ─────────────────────────► │   PC Server         │
│  Capacitor +     │     WiFi / USB / Hotspot    │   Python + tkinter  │
│  HTML / CSS / JS │ ◄──────── events ────────── │   pyautogui + pynput│
└──────────────────┘                             └─────────────────────┘
```

The phone app sends JSON commands over a WebSocket. The Python server translates them into real mouse and keyboard input using `pyautogui` and `pynput`.

---

## Stack

| Layer | Technology |
|---|---|
| Mobile app | HTML5, CSS3, JavaScript, Capacitor |
| PC server | Python, aiohttp, pyautogui, pynput, tkinter |
| Build pipeline | GitHub Actions — APK + EXE on every push |
| Transport | WebSockets (ws://) |

---

## Getting Started

### PC Server

**Option A — Standalone EXE (recommended)**

Download `PC Controller.exe` from [Actions → Build Windows EXE](../../actions) and double-click it. No Python needed.

**Option B — Run from source**

```bash
pip install aiohttp pynput pyautogui pillow qrcode
python server.py
```

### Mobile App

Download the latest APK from [Actions → Build Android APK](../../actions) and install it on your Android phone. Allow "Install from unknown sources" when prompted.

---

## Connecting

### WiFi
1. Make sure phone and PC are on the same network
2. Open the app → **WiFi** tab
3. Scan the QR code shown in the server window, or enter the IP manually

### USB
1. Connect phone to PC via USB
2. Enable **USB Debugging** (Settings → Developer Options → USB Debugging)
3. In the server window, click **🔌 Setup USB** — it runs `adb reverse` automatically
4. Open the app → **USB** tab → Connect

### Mobile Hotspot
1. Turn on **Hotspot** on your phone
2. Connect your PC to the hotspot network
3. The server detects the new IP automatically — no restart needed
4. Open the app → **Hotspot** tab → enter the IP or scan QR

---

## Project Structure

```
Controller/
├── server.py                   # PC server
├── controller.html             # Lightweight browser fallback
└── ControllerApp2/
    ├── www/
    │   └── index.html          # Full mobile app (single file)
    ├── package.json
    └── capacitor.config.json
```

---

## Building

Both the APK and EXE are built automatically by GitHub Actions on every push to `main`.

| Artifact | Workflow | Download |
|---|---|---|
| Android APK | Build Android APK | Actions → Artifacts |
| Windows EXE | Build Windows EXE | Actions → Artifacts |

---

## Known Limitations

- Windows only (server)
- Android only (app)
- Requires local network or USB — not designed for remote access over the internet

---

## License

MIT
