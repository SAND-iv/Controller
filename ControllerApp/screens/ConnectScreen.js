// screens/ConnectScreen.js
import React, { useState, useEffect } from "react";
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ActivityIndicator, Alert,
  KeyboardAvoidingView, Platform, ScrollView,
} from "react-native";
import { scanAndConnect } from "../utils/bleClient";
import { initWifi }        from "../utils/wifiClient";
import { BleManager }      from "react-native-ble-plx";
import { requestMultiple, PERMISSIONS, RESULTS } from "react-native-permissions";

const C = {
  bg: "#0f1113", panel: "#1a1c1e", btn: "#2a2d30",
  accent: "#3b82f6", text: "#e2e8f0", muted: "#94a3b8",
  green: "#22c55e", red: "#ef4444",
};

const BLE_STATUS_LABELS = {
  idle: "Tap to scan",
  scanning: "Scanning for PC Controller…",
  connecting: "Connecting…",
  connected: "Connected via Bluetooth!",
  disconnected: "Disconnected",
  not_found: "Device not found. Is the server running?",
  scan_error: "Scan error — check Bluetooth permissions",
  error: "Connection failed",
};

export default function ConnectScreen({ navigation }) {
  const [mode, setMode]       = useState(null);   // "wifi" | "ble"
  const [ip, setIp]           = useState("");
  const [wifiStatus, setWifi] = useState("idle"); // idle | connecting | connected | error
  const [bleStatus, setBle]   = useState("idle");

  // ---- WiFi ----
  function connectWifi() {
    if (!ip.trim()) { Alert.alert("Enter IP", "Please enter your PC's IP address."); return; }
    setWifi("connecting");
    initWifi(ip.trim(), (status) => {
      setWifi(status);
      if (status === "connected") {
        navigation.replace("Controller", { mode: "wifi" });
      }
    });
  }

  // ---- BLE ----
  async function connectBle() {
    if (Platform.OS === "android") {
      const granted = await requestMultiple([
        PERMISSIONS.ANDROID.BLUETOOTH_SCAN,
        PERMISSIONS.ANDROID.BLUETOOTH_CONNECT,
        PERMISSIONS.ANDROID.ACCESS_FINE_LOCATION,
      ]);
      const allGranted = Object.values(granted).every(r => r === RESULTS.GRANTED);
      if (!allGranted) {
        Alert.alert("Permissions needed", "Bluetooth permissions are required to scan for your PC.");
        return;
      }
    }

    try {
      await scanAndConnect((status) => {
        setBle(status);
        if (status === "connected") {
          navigation.replace("Controller", { mode: "ble" });
        }
      });
    } catch (err) {
      console.warn("BLE connect error:", err.message);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">

        <Text style={styles.title}>PC Controller</Text>
        <Text style={styles.subtitle}>Choose how to connect</Text>

        {/* Mode selector */}
        <View style={styles.modeRow}>
          <TouchableOpacity
            style={[styles.modeBtn, mode === "wifi" && styles.modeBtnActive]}
            onPress={() => setMode("wifi")}>
            <Text style={styles.modeIcon}>📡</Text>
            <Text style={[styles.modeLabel, mode === "wifi" && styles.modeLabelActive]}>WiFi</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeBtn, mode === "ble" && styles.modeBtnActive]}
            onPress={() => setMode("ble")}>
            <Text style={styles.modeIcon}>🔵</Text>
            <Text style={[styles.modeLabel, mode === "ble" && styles.modeLabelActive]}>Bluetooth</Text>
          </TouchableOpacity>
        </View>

        {/* WiFi panel */}
        {mode === "wifi" && (
          <View style={styles.panel}>
            <Text style={styles.panelTitle}>Enter your PC's IP address</Text>
            <Text style={styles.hint}>Find it in the server app window on your PC</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. 192.168.1.42"
              placeholderTextColor={C.muted}
              value={ip}
              onChangeText={setIp}
              keyboardType="decimal-pad"
              autoCapitalize="none"
              returnKeyType="done"
              onSubmitEditing={connectWifi}
            />
            <TouchableOpacity
              style={[styles.connectBtn, wifiStatus === "connecting" && styles.connectBtnDisabled]}
              onPress={connectWifi}
              disabled={wifiStatus === "connecting"}>
              {wifiStatus === "connecting"
                ? <ActivityIndicator color="#fff" />
                : <Text style={styles.connectBtnText}>Connect</Text>}
            </TouchableOpacity>
            {wifiStatus === "error" && (
              <Text style={styles.errorText}>Could not connect — check IP and server</Text>
            )}
          </View>
        )}

        {/* BLE panel */}
        {mode === "ble" && (
          <View style={styles.panel}>
            <Text style={styles.panelTitle}>Scan for PC Controller</Text>
            <Text style={styles.hint}>
              Make sure the server is running on your PC{"\n"}and Bluetooth is on for both devices
            </Text>
            <View style={styles.bleStatusBox}>
              {(bleStatus === "scanning" || bleStatus === "connecting") && (
                <ActivityIndicator color={C.accent} style={{ marginRight: 10 }} />
              )}
              <Text style={[styles.bleStatusText, bleStatus === "connected" && { color: C.green },
                            bleStatus.includes("error") || bleStatus === "not_found" ? { color: C.red } : null]}>
                {BLE_STATUS_LABELS[bleStatus] ?? bleStatus}
              </Text>
            </View>
            <TouchableOpacity
              style={[styles.connectBtn, ["scanning","connecting"].includes(bleStatus) && styles.connectBtnDisabled]}
              onPress={connectBle}
              disabled={["scanning","connecting"].includes(bleStatus)}>
              <Text style={styles.connectBtnText}>
                {bleStatus === "scanning" ? "Scanning…" : "Scan & Connect"}
              </Text>
            </TouchableOpacity>
            <Text style={styles.bleNote}>
              ⚠️ Bluetooth has slightly more latency than WiFi — best for keyboard/media use
            </Text>
          </View>
        )}

        {!mode && (
          <Text style={styles.tipText}>
            💡 WiFi is recommended for the touchpad.{"\n"}Use Bluetooth when on a different network.
          </Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root:     { flex: 1, backgroundColor: C.bg },
  scroll:   { flexGrow: 1, alignItems: "center", padding: 24, paddingTop: 60 },
  title:    { fontSize: 32, fontWeight: "800", color: C.text, marginBottom: 6 },
  subtitle: { fontSize: 16, color: C.muted, marginBottom: 36 },
  modeRow:  { flexDirection: "row", gap: 16, marginBottom: 28 },
  modeBtn:  { flex: 1, backgroundColor: C.panel, borderRadius: 16, paddingVertical: 20,
              alignItems: "center", borderWidth: 2, borderColor: "transparent" },
  modeBtnActive:   { borderColor: C.accent },
  modeIcon:        { fontSize: 28, marginBottom: 6 },
  modeLabel:       { fontSize: 14, fontWeight: "600", color: C.muted },
  modeLabelActive: { color: C.accent },
  panel:    { width: "100%", backgroundColor: C.panel, borderRadius: 16, padding: 20, gap: 12 },
  panelTitle: { fontSize: 16, fontWeight: "700", color: C.text },
  hint:       { fontSize: 13, color: C.muted, lineHeight: 18 },
  input:      { backgroundColor: C.btn, borderRadius: 10, padding: 14,
                fontSize: 16, color: C.text, letterSpacing: 1 },
  connectBtn:         { backgroundColor: C.accent, borderRadius: 12, padding: 16, alignItems: "center" },
  connectBtnDisabled: { opacity: 0.5 },
  connectBtnText:     { color: "#fff", fontWeight: "700", fontSize: 16 },
  errorText:          { color: C.red, fontSize: 13, textAlign: "center" },
  bleStatusBox:       { flexDirection: "row", alignItems: "center", minHeight: 24 },
  bleStatusText:      { color: C.muted, fontSize: 14, flexShrink: 1 },
  bleNote:            { fontSize: 12, color: C.muted, lineHeight: 17 },
  tipText:            { marginTop: 32, color: C.muted, fontSize: 14, textAlign: "center", lineHeight: 22 },
});
