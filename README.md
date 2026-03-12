# PC Controller

Control your PC from your phone — over **WiFi** or **Bluetooth BLE**.

---

## PC Server Setup

### Install dependencies
```bash
pip install aiohttp pynput pyautogui pillow qrcode bless
```

> **Windows note:** `bless` requires the Windows 10+ Bluetooth stack (WinRT).
> Run the server as **Administrator** the first time if BLE fails to start.

### Run the server
```bash
python server.py
```

A window will appear with a QR code for WiFi and a BLE status line.

---

## Mobile App Setup

Requires **Node.js 18+** and **Expo CLI**.

```bash
cd ControllerApp
npm install

# Android (USB or wireless ADB)
npm run android

# iOS (Mac + Xcode required)
npm run ios
```

> ⚠️ This app uses `react-native-ble-plx` which requires native code.
> **Expo Go won't work** — you must use `expo run:android` / `expo run:ios`
> or build with EAS Build.

### EAS Build (no USB needed)
```bash
npm install -g eas-cli
eas build --profile development --platform android
```

---

## Connecting

### WiFi
1. Open the app → tap **WiFi**
2. Enter your PC's IP (shown in the server window)
3. Tap **Connect**

### Bluetooth
1. Open the app → tap **Bluetooth**
2. Tap **Scan & Connect** — the app will find "PC Controller"
3. Connection is automatic

---

## Controls

| Control | Action |
|---|---|
| Single finger drag | Move mouse |
| Two finger drag | Scroll |
| Tap | Left click |
| L / R buttons | Left / Right click |
| 🔓 Drag | Hold mouse button (for drag & drop) |
| Ctrl / Alt | Toggle modifier keys |
| ⊞ Win | Windows key |
| ⌨ Type | Open keyboard to type text |
| Media row | Volume, mute, play/pause, skip |
