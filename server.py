import asyncio
import json
import os
import socket
import qrcode
from PIL import Image, ImageTk
import threading
import tkinter as tk
from tkinter import ttk
from aiohttp import web
from pynput.keyboard import Controller as KeyController, Key
import pyautogui

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

keyboard = KeyController()

# Extended Keymap
keymap = {
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "ENTER": Key.enter, "BACKSPACE": Key.backspace, "TAB": Key.tab, "ESC": Key.esc,
    " ": " ",
    "vol_up": Key.media_volume_up, "vol_down": Key.media_volume_down,
    "mute": Key.media_volume_mute, "play": Key.media_play_pause,
    "next": Key.media_next, "prev": Key.media_previous
}
for i in range(65, 91):
    keymap[chr(i)] = chr(i).lower()

def press_key(k):
    keyboard.press(keymap.get(k, k))

def release_key(k):
    keyboard.release(keymap.get(k, k))

# ---------- helpers ----------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except:
        return "127.0.0.1"
    finally:
        s.close()

def generate_qr_image(url, file="controller_qr.png"):
    qr = qrcode.make(url)
    qr.save(file)
    return file

state = {
    "mouse_speed": DEFAULT_MOUSE_SPEED,
    "acceleration_enabled": False,
}

# ---------- websocket ----------
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    cmd = data.get("command")

                    if cmd == "type":
                        keyboard.type(data.get("text", ""))

                    elif cmd == "key":
                        k = data.get("key")
                        if k in keymap:
                            press_key(k)
                            release_key(k)

                    # --- NEW: DRAG SUPPORT ---
                    elif cmd == "drag_start":
                        pyautogui.mouseDown() # Holds Left Click
                    
                    elif cmd == "drag_end":
                        pyautogui.mouseUp()   # Releases Left Click
                    # -------------------------

                    elif cmd == "hold":
                        press_key(data["key"])

                    elif cmd == "release":
                        release_key(data["key"])

                    elif cmd == "move":
                        dx = float(data.get("dx", 0))
                        dy = float(data.get("dy", 0))
                        speed = state["mouse_speed"]
                        if state["acceleration_enabled"]:
                            factor = (abs(dx) + abs(dy)) / 8.0
                            factor = max(1.0, 1.0 + factor)
                        else:
                            factor = 1.0
                        pyautogui.moveRel(dx * speed * factor, dy * speed * factor)

                    elif cmd == "click":
                        btn = data["button"]
                        if btn == "left": pyautogui.click()
                        elif btn == "right": pyautogui.rightClick()

                    elif cmd == "scroll":
                        dy = int(data.get("dy", 0))
                        pyautogui.scroll(int(dy * SCROLL_MULTIPLIER))

                    elif cmd == "set_speed":
                        state["mouse_speed"] = float(data.get("value", DEFAULT_MOUSE_SPEED))
                    
                    elif cmd == "set_acc":
                        state["acceleration_enabled"] = bool(data.get("value"))

                except Exception as e:
                    print(f"Error: {e}")
    finally:
        # Safety: Release mouse if connection drops while dragging
        pyautogui.mouseUp()
        print("Connection closed, released mouse.")

    return ws

# ---------- static server ----------
async def serve_file(request):
    filename = request.match_info.get("filename", "controller.html")
    path = os.path.join(WEB_DIR, filename)

    if not os.path.exists(path):
        return web.Response(status=404, text="Not found")

    headers = {}
    if filename.endswith(".json"): headers["Content-Type"] = "application/json"
    elif filename.endswith(".js"): headers["Content-Type"] = "application/javascript"
    elif filename.endswith(".png"): headers["Content-Type"] = "image/png"
    elif filename.endswith(".html"): headers["Content-Type"] = "text/html"

    return web.FileResponse(path, headers=headers)

# ---------- aio thread ----------
def start_web_server(loop):
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.add_routes([
        web.get('/ws', websocket_handler),
        web.get('/', serve_file),
        web.get('/{filename}', serve_file)
    ])
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    loop.run_until_complete(site.start())
    print(f"Server running at http://0.0.0.0:{PORT}/")
    loop.run_forever()

# ---------- GUI ----------
class ServerGUI:
    def __init__(self, root):
        self.root = root
        root.title("Phone Controller")
        root.geometry("400x550")
        root.resizable(False, False)

        self.ip = get_local_ip()
        self.url = f"http://{self.ip}:{PORT}/"

        self.create_widgets()

        self.http_loop = asyncio.new_event_loop()
        threading.Thread(target=start_web_server, args=(self.http_loop,), daemon=True).start()

        qr_file = generate_qr_image(self.url)
        self.show_qr(qr_file)

    def create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 11))

        frm = ttk.Frame(self.root, padding=20)
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text="Scan to Connect", font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))
        self.qr_label = ttk.Label(frm)
        self.qr_label.pack(pady=10)
        ttk.Label(frm, text=self.url, foreground="blue", cursor="hand2").pack(pady=5)
        
        opts = ttk.LabelFrame(frm, text="Settings", padding=15)
        opts.pack(fill='x', pady=20)

        ttk.Label(opts, text="Base Mouse Speed").pack(anchor='w')
        self.speed_var = tk.DoubleVar(value=state["mouse_speed"])
        def update_speed(v): state["mouse_speed"] = float(v)
        s = ttk.Scale(opts, from_=0.5, to=5.0, variable=self.speed_var, command=update_speed)
        s.pack(fill='x', pady=(5, 15))

        self.acc = tk.BooleanVar(value=state["acceleration_enabled"])
        def update_acc(): state["acceleration_enabled"] = self.acc.get()
        ttk.Checkbutton(opts, text="Enable Acceleration", variable=self.acc, command=update_acc).pack(anchor='w')

    def show_qr(self, f):
        im = Image.open(f).resize((220, 220))
        self.qr_img = ImageTk.PhotoImage(im)
        self.qr_label.config(image=self.qr_img)

if __name__ == "__main__":
    root = tk.Tk()
    gui = ServerGUI(root)
    root.mainloop()