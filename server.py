import asyncio
import json
import os
import socket
import ssl
import secrets
import hashlib
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
import ipaddress

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP = 0
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ---------- paths ----------
if getattr(sys, 'frozen', False):
    WEB_DIR  = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    WEB_DIR  = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = WEB_DIR

PORT     = 8080
WSS_PORT = 8443   # encrypted WebSocket port
DEFAULT_MOUSE_SPEED = 1.5
SCROLL_MULTIPLIER   = 4
QR_FILE  = os.path.join(BASE_DIR, "controller_qr.png")
CERT_FILE = os.path.join(BASE_DIR, "server.crt")
KEY_FILE  = os.path.join(BASE_DIR, "server.key")

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

ALLOWED_COMMANDS = {
    "type", "key", "drag_start", "drag_end", "hold", "release",
    "move", "click", "scroll", "set_speed", "set_acc", "key_toggle", "auth", "ping"
}

def press_key(k):   keyboard.press(keymap.get(k, k))
def release_key(k): keyboard.release(keymap.get(k, k))

# ============================================================
# Security state
# ============================================================
security = {
    "pin":          None,
    "pin_hash":     None,
    "pin_enabled":  False,      # PIN is optional
    "active_ws":    None,
    "lock":         threading.Lock(),
}

def generate_pin():
    """Generate a random 6-digit PIN."""
    return str(secrets.randbelow(900000) + 100000)

def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()

def verify_pin(pin: str) -> bool:
    return hashlib.compare_digest(hash_pin(pin), security["pin_hash"])

# ============================================================
# SSL certificate (self-signed, generated at startup)
# ============================================================
def generate_self_signed_cert():
    """Generate a self-signed cert using Python's cryptography library or openssl."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return True
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, u"PC Controller"),
        ])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
            .sign(key, hashes.SHA256())
        )
        with open(KEY_FILE, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()
            ))
        with open(CERT_FILE, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        log.info("Self-signed certificate generated")
        return True
    except ImportError:
        log.warning("cryptography library not installed — WSS unavailable, using WS")
        return False
    except Exception as e:
        log.error(f"Cert generation failed: {e}")
        return False

# ============================================================
# Command dispatcher
# ============================================================
def handle_command(data: dict):
    cmd = data.get("command")
    if cmd not in ALLOWED_COMMANDS:
        log.warning(f"Rejected unknown command: {cmd}")
        return
    try:
        if cmd == "type":
            text = data.get("text", "")
            if len(text) > 500: return   # rate limit
            keyboard.type(text)
        elif cmd == "key":
            k = data.get("key")
            if k in keymap: press_key(k); release_key(k)
        elif cmd == "drag_start":  pyautogui.mouseDown()
        elif cmd == "drag_end":    pyautogui.mouseUp()
        elif cmd == "hold":        press_key(data["key"])
        elif cmd == "release":     release_key(data["key"])
        elif cmd == "move":
            dx = max(-200, min(200, float(data.get("dx", 0))))
            dy = max(-200, min(200, float(data.get("dy", 0))))
            spd = state["mouse_speed"]
            fac = max(1.0, 1.0+(abs(dx)+abs(dy))/8.0) if state["acceleration_enabled"] else 1.0
            pyautogui.moveRel(dx*spd*fac, dy*spd*fac)
        elif cmd == "click":
            b = data.get("button")
            if b == "left": pyautogui.click()
            elif b == "right": pyautogui.rightClick()
        elif cmd == "scroll":
            dy = max(-20, min(20, int(data.get("dy", 0))))
            pyautogui.scroll(int(dy * SCROLL_MULTIPLIER))
        elif cmd == "set_speed":
            v = max(0.5, min(5.0, float(data.get("value", DEFAULT_MOUSE_SPEED))))
            state["mouse_speed"] = v
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

state = {"mouse_speed": DEFAULT_MOUSE_SPEED, "acceleration_enabled": False}

# ============================================================
# WebSocket server — PIN auth + single connection
# ============================================================
async def websocket_handler(request):
    # ── Single connection limit ──
    with security["lock"]:
        if security["active_ws"] is not None:
            log.warning("Connection rejected — another device already connected")
            return web.Response(status=409, text="Another device is already connected")

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    authenticated = False
    log.info(f"New connection from {request.remote}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    await ws.send_str(json.dumps({"status": "error", "msg": "Invalid JSON"}))
                    continue

                cmd = data.get("command")

                # ── Auth flow ──
                if not authenticated:
                    # If PIN is disabled, auto-authenticate
                    if not security["pin_enabled"]:
                        authenticated = True
                        with security["lock"]:
                            security["active_ws"] = ws
                        await ws.send_str(json.dumps({"status": "auth_ok"}))
                        log.info("Client connected (no PIN required)")
                        continue

                    if cmd == "auth":
                        pin = str(data.get("pin", ""))
                        if verify_pin(pin):
                            authenticated = True
                            with security["lock"]:
                                security["active_ws"] = ws
                            await ws.send_str(json.dumps({"status": "auth_ok"}))
                            log.info("Client authenticated successfully")
                        else:
                            await ws.send_str(json.dumps({"status": "auth_fail"}))
                            log.warning(f"Wrong PIN from {request.remote}")
                            await ws.close()
                            return ws
                    else:
                        await ws.send_str(json.dumps({"status": "auth_required"}))
                    continue

                # ── Authenticated — handle commands ──
                handle_command(data)

    finally:
        pyautogui.mouseUp()
        with security["lock"]:
            if security["active_ws"] is ws:
                security["active_ws"] = None
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

def start_server(loop, ssl_ctx=None):
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.add_routes([web.get("/ws", websocket_handler),
                    web.get("/", serve_file),
                    web.get("/{filename}", serve_file)])
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    port = WSS_PORT if ssl_ctx else PORT
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", port, ssl_context=ssl_ctx).start())
    log.info(f"Server running on port {port} ({'WSS' if ssl_ctx else 'WS'})")
    loop.run_forever()

# ============================================================
# QR / Firewall / USB
# ============================================================
def cleanup_qr():
    for f in [QR_FILE, CERT_FILE, KEY_FILE]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

atexit.register(cleanup_qr)

def ensure_firewall_rule():
    def _run():
        try:
            for port in [PORT, WSS_PORT]:
                subprocess.run([
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    "name=PC Controller", "dir=in", "action=allow",
                    f"localport={port}", "protocol=tcp"
                ], capture_output=True, timeout=5)
        except Exception as e:
            log.warning(f"Firewall rule skipped: {e}")
    threading.Thread(target=_run, daemon=True).start()

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
        except: continue
    return None

def setup_usb(callback):
    def _run():
        adb = find_adb()
        if not adb:
            callback("error", "adb not found.\nInstall Android Studio first."); return
        callback("info", "Checking device…")
        try:
            devices = subprocess.run([adb, "devices"], capture_output=True,
                                     text=True, timeout=5)
            lines = [l for l in devices.stdout.strip().split("\n")[1:] if l.strip()]
            if not lines:
                callback("error", "No device found.\nConnect phone + allow USB Debugging."); return
            r = subprocess.run([adb, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                callback("ok", "✅ USB ready!\nOpen app → USB → Connect")
            else:
                callback("error", f"adb error:\n{r.stderr.strip()}")
        except Exception as e:
            callback("error", str(e))
    threading.Thread(target=_run, daemon=True).start()

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
        root.geometry("460x700")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Generate PIN
        pin = generate_pin()
        security["pin"] = pin
        security["pin_hash"] = hash_pin(pin)

        # Try SSL
        self.ssl_ctx = None
        if generate_self_signed_cert():
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(CERT_FILE, KEY_FILE)
                self.ssl_ctx = ctx
            except Exception as e:
                log.warning(f"SSL setup failed: {e}")

        self.ip   = get_local_ip()
        self.port = WSS_PORT if self.ssl_ctx else PORT
        self.url  = f"http://{self.ip}:{PORT}/"

        self._build_ui()
        self._start_server()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="PC Controller",
                  font=("Segoe UI", 16, "bold")).pack(pady=(0,4))

        # QR
        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=2)
        ttk.Label(frm, text=self.url, foreground="#3b82f6",
                  font=("Segoe UI", 9)).pack(pady=(0,4))

        # PIN — optional toggle
        pin_frm = ttk.LabelFrame(frm, text="🔐 Connection PIN (Optional)", padding=12)
        pin_frm.pack(fill="x", pady=(0,8))

        # Toggle row
        tog_row = ttk.Frame(pin_frm); tog_row.pack(fill="x", pady=(0,8))
        self.pin_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tog_row, text="Require PIN to connect",
                        variable=self.pin_enabled_var,
                        command=self._on_pin_toggle).pack(side="left")

        # PIN display (hidden by default)
        self.pin_content = ttk.Frame(pin_frm)
        pin_inner = ttk.Frame(self.pin_content); pin_inner.pack(fill="x")
        self.pin_lbl = ttk.Label(pin_inner,
                  text=security["pin"],
                  font=("Segoe UI", 32, "bold"),
                  foreground="#f59e0b")
        self.pin_lbl.pack(side="left")
        btn_col = ttk.Frame(pin_inner); btn_col.pack(side="right")
        ttk.Button(btn_col, text="🔄 New PIN",
                   command=self._regen_pin).pack(pady=(0,4))
        ttk.Button(btn_col, text="📋 Copy",
                   command=lambda: self._copy(security["pin"])).pack()
        ttk.Label(self.pin_content,
                  text="Share this PIN with whoever needs to connect",
                  font=("Segoe UI", 9), foreground="#888").pack(anchor="w")

        # Connection status
        status_frm = ttk.LabelFrame(frm, text="Connection Status", padding=10)
        status_frm.pack(fill="x", pady=(0,8))
        self.conn_var = tk.StringVar(value="⚪ No device connected")
        ttk.Label(status_frm, textvariable=self.conn_var,
                  font=("Segoe UI", 10)).pack(anchor="w")
        ttk.Button(status_frm, text="⛔ Kick Device",
                   command=self._kick).pack(anchor="e")

        # IP
        ip_frm = ttk.LabelFrame(frm, text="WiFi / Hotspot IP", padding=10)
        ip_frm.pack(fill="x", pady=(0,8))
        row = ttk.Frame(ip_frm); row.pack(fill="x")
        ttk.Label(row, text=self.ip, font=("Segoe UI", 18, "bold"),
                  foreground="#22c55e").pack(side="left")
        ttk.Button(row, text="📋 Copy",
                   command=lambda: self._copy(self.ip)).pack(side="right")
        enc = "🔒 Encrypted (WSS)" if self.ssl_ctx else "⚠️ Unencrypted (WS)"
        ttk.Label(ip_frm, text=enc,
                  font=("Segoe UI", 9),
                  foreground="#22c55e" if self.ssl_ctx else "#f59e0b").pack(anchor="w")

        # USB
        usb_frm = ttk.LabelFrame(frm, text="USB Connection", padding=10)
        usb_frm.pack(fill="x", pady=(0,8))
        ttk.Label(usb_frm,
                  text="Plug in your phone with USB Debugging ON, then click:",
                  font=("Segoe UI", 9), foreground="#888",
                  wraplength=400).pack(anchor="w", pady=(0,6))
        br = ttk.Frame(usb_frm); br.pack(fill="x")
        self.usb_btn = ttk.Button(br, text="🔌 Setup USB", command=self._do_usb)
        self.usb_btn.pack(side="left")
        self.usb_var = tk.StringVar(value="")
        self.usb_lbl = ttk.Label(br, textvariable=self.usb_var,
                                  font=("Segoe UI", 9), foreground="#888",
                                  wraplength=240)
        self.usb_lbl.pack(side="left", padx=(10,0))

        # Settings
        opts = ttk.LabelFrame(frm, text="Settings", padding=12)
        opts.pack(fill="x", pady=(0,6))
        sr = ttk.Frame(opts); sr.pack(fill="x", pady=(0,4))
        ttk.Label(sr, text="Mouse Speed:", font=("Segoe UI", 10)).pack(side="left")
        self.spd_lbl = ttk.Label(sr, text=f"{state['mouse_speed']:.1f}×",
                                  font=("Segoe UI", 10, "bold"), foreground="#3b82f6")
        self.spd_lbl.pack(side="right")
        self.spd_var = tk.DoubleVar(value=state["mouse_speed"])
        ttk.Scale(opts, from_=0.5, to=5.0, variable=self.spd_var,
                  orient="horizontal", command=self._on_speed).pack(fill="x", pady=(0,8))
        self.acc_var = tk.BooleanVar(value=state["acceleration_enabled"])
        ttk.Checkbutton(opts, text="Enable Mouse Acceleration",
                        variable=self.acc_var, command=self._on_acc).pack(anchor="w")

        self.status_var = tk.StringVar(value="Starting…")
        ttk.Label(frm, textvariable=self.status_var,
                  foreground="#888", font=("Segoe UI", 9)).pack(pady=(4,0))

    def _on_pin_toggle(self):
        enabled = self.pin_enabled_var.get()
        security["pin_enabled"] = enabled
        if enabled:
            self.pin_content.pack(fill="x", pady=(0,4))
        else:
            self.pin_content.pack_forget()
            self._kick()  # kick any connected device when disabling PIN
        log.info(f"PIN {'enabled' if enabled else 'disabled'}")

    def _regen_pin(self):
        pin = generate_pin()
        security["pin"] = pin
        security["pin_hash"] = hash_pin(pin)
        self.pin_lbl.config(text=pin)
        self._kick()
        log.info("PIN regenerated")

    def _kick(self):
        with security["lock"]:
            ws = security["active_ws"]
        if ws:
            asyncio.run_coroutine_threadsafe(ws.close(), self._loop)
            self.conn_var.set("⚪ No device connected")

    def _update_conn_status(self, connected: bool):
        self.root.after(0, lambda: self.conn_var.set(
            "🟢 Device connected" if connected else "⚪ No device connected"
        ))

    def _do_usb(self):
        self.usb_btn.config(state="disabled")
        self.usb_var.set("Working…")
        def cb(status, msg):
            def _u():
                self.usb_var.set(msg)
                self.usb_lbl.config(
                    foreground="#22c55e" if status=="ok" else
                    "#ef4444" if status=="error" else "#888")
                self.usb_btn.config(state="normal")
            self.root.after(0, _u)
        setup_usb(cb)

    def _on_speed(self, val):
        v = float(val); state["mouse_speed"] = v
        self.spd_lbl.config(text=f"{v:.1f}×")

    def _on_acc(self):
        state["acceleration_enabled"] = self.acc_var.get()

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _start_server(self):
        ensure_firewall_rule()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=start_server,
                         args=(self._loop, self.ssl_ctx), daemon=True).start()
        self.root.after(500, self._load_qr)
        proto = "WSS 🔒" if self.ssl_ctx else "WS ⚠️"
        self.root.after(600, lambda: self.status_var.set(
            f"✅ Running — {self.ip}:{self.port} ({proto})"))

    def _load_qr(self):
        try:
            f = generate_qr_image(self.url)
            im = Image.open(f).resize((150, 150))
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
