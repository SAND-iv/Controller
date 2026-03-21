# PC Controller

Control your PC from your phone over WiFi.

## Folder Structure
```
Controller/
├── server.py          ← Run this on your PC
├── controller.html    ← Web fallback (browser version)
└── ControllerApp2/    ← Mobile app source
    ├── App.js
    ├── app.json
    ├── eas.json
    ├── package.json
    └── babel.config.js
```

---

## PC Server

### Install dependencies
```bash
pip install aiohttp pynput pyautogui pillow qrcode
```

### Run
```bash
python server.py
```
- A window shows your IP address in green and a QR code
- QR image is automatically deleted when you close the server

---

## Mobile App (Build APK)

```bash
cd ControllerApp2
npm install
eas login
eas build:configure    # select Android
eas build --platform android --profile preview
```

Download the APK link when done and install on your phone.

---

## Connecting

1. Run `server.py` on your PC
2. Open the app on your phone
3. Type the IP shown in the server window (green number)
4. Tap **Connect**

Make sure your phone and PC are on the same WiFi network.
