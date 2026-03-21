import React, { useState, useRef } from "react";
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, StatusBar, ActivityIndicator,
  KeyboardAvoidingView, Platform,
} from "react-native";
import { WebView } from "react-native-webview";

export default function App() {
  const [ip, setIp] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const webviewRef = useRef(null);

  function connect() {
    if (!ip.trim()) return;
    setError(false);
    setLoading(true);
    setConnected(true);
  }

  function disconnect() {
    setConnected(false);
    setLoading(false);
    setError(false);
  }

  if (connected) {
    return (
      <View style={styles.root}>
        <StatusBar barStyle="light-content" backgroundColor="#0f1113" />

        {/* Top bar */}
        <View style={styles.bar}>
          <TouchableOpacity onPress={disconnect} style={styles.backBtn}>
            <Text style={styles.backText}>✕ Disconnect</Text>
          </TouchableOpacity>
          <View style={styles.pill}>
            <View style={[styles.dot, error ? styles.dotRed : loading ? styles.dotYellow : styles.dotGreen]} />
            <Text style={styles.pillText}>
              {error ? "Error" : loading ? "Connecting…" : "Connected"}
            </Text>
          </View>
        </View>

        {/* WebView */}
        <WebView
          ref={webviewRef}
          source={{ uri: `http://${ip.trim()}:8080/` }}
          style={styles.webview}
          onLoadStart={() => { setLoading(true); setError(false); }}
          onLoadEnd={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          mediaPlaybackRequiresUserAction={false}
          allowsInlineMediaPlayback={true}
          scrollEnabled={false}
          bounces={false}
          overScrollMode="never"
        />

        {error && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>
              ⚠️ Can't reach {ip}:8080 — is the server running?
            </Text>
            <TouchableOpacity onPress={() => { setError(false); setLoading(true); webviewRef.current?.reload(); }}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor="#0f1113" />

      <View style={styles.connectScreen}>
        <Text style={styles.title}>PC Controller</Text>
        <Text style={styles.subtitle}>Enter your PC's IP address to connect</Text>

        <View style={styles.card}>
          <Text style={styles.label}>PC IP Address</Text>
          <TextInput
            style={styles.input}
            placeholder="e.g. 192.168.1.42"
            placeholderTextColor="#64748b"
            value={ip}
            onChangeText={setIp}
            keyboardType="decimal-pad"
            autoCapitalize="none"
            returnKeyType="done"
            onSubmitEditing={connect}
          />
          <Text style={styles.hint}>
            Find the IP in the server window on your PC
          </Text>
        </View>

        <TouchableOpacity
          style={[styles.connectBtn, !ip.trim() && styles.connectBtnOff]}
          onPress={connect}
          disabled={!ip.trim()}>
          <Text style={styles.connectBtnText}>Connect →</Text>
        </TouchableOpacity>

        <Text style={styles.tip}>
          💡 Make sure your phone and PC are on the same WiFi network
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const C = {
  bg: "#0f1113", panel: "#1a1c1e", btn: "#2a2d30",
  accent: "#3b82f6", text: "#e2e8f0", muted: "#94a3b8",
  green: "#22c55e", red: "#ef4444", yellow: "#eab308",
};

const styles = StyleSheet.create({
  root:          { flex: 1, backgroundColor: C.bg },
  bar:           { flexDirection: "row", justifyContent: "space-between",
                   alignItems: "center", backgroundColor: C.bg,
                   paddingHorizontal: 16, paddingTop: Platform.OS === "ios" ? 52 : 36,
                   paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: "#222" },
  backBtn:       { padding: 6 },
  backText:      { color: C.muted, fontSize: 14 },
  pill:          { flexDirection: "row", alignItems: "center", gap: 6,
                   backgroundColor: C.panel, paddingHorizontal: 10,
                   paddingVertical: 4, borderRadius: 20 },
  dot:           { width: 8, height: 8, borderRadius: 4 },
  dotGreen:      { backgroundColor: C.green },
  dotRed:        { backgroundColor: C.red },
  dotYellow:     { backgroundColor: C.yellow },
  pillText:      { color: C.text, fontSize: 12, fontWeight: "600" },
  webview:       { flex: 1, backgroundColor: C.bg },
  errorBanner:   { backgroundColor: "#1a0a0a", borderTopWidth: 1, borderTopColor: C.red,
                   padding: 12, flexDirection: "row", justifyContent: "space-between",
                   alignItems: "center" },
  errorText:     { color: C.red, fontSize: 13, flex: 1 },
  retryText:     { color: C.accent, fontSize: 13, fontWeight: "700", marginLeft: 12 },

  connectScreen: { flex: 1, alignItems: "center", justifyContent: "center", padding: 28 },
  title:         { fontSize: 36, fontWeight: "800", color: C.text, marginBottom: 8 },
  subtitle:      { fontSize: 15, color: C.muted, textAlign: "center", marginBottom: 36, lineHeight: 22 },
  card:          { width: "100%", backgroundColor: C.panel, borderRadius: 16,
                   padding: 20, marginBottom: 20, borderWidth: 1, borderColor: "#2a2d30" },
  label:         { fontSize: 12, color: C.muted, fontWeight: "700",
                   textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 },
  input:         { backgroundColor: C.btn, borderRadius: 10, padding: 14,
                   fontSize: 18, color: C.text, letterSpacing: 1 },
  hint:          { fontSize: 12, color: C.muted, marginTop: 10 },
  connectBtn:    { width: "100%", backgroundColor: C.accent, borderRadius: 14,
                   padding: 18, alignItems: "center", marginBottom: 24 },
  connectBtnOff: { opacity: 0.4 },
  connectBtnText:{ color: "#fff", fontWeight: "800", fontSize: 17 },
  tip:           { color: C.muted, fontSize: 13, textAlign: "center", lineHeight: 20 },
});
