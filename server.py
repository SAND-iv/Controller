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

if getattr(sys, 'frozen', False):
    WEB_DIR  = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    WEB_DIR  = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = WEB_DIR

PORT               = 8080
DEFAULT_SPEED      = 1.5
SCROLL_MULTIPLIER  = 4
QR_FILE            = os.path.join(BASE_DIR, "controller_qr.png")

keyboard = KeyController()

KEYMAP = {
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "ENTER": Key.enter, "BACKSPACE": Key.backspace, "TAB": Key.tab, "ESC": Key.esc,
    " ": " ",
    "vol_up": Key.media_volume_up,   "vol_down": Key.media_volume_down,
    "mute":   Key.media_volume_mute, "play":     Key.media_play_pause,
    "next":   Key.media_next,        "prev":     Key.media_previous,
    "win":    Key.cmd,
}
for i in range(65, 91):
    KEYMAP[chr(i)] = chr(i).lower()

ALLOWED = {
    "type", "key", "drag_start", "drag_end", "hold", "release",
    "move", "click", "scroll", "set_speed", "set_acc", "key_toggle", "ping"
}

state = {"speed": DEFAULT_SPEED, "accel": False}

conn = {
    "ws":   None,
    "lock": threading.Lock(),
    "on_connect":    None,
    "on_disconnect": None,
}


def handle_command(data: dict):
    cmd = data.get("command")
    if cmd not in ALLOWED:
        return
    try:
        if cmd == "type":
            text = data.get("text", "")
            if len(text) <= 500:
                keyboard.type(text)

        elif cmd == "key":
            k = data.get("key")
            if k in KEYMAP:
                keyboard.press(KEYMAP[k])
                keyboard.release(KEYMAP[k])

        elif cmd == "drag_start":
            pyautogui.mouseDown()

        elif cmd == "drag_end":
            pyautogui.mouseUp()

        elif cmd == "move":
            dx = max(-200, min(200, float(data.get("dx", 0))))
            dy = max(-200, min(200, float(data.get("dy", 0))))
            spd = state["speed"]
            fac = max(1.0, 1.0 + (abs(dx) + abs(dy)) / 8.0) if state["accel"] else 1.0
            pyautogui.moveRel(dx * spd * fac, dy * spd * fac)

        elif cmd == "click":
            btn = data.get("button")
            if btn == "left":
                pyautogui.click()
            elif btn == "right":
                pyautogui.rightClick()

        elif cmd == "scroll":
            dy = max(-20, min(20, int(data.get("dy", 0))))
            pyautogui.scroll(dy * SCROLL_MULTIPLIER)

        elif cmd == "set_speed":
            state["speed"] = max(0.5, min(5.0, float(data.get("value", DEFAULT_SPEED))))

        elif cmd == "set_acc":
            state["accel"] = bool(data.get("value"))

        elif cmd == "key_toggle":
            mod = {"ctrl": Key.ctrl, "alt": Key.alt,
                   "shift": Key.shift, "cmd": Key.cmd}.get(data.get("key"))
            if mod:
                if data.get("state") == "down":
                    keyboard.press(mod)
                elif data.get("state") == "up":
                    keyboard.release(mod)

    except Exception as e:
        log.error(f"Command error ({cmd}): {e}")


async def websocket_handler(request):
    with conn["lock"]:
        if conn["ws"] is not None:
            return web.Response(status=409, text="Already connected")

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    log.info(f"Connected: {request.remote}")

    with conn["lock"]:
        conn["ws"] = ws
    await ws.send_str(json.dumps({"status": "auth_ok"}))
    if conn["on_connect"]:
        conn["on_connect"]()

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    handle_command(json.loads(msg.data))
                except Exception as e:
                    log.error(f"Bad message: {e}")
    finally:
        pyautogui.mouseUp()
        with conn["lock"]:
            if conn["ws"] is ws:
                conn["ws"] = None
                if conn["on_disconnect"]:
                    conn["on_disconnect"]()
        log.info("Disconnected")

    return ws


async def serve_file(request):
    filename = request.match_info.get("filename", "controller.html")
    path = os.path.join(WEB_DIR, filename)
    if not os.path.exists(path):
        return web.Response(status=404, text="Not found")
    mime = {
        ".html": "text/html", ".js": "application/javascript",
        ".json": "application/json", ".png": "image/png"
    }
    ct = mime.get(os.path.splitext(filename)[1], "application/octet-stream")
    return web.FileResponse(path, headers={"Content-Type": ct})


def start_server(loop):
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.add_routes([
        web.get("/ws", websocket_handler),
        web.get("/", serve_file),
        web.get("/{filename}", serve_file),
    ])
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", PORT).start())
    loop.run_forever()


def cleanup_qr():
    try:
        os.remove(QR_FILE)
    except FileNotFoundError:
        pass

atexit.register(cleanup_qr)


def ensure_firewall_rule():
    def _run():
        try:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", "name=PC Controller"],
                capture_output=True, timeout=5
            )
            subprocess.run([
                "netsh", "advfirewall", "firewall", "add", "rule",
                "name=PC Controller", "dir=in", "action=allow",
                f"localport={PORT}", "protocol=tcp", "profile=any"
            ], capture_output=True, timeout=5)
        except Exception as e:
            log.warning(f"Firewall: {e}")
    threading.Thread(target=_run, daemon=True).start()


def find_adb():
    candidates = [
        "adb",
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
    ]
    for path in candidates:
        try:
            if subprocess.run([path, "version"], capture_output=True, timeout=3).returncode == 0:
                return path
        except Exception:
            continue
    return None


def setup_usb(callback):
    def _run():
        adb = find_adb()
        if not adb:
            callback("error", "adb not found.\nInstall Android Studio first.")
            return

        callback("info", "Checking device…")
        try:
            result = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5)
            devices = [l for l in result.stdout.strip().split("\n")[1:] if l.strip()]
            if not devices:
                callback("error", "No device found.\nConnect phone + allow USB Debugging.")
                return

            r = subprocess.run(
                [adb, "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                callback("ok", "✅ USB ready!\nOpen app → USB → Connect")
            else:
                callback("error", f"adb error:\n{r.stderr.strip()}")
        except Exception as e:
            callback("error", str(e))

    threading.Thread(target=_run, daemon=True).start()


def get_local_ip():
    ips = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    seen, unique = set(), []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique.append(ip)

    # Hotspot addresses take priority over regular WiFi
    for ip in unique:
        if ip.startswith("192.168.43."):
            return ip
    for ip in unique:
        if any(ip.startswith(p) for p in ("192.168.", "10.", "172.")):
            return ip
    return unique[0] if unique else "127.0.0.1"


def generate_qr(url):
    qrcode.make(url).save(QR_FILE)
    return QR_FILE


class ServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("PC Controller")
        root.geometry("460x700")
        root.resizable(True, True)
        root.minsize(400, 500)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.ip  = get_local_ip()
        self.url = f"http://{self.ip}:{PORT}/"

        self._build_ui()
        self._start_server()

    def _build_ui(self):
        canvas = tk.Canvas(self.root, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frm = ttk.Frame(canvas, padding=16)
        win = canvas.create_window((0, 0), window=frm, anchor="nw")

        frm.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        ttk.Label(frm, text="PC Controller", font=("Segoe UI", 16, "bold")).pack(pady=(0, 4))

        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=2)

        self.url_lbl = ttk.Label(frm, text=self.url, foreground="#3b82f6", font=("Segoe UI", 9))
        self.url_lbl.pack(pady=(0, 4))

        status_frm = ttk.LabelFrame(frm, text="Connection Status", padding=10)
        status_frm.pack(fill="x", pady=(0, 8))
        self.conn_var = tk.StringVar(value="⚪ No device connected")
        ttk.Label(status_frm, textvariable=self.conn_var, font=("Segoe UI", 10)).pack(anchor="w")
        ttk.Button(status_frm, text="⛔ Kick Device", command=self._kick).pack(anchor="e")

        ip_frm = ttk.LabelFrame(frm, text="WiFi / Hotspot IP", padding=10)
        ip_frm.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(ip_frm)
        row.pack(fill="x")
        self.ip_lbl = ttk.Label(row, text=self.ip, font=("Segoe UI", 18, "bold"), foreground="#22c55e")
        self.ip_lbl.pack(side="left")
        ttk.Button(row, text="📋 Copy", command=lambda: self._copy(self.ip)).pack(side="right")
        ttk.Label(ip_frm, text="Enter this in the app", font=("Segoe UI", 9), foreground="#888").pack(anchor="w")

        usb_frm = ttk.LabelFrame(frm, text="USB Connection", padding=10)
        usb_frm.pack(fill="x", pady=(0, 8))
        ttk.Label(usb_frm, text="Connect phone with USB Debugging ON, then click:",
                  font=("Segoe UI", 9), foreground="#888", wraplength=400).pack(anchor="w", pady=(0, 6))
        br = ttk.Frame(usb_frm)
        br.pack(fill="x")
        self.usb_btn = ttk.Button(br, text="🔌 Setup USB", command=self._do_usb)
        self.usb_btn.pack(side="left")
        self.usb_var = tk.StringVar(value="")
        self.usb_lbl = ttk.Label(br, textvariable=self.usb_var, font=("Segoe UI", 9),
                                  foreground="#888", wraplength=240)
        self.usb_lbl.pack(side="left", padx=(10, 0))

        settings = ttk.LabelFrame(frm, text="Settings", padding=12)
        settings.pack(fill="x", pady=(0, 6))
        spd_row = ttk.Frame(settings)
        spd_row.pack(fill="x", pady=(0, 4))
        ttk.Label(spd_row, text="Mouse Speed:", font=("Segoe UI", 10)).pack(side="left")
        self.spd_lbl = ttk.Label(spd_row, text=f"{state['speed']:.1f}×",
                                  font=("Segoe UI", 10, "bold"), foreground="#3b82f6")
        self.spd_lbl.pack(side="right")
        self.spd_var = tk.DoubleVar(value=state["speed"])
        ttk.Scale(settings, from_=0.5, to=5.0, variable=self.spd_var,
                  orient="horizontal", command=self._on_speed).pack(fill="x", pady=(0, 8))
        self.acc_var = tk.BooleanVar(value=state["accel"])
        ttk.Checkbutton(settings, text="Enable Mouse Acceleration",
                        variable=self.acc_var, command=self._on_acc).pack(anchor="w")

        self.status_var = tk.StringVar(value="Starting…")
        ttk.Label(frm, textvariable=self.status_var, foreground="#888",
                  font=("Segoe UI", 9)).pack(pady=(4, 0))

    def _kick(self):
        with conn["lock"]:
            ws = conn["ws"]
        if ws:
            async def _close():
                try:
                    await ws.send_str(json.dumps({"status": "kicked"}))
                    await ws.close()
                except Exception:
                    pass
            asyncio.run_coroutine_threadsafe(_close(), self._loop)
            self.conn_var.set("⚪ No device connected")

    def _do_usb(self):
        self.usb_btn.config(state="disabled")
        self.usb_var.set("Working…")

        def cb(status, msg):
            def update():
                self.usb_var.set(msg)
                self.usb_lbl.config(foreground={
                    "ok": "#22c55e", "error": "#ef4444"
                }.get(status, "#888"))
                self.usb_btn.config(state="normal")
            self.root.after(0, update)

        setup_usb(cb)

    def _on_speed(self, val):
        state["speed"] = float(val)
        self.spd_lbl.config(text=f"{float(val):.1f}×")

    def _on_acc(self):
        state["accel"] = self.acc_var.get()

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _start_server(self):
        ensure_firewall_rule()
        conn["on_connect"]    = lambda: self.root.after(0, lambda: self.conn_var.set("🟢 Device connected"))
        conn["on_disconnect"] = lambda: self.root.after(0, lambda: self.conn_var.set("⚪ No device connected"))
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=start_server, args=(self._loop,), daemon=True).start()
        self.root.after(500,  self._load_qr)
        self.root.after(600,  lambda: self.status_var.set(f"✅ Running — {self.ip}:{PORT}"))
        self.root.after(1500, self._watch_ip)

    def _watch_ip(self):
        new_ip = get_local_ip()
        if new_ip != self.ip:
            self.ip  = new_ip
            self.url = f"http://{new_ip}:{PORT}/"
            self.ip_lbl.config(text=new_ip)
            self.url_lbl.config(text=self.url)
            self._load_qr()
            self.status_var.set(f"✅ Running — {new_ip}:{PORT}")
            self._kick()
            log.info(f"IP changed → {new_ip}")
        self.root.after(1500, self._watch_ip)

    def _load_qr(self):
        try:
            img = Image.open(generate_qr(self.url)).resize((150, 150))
            self.qr_img = ImageTk.PhotoImage(img)
            self.qr_label.config(image=self.qr_img)
        except Exception as e:
            log.error(f"QR: {e}")

    def _on_close(self):
        cleanup_qr()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    ServerGUI(root)
    root.mainloop()
