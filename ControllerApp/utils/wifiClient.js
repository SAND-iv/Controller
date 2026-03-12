// utils/wifiClient.js
// Manages a WebSocket connection to the PC server over WiFi.

let ws = null;
let reconnectTimer = null;
let onStatusChange = null;

export function initWifi(ip, statusCallback) {
  onStatusChange = statusCallback;
  _connect(ip);
}

function _connect(ip) {
  if (ws) {
    ws.close();
    ws = null;
  }

  const url = `ws://${ip}:8080/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    onStatusChange?.("connected");
  };

  ws.onclose = () => {
    onStatusChange?.("disconnected");
    reconnectTimer = setTimeout(() => _connect(ip), 2000);
  };

  ws.onerror = () => {
    onStatusChange?.("error");
  };
}

export function sendWifi(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

export function disconnectWifi() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
  ws?.close();
  ws = null;
}
