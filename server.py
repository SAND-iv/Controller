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

state = {"mouse_speed": DEFAULT_MOUSE_SPEED, "acceleration_enabled": False}

# ---------- delete QR on exit ----------
def cleanup_qr():
    if os.path.exists(QR_FILE):
        try:
            os.remove(QR_FILE)
            log.info("QR code deleted")
        except Exception as e:
            log.warning(f"Could not delete QR: {e}")

atexit.register(cleanup_qr)

# ============================================================
# Shared command dispatcher
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
            if btn == "left":  pyautogui.click()
            elif btn == "right": pyautogui.rightClick()
        elif cmd == "scroll":
            pyautogui.scroll(int(int(data.get("dy", 0)) * SCROLL_MULTIPLIER))
        elif cmd == "set_speed":
            state["mouse_speed"] = float(data.get("value", DEFAULT_MOUSE_SPEED))
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
# WiFi — aiohttp WebSocket server
# ============================================================
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    log.info("WiFi client connected")
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    handle_command(json.loads(msg.data))
                except Exception as e:
                    log.error(f"WiFi parse error: {e}")
    finally:
        pyautogui.mouseUp()
        log.info("WiFi client disconnected")
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
    log.info(f"WiFi server → http://0.0.0.0:{PORT}/")
    loop.run_forever()

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
        root.title("PC Controller Server")
        root.geometry("400x520")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.ip  = get_local_ip()
        self.url = f"http://{self.ip}:{PORT}/"
        self._build_ui()
        self._start_servers()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=20)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="PC Controller Server",
                  font=("Segoe UI", 16, "bold")).pack(pady=(0, 4))
        ttk.Label(frm, text="Scan QR or enter IP in the app",
                  font=("Segoe UI", 10), foreground="#888").pack(pady=(0, 10))

        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=4)

        ttk.Label(frm, text=self.url, foreground="#3b82f6").pack(pady=4)

        # IP highlight box
        ip_frm = ttk.LabelFrame(frm, text="Your PC IP", padding=10)
        ip_frm.pack(fill="x", pady=8)
        ttk.Label(ip_frm, text=self.ip,
                  font=("Segoe UI", 18, "bold"), foreground="#22c55e").pack()
        ttk.Label(ip_frm, text="Enter this in the mobile app",
                  font=("Segoe UI", 9), foreground="#888").pack()

        opts = ttk.LabelFrame(frm, text="Settings", padding=12)
        opts.pack(fill="x", pady=6)
        ttk.Label(opts, text="Base Mouse Speed").pack(anchor="w")
        self.speed_var = tk.DoubleVar(value=state["mouse_speed"])
        ttk.Scale(opts, from_=0.5, to=5.0, variable=self.speed_var,
                  command=lambda v: state.update({"mouse_speed": float(v)})).pack(fill="x", pady=(4,12))
        self.acc = tk.BooleanVar(value=state["acceleration_enabled"])
        ttk.Checkbutton(opts, text="Enable Acceleration", variable=self.acc,
                        command=lambda: state.update({"acceleration_enabled": self.acc.get()})).pack(anchor="w")

    def _start_servers(self):
        threading.Thread(target=start_wifi_server,
                         args=(asyncio.new_event_loop(),), daemon=True).start()
        self._show_qr(generate_qr_image(self.url))

    def _show_qr(self, f):
        im = Image.open(f).resize((180, 180))
        self.qr_img = ImageTk.PhotoImage(im)
        self.qr_label.config(image=self.qr_img)

    def _on_close(self):
        cleanup_qr()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    ServerGUI(root)
    root.mainloop()
