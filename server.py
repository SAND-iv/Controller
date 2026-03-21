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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------- pyautogui perf ----------
pyautogui.MINIMUM_DURATION = 0
pyautogui.MINIMUM_SLEEP = 0
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

# ---------- config ----------
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8080
DEFAULT_MOUSE_SPEED = 1.5
SCROLL_MULTIPLIER = 4
QR_FILE = os.path.join(WEB_DIR, "controller_qr.png")

keyboard = KeyController()

keymap = {
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "ENTER": Key.enter, "BACKSPACE": Key.backspace, "TAB": Key.tab, "ESC": Key.esc,
    " ": " ",
    "vol_up": Key.media_volume_up, "vol_down": Key.media_volume_down,
    "mute": Key.media_volume_mute, "play": Key.media_play_pause,
    "next": Key.media_next, "prev": Key.media_previous,
    "win": Key.cmd,
}
for i in range(65, 91):
    keymap[chr(i)] = chr(i).lower()

def press_key(k):   keyboard.press(keymap.get(k, k))
def release_key(k): keyboard.release(keymap.get(k, k))

# ---------- shared state ----------
state = {
    "mouse_speed": DEFAULT_MOUSE_SPEED,
    "acceleration_enabled": False,
}

# ---------- QR cleanup ----------
def cleanup_qr():
    if os.path.exists(QR_FILE):
        try:
            os.remove(QR_FILE)
            log.info("QR code deleted")
        except Exception as e:
            log.warning(f"Could not delete QR: {e}")

atexit.register(cleanup_qr)

# ============================================================
# Command dispatcher
# ============================================================
def handle_command(data: dict):
    cmd = data.get("command")
    try:
        if cmd == "type":
            keyboard.type(data.get("text", ""))
        elif cmd == "key":
            k = data.get("key")
            if k in keymap:
                press_key(k); release_key(k)
        elif cmd == "drag_start":  pyautogui.mouseDown()
        elif cmd == "drag_end":    pyautogui.mouseUp()
        elif cmd == "hold":        press_key(data["key"])
        elif cmd == "release":     release_key(data["key"])
        elif cmd == "move":
            dx = float(data.get("dx", 0))
            dy = float(data.get("dy", 0))
            speed = state["mouse_speed"]
            factor = max(1.0, 1.0 + (abs(dx)+abs(dy))/8.0) if state["acceleration_enabled"] else 1.0
            pyautogui.moveRel(dx * speed * factor, dy * speed * factor)
        elif cmd == "click":
            btn = data.get("button")
            if btn == "left":    pyautogui.click()
            elif btn == "right": pyautogui.rightClick()
        elif cmd == "scroll":
            pyautogui.scroll(int(int(data.get("dy", 0)) * SCROLL_MULTIPLIER))
        elif cmd == "set_speed":
            v = float(data.get("value", DEFAULT_MOUSE_SPEED))
            state["mouse_speed"] = v
            log.info(f"Speed set to {v:.1f}")
        elif cmd == "set_acc":
            state["acceleration_enabled"] = bool(data.get("value"))
        elif cmd == "key_toggle":
            target = {"ctrl": Key.ctrl, "alt": Key.alt,
                      "shift": Key.shift, "cmd": Key.cmd}.get(data.get("key"))
            if target:
                if data.get("state") == "down": keyboard.press(target)
                elif data.get("state") == "up":  keyboard.release(target)
    except Exception as e:
        log.error(f"Command error ({cmd}): {e}")


# ============================================================
# WiFi — WebSocket server
# ============================================================
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    log.info("Client connected")
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    handle_command(json.loads(msg.data))
                except Exception as e:
                    log.error(f"Parse error: {e}")
    finally:
        pyautogui.mouseUp()
        log.info("Client disconnected, mouse released")
    return ws

async def serve_file(request):
    filename = request.match_info.get("filename", "controller.html")
    path = os.path.join(WEB_DIR, filename)
    if not os.path.exists(path):
        return web.Response(status=404, text="Not found")
    mime = {".json":"application/json", ".js":"application/javascript",
            ".png":"image/png", ".html":"text/html"}
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
    log.info(f"Server running → http://0.0.0.0:{PORT}/")
    loop.run_forever()


# ============================================================
# Helpers
# ============================================================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

def generate_qr_image(url):
    qrcode.make(url).save(QR_FILE)
    return QR_FILE


# ============================================================
# GUI
# ============================================================
class ServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("PC Controller Server")
        root.geometry("420x560")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.ip  = get_local_ip()
        self.url = f"http://{self.ip}:{PORT}/"
        self._build_ui()
        self._start_server()

    def _build_ui(self):
        # Main frame
        frm = ttk.Frame(self.root, padding=16)
        frm.pack(fill="both", expand=True)

        # Title
        ttk.Label(frm, text="PC Controller Server",
                  font=("Segoe UI", 15, "bold")).pack(pady=(0, 4))

        # QR code
        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=4)

        # URL
        ttk.Label(frm, text=self.url, foreground="#3b82f6",
                  font=("Segoe UI", 9)).pack(pady=(0, 6))

        # IP display
        ip_frm = ttk.LabelFrame(frm, text="Your PC IP Address", padding=10)
        ip_frm.pack(fill="x", pady=(0, 10))

        ip_inner = ttk.Frame(ip_frm)
        ip_inner.pack(fill="x")
        ttk.Label(ip_inner, text=self.ip,
                  font=("Segoe UI", 22, "bold"),
                  foreground="#22c55e").pack(side="left")
        ttk.Button(ip_inner, text="Copy",
                   command=lambda: self._copy(self.ip)).pack(side="right")
        ttk.Label(ip_frm, text="Enter this in the mobile app",
                  font=("Segoe UI", 9), foreground="#888").pack(anchor="w")

        # Settings
        opts = ttk.LabelFrame(frm, text="Settings", padding=12)
        opts.pack(fill="x", pady=(0, 6))

        # Speed slider
        speed_row = ttk.Frame(opts)
        speed_row.pack(fill="x", pady=(0, 8))
        ttk.Label(speed_row, text="Mouse Speed:",
                  font=("Segoe UI", 10)).pack(side="left")
        self.speed_label = ttk.Label(speed_row,
                  text=f"{state['mouse_speed']:.1f}×",
                  font=("Segoe UI", 10, "bold"), foreground="#3b82f6")
        self.speed_label.pack(side="right")

        self.speed_var = tk.DoubleVar(value=state["mouse_speed"])
        speed_scale = ttk.Scale(opts, from_=0.5, to=5.0,
                                variable=self.speed_var,
                                orient="horizontal",
                                command=self._on_speed_change)
        speed_scale.pack(fill="x", pady=(0, 10))

        # Acceleration checkbox
        self.acc_var = tk.BooleanVar(value=state["acceleration_enabled"])
        acc_cb = ttk.Checkbutton(opts, text="Enable Mouse Acceleration",
                                  variable=self.acc_var,
                                  command=self._on_acc_change)
        acc_cb.pack(anchor="w")

        # Status
        self.status_var = tk.StringVar(value="Starting server…")
        ttk.Label(frm, textvariable=self.status_var,
                  foreground="#888", font=("Segoe UI", 9)).pack(pady=(4, 0))

    def _on_speed_change(self, val):
        v = float(val)
        state["mouse_speed"] = v
        self.speed_label.config(text=f"{v:.1f}×")

    def _on_acc_change(self):
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
            f"✅ Running — connect to {self.ip}"))

    def _load_qr(self):
        try:
            f = generate_qr_image(self.url)
            im = Image.open(f).resize((180, 180))
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
