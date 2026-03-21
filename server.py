import asyncio
import json
import os
import socket
import qrcode
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from aiohttp import web
from pynput.keyboard import Controller as KeyController, Key
import pyautogui
import logging
import atexit
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP = 0
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ---------- paths (works both as .py and .exe) ----------
if getattr(sys, 'frozen', False):
    WEB_DIR  = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    WEB_DIR  = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = WEB_DIR

PORT = 8080
DEFAULT_MOUSE_SPEED = 1.5
SCROLL_MULTIPLIER   = 4
QR_FILE = os.path.join(BASE_DIR, "controller_qr.png")

keyboard = KeyController()

keymap = {
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "ENTER": Key.enter, "BACKSPACE": Key.backspace, "TAB": Key.tab, "ESC": Key.esc,
    " ": " ",
    "vol_up":  Key.media_volume_up,   "vol_down": Key.media_volume_down,
    "mute":    Key.media_volume_mute, "play":     Key.media_play_pause,
    "next":    Key.media_next,        "prev":     Key.media_previous,
    "win":     Key.cmd,
}
for i in range(65, 91):
    keymap[chr(i)] = chr(i).lower()

def press_key(k):   keyboard.press(keymap.get(k, k))
def release_key(k): keyboard.release(keymap.get(k, k))

state = {"mouse_speed": DEFAULT_MOUSE_SPEED, "acceleration_enabled": False}

def cleanup_qr():
    if os.path.exists(QR_FILE):
        try:
            os.remove(QR_FILE)
        except Exception:
            pass

atexit.register(cleanup_qr)

# ============================================================
# Command dispatcher
# ============================================================
def handle_command(data: dict):
    cmd = data.get("command")
    try:
        if cmd == "type":          keyboard.type(data.get("text", ""))
        elif cmd == "key":
            k = data.get("key")
            if k in keymap: press_key(k); release_key(k)
        elif cmd == "drag_start":  pyautogui.mouseDown()
        elif cmd == "drag_end":    pyautogui.mouseUp()
        elif cmd == "hold":        press_key(data["key"])
        elif cmd == "release":     release_key(data["key"])
        elif cmd == "move":
            dx, dy = float(data.get("dx", 0)), float(data.get("dy", 0))
            spd = state["mouse_speed"]
            fac = max(1.0, 1.0 + (abs(dx)+abs(dy))/8.0) if state["acceleration_enabled"] else 1.0
            pyautogui.moveRel(dx*spd*fac, dy*spd*fac)
        elif cmd == "click":
            b = data.get("button")
            if b == "left": pyautogui.click()
            elif b == "right": pyautogui.rightClick()
        elif cmd == "scroll":
            pyautogui.scroll(int(int(data.get("dy", 0)) * SCROLL_MULTIPLIER))
        elif cmd == "set_speed":
            state["mouse_speed"] = float(data.get("value", DEFAULT_MOUSE_SPEED))
        elif cmd == "set_acc":
            state["acceleration_enabled"] = bool(data.get("value"))
        elif cmd == "key_toggle":
            t = {"ctrl": Key.ctrl, "alt": Key.alt,
                 "shift": Key.shift, "cmd": Key.cmd}.get(data.get("key"))
            if t:
                if data.get("state") == "down": keyboard.press(t)
                elif data.get("state") == "up":  keyboard.release(t)
    except Exception as e:
        log.error(f"Command error ({cmd}): {e}")

# ============================================================
# WebSocket server
# ============================================================
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    log.info("Client connected")
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try: handle_command(json.loads(msg.data))
                except Exception as e: log.error(f"Parse error: {e}")
    finally:
        pyautogui.mouseUp()
        log.info("Client disconnected")
    return ws

async def serve_file(request):
    filename = request.match_info.get("filename", "controller.html")
    path = os.path.join(WEB_DIR, filename)
    if not os.path.exists(path):
        return web.Response(status=404, text="Not found")
    mime = {".json":"application/json",".js":"application/javascript",
            ".png":"image/png",".html":"text/html"}
    ct = mime.get(os.path.splitext(filename)[1], "application/octet-stream")
    return web.FileResponse(path, headers={"Content-Type": ct})

def start_wifi_server(loop):
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.add_routes([web.get("/ws", websocket_handler),
                    web.get("/", serve_file),
                    web.get("/{filename}", serve_file)])
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", PORT).start())
    loop.run_forever()

# ============================================================
# USB helper
# ============================================================
def find_adb():
    candidates = [
        "adb",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
    ]
    for c in candidates:
        try:
            r = subprocess.run([c, "version"], capture_output=True, timeout=3)
            if r.returncode == 0: return c
        except Exception: continue
    return None

def setup_usb(callback):
    def _run():
        adb = find_adb()
        if not adb:
            callback("error", "adb not found.\nInstall Android Studio first.")
            return
        callback("info", "Checking device…")
        try:
            devices = subprocess.run([adb, "devices"], capture_output=True,
                                     text=True, timeout=5)
            lines = [l for l in devices.stdout.strip().split("\n")[1:] if l.strip()]
            if not lines:
                callback("error", "No device found.\nConnect phone + allow USB Debugging.")
                return
            r = subprocess.run([adb, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                callback("ok", "✅ USB ready!\nOpen app → USB → Connect")
            else:
                callback("error", f"adb error:\n{r.stderr.strip()}")
        except Exception as e:
            callback("error", str(e))
    threading.Thread(target=_run, daemon=True).start()

# ============================================================
# Helpers
# ============================================================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except: return "127.0.0.1"
    finally: s.close()

def generate_qr_image(url):
    qrcode.make(url).save(QR_FILE)
    return QR_FILE

# ============================================================
# GUI
# ============================================================
class ServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("PC Controller")
        root.geometry("440x630")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.ip  = get_local_ip()
        self.url = f"http://{self.ip}:{PORT}/"
        self._build_ui()
        self._start_server()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="PC Controller",
                  font=("Segoe UI", 16, "bold")).pack(pady=(0,4))

        # QR code
        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=2)
        ttk.Label(frm, text=self.url, foreground="#3b82f6",
                  font=("Segoe UI", 9)).pack(pady=(0,6))

        # WiFi IP
        ip_frm = ttk.LabelFrame(frm, text="WiFi / Hotspot IP", padding=10)
        ip_frm.pack(fill="x", pady=(0,8))
        row = ttk.Frame(ip_frm); row.pack(fill="x")
        ttk.Label(row, text=self.ip, font=("Segoe UI", 22, "bold"),
                  foreground="#22c55e").pack(side="left")
        ttk.Button(row, text="📋 Copy",
                   command=lambda: self._copy(self.ip)).pack(side="right")
        ttk.Label(ip_frm, text="Enter this in the app (WiFi or Hotspot tab)",
                  font=("Segoe UI", 9), foreground="#888").pack(anchor="w")

        # USB
        usb_frm = ttk.LabelFrame(frm, text="USB Connection", padding=10)
        usb_frm.pack(fill="x", pady=(0,8))
        ttk.Label(usb_frm,
                  text="Plug in your phone with USB Debugging ON, then click:",
                  font=("Segoe UI", 9), foreground="#888",
                  wraplength=380).pack(anchor="w", pady=(0,6))
        btn_row = ttk.Frame(usb_frm); btn_row.pack(fill="x")
        self.usb_btn = ttk.Button(btn_row, text="🔌 Setup USB",
                                   command=self._do_usb)
        self.usb_btn.pack(side="left")
        self.usb_var = tk.StringVar(value="")
        self.usb_lbl = ttk.Label(btn_row, textvariable=self.usb_var,
                                  font=("Segoe UI", 9), foreground="#888",
                                  wraplength=240)
        self.usb_lbl.pack(side="left", padx=(10,0))

        # Settings
        opts = ttk.LabelFrame(frm, text="Settings", padding=12)
        opts.pack(fill="x", pady=(0,6))
        sr = ttk.Frame(opts); sr.pack(fill="x", pady=(0,4))
        ttk.Label(sr, text="Mouse Speed:", font=("Segoe UI", 10)).pack(side="left")
        self.spd_lbl = ttk.Label(sr, text=f"{state['mouse_speed']:.1f}×",
                                  font=("Segoe UI", 10, "bold"),
                                  foreground="#3b82f6")
        self.spd_lbl.pack(side="right")
        self.spd_var = tk.DoubleVar(value=state["mouse_speed"])
        ttk.Scale(opts, from_=0.5, to=5.0, variable=self.spd_var,
                  orient="horizontal",
                  command=self._on_speed).pack(fill="x", pady=(0,8))
        self.acc_var = tk.BooleanVar(value=state["acceleration_enabled"])
        ttk.Checkbutton(opts, text="Enable Mouse Acceleration",
                        variable=self.acc_var,
                        command=self._on_acc).pack(anchor="w")

        self.status_var = tk.StringVar(value="Starting…")
        ttk.Label(frm, textvariable=self.status_var,
                  foreground="#888", font=("Segoe UI", 9)).pack(pady=(6,0))

    def _do_usb(self):
        self.usb_btn.config(state="disabled")
        self.usb_var.set("Working…")
        def cb(status, msg):
            def _u():
                self.usb_var.set(msg)
                fg = "#22c55e" if status=="ok" else "#ef4444" if status=="error" else "#888"
                self.usb_lbl.config(foreground=fg)
                self.usb_btn.config(state="normal")
            self.root.after(0, _u)
        setup_usb(cb)

    def _on_speed(self, val):
        v = float(val)
        state["mouse_speed"] = v
        self.spd_lbl.config(text=f"{v:.1f}×")

    def _on_acc(self):
        state["acceleration_enabled"] = self.acc_var.get()

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _start_server(self):
        threading.Thread(target=start_wifi_server,
                         args=(asyncio.new_event_loop(),), daemon=True).start()
        self.root.after(500, self._load_qr)
        self.root.after(600, lambda: self.status_var.set(
            f"✅ Running — {self.ip}:{PORT}"))

    def _load_qr(self):
        try:
            f = generate_qr_image(self.url)
            im = Image.open(f).resize((160, 160))
            self.qr_img = ImageTk.PhotoImage(im)
            self.qr_label.config(image=self.qr_img)
        except Exception as e:
            log.error(f"QR error: {e}")

    def _on_close(self):
        cleanup_qr()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    ServerGUI(root)
    root.mainloop()
