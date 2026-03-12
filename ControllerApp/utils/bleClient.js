// utils/bleClient.js
// Manages a BLE GATT connection to the PC server.
// Uses the chunked write protocol matching server.py:
//   Each write = [chunk_idx (1 byte)][total_chunks (1 byte)][payload bytes...]
// MTU payload size is kept at 18 bytes to be safe on all devices.

import { BleManager } from "react-native-ble-plx";
import { Buffer } from "buffer";

export const SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0";
export const CHAR_UUID    = "12345678-1234-5678-1234-56789abcdef1";
export const DEVICE_NAME  = "PC Controller";
const CHUNK_PAYLOAD = 18; // bytes of JSON payload per BLE write

let manager = null;
let device  = null;
let characteristic = null;
let onStatusChange = null;

export function getBleManager() {
  if (!manager) manager = new BleManager();
  return manager;
}

export async function scanAndConnect(statusCallback) {
  onStatusChange = statusCallback;
  const mgr = getBleManager();

  return new Promise((resolve, reject) => {
    onStatusChange("scanning");

    mgr.startDeviceScan(null, { allowDuplicates: false }, async (error, scannedDevice) => {
      if (error) {
        onStatusChange("scan_error");
        reject(error);
        return;
      }

      if (scannedDevice?.name === DEVICE_NAME) {
        mgr.stopDeviceScan();
        onStatusChange("connecting");

        try {
          device = await scannedDevice.connect();
          await device.discoverAllServicesAndCharacteristics();

          const services = await device.services();
          const service  = services.find(s => s.uuid.toLowerCase() === SERVICE_UUID.toLowerCase());
          if (!service) throw new Error("Service not found on device");

          const chars = await service.characteristics();
          characteristic = chars.find(c => c.uuid.toLowerCase() === CHAR_UUID.toLowerCase());
          if (!characteristic) throw new Error("Characteristic not found");

          device.onDisconnected(() => {
            characteristic = null;
            device = null;
            onStatusChange("disconnected");
          });

          onStatusChange("connected");
          resolve(device);
        } catch (err) {
          onStatusChange("error");
          reject(err);
        }
      }
    });

    // Stop scanning after 15 seconds if nothing found
    setTimeout(() => {
      mgr.stopDeviceScan();
      if (!device) {
        onStatusChange("not_found");
        reject(new Error("Device not found within timeout"));
      }
    }, 15000);
  });
}

export function sendBle(data) {
  if (!characteristic) return;

  const json   = JSON.stringify(data);
  const bytes  = Buffer.from(json, "utf-8");
  const total  = Math.ceil(bytes.length / CHUNK_PAYLOAD);

  for (let i = 0; i < total; i++) {
    const payload = bytes.slice(i * CHUNK_PAYLOAD, (i + 1) * CHUNK_PAYLOAD);
    const packet  = Buffer.concat([Buffer.from([i, total]), payload]);
    const b64     = packet.toString("base64");

    characteristic.writeWithoutResponse(b64).catch(err => {
      console.warn("BLE write error:", err);
    });
  }
}

export function disconnectBle() {
  device?.cancelConnection();
  device = null;
  characteristic = null;
}

export function destroyBleManager() {
  manager?.destroy();
  manager = null;
}
