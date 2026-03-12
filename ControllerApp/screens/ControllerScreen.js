// screens/ControllerScreen.js
import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  View, Text, TouchableOpacity, PanResponder,
  StyleSheet, Vibration, TextInput, Platform,
  ScrollView, Switch,
} from "react-native";
import Slider from "@react-native-community/slider";
import { sendWifi, disconnectWifi } from "../utils/wifiClient";
import { sendBle, disconnectBle }   from "../utils/bleClient";

const C = {
  bg: "#0f1113", panel: "#1a1c1e", btn: "#2a2d30",
  accent: "#3b82f6", text: "#e2e8f0", muted: "#94a3b8",
  green: "#22c55e",
};

export default function ControllerScreen({ route, navigation }) {
  const { mode } = route.params;  // "wifi" | "ble"

  const [speed, setSpeed]         = useState(1.5);
  const [isDragging, setDragging] = useState(false);
  const [ctrlActive, setCtrl]     = useState(false);
  const [altActive,  setAlt]      = useState(false);
  const [showKeyboard, setShowKB] = useState(false);
  const hiddenRef = useRef(null);

  // ---- send helper ----
  const send = useCallback((data) => {
    if (mode === "wifi") sendWifi(data);
    else                 sendBle(data);
  }, [mode]);

  const vibrate = () => Vibration.vibrate(15);

  // ---- disconnect on back ----
  useEffect(() => {
    return () => {
      if (mode === "wifi") disconnectWifi();
      else                 disconnectBle();
    };
  }, []);

  // ---- speed ----
  const onSpeedChange = (v) => {
    setSpeed(v);
    send({ command: "set_speed", value: v });
  };

  // ---- media / keys ----
  const sendKey = (key) => { vibrate(); send({ command: "key", key }); };
  const clickBtn = (button) => { vibrate(); send({ command: "click", button }); };

  // ---- drag ----
  const toggleDrag = () => {
    const next = !isDragging;
    setDragging(next);
    vibrate();
    send({ command: next ? "drag_start" : "drag_end" });
  };

  // ---- modifier keys ----
  const toggleMod = (key, isActive, setter) => {
    const next = !isActive;
    setter(next);
    vibrate();
    send({ command: "key_toggle", key, state: next ? "down" : "up" });
  };

  // ---- touchpad pan responder ----
  const lastPos  = useRef({ x: 0, y: 0 });
  const tapTimer = useRef(null);
  const isScroll = useRef(false);
  const touchCount = useRef(0);

  const panResponder = useRef(PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder:  () => true,

    onPanResponderGrant: (evt) => {
      const touches = evt.nativeEvent.touches;
      touchCount.current = touches.length;
      isScroll.current   = touches.length >= 2;

      if (touches.length === 1) {
        lastPos.current = { x: touches[0].pageX, y: touches[0].pageY };
        tapTimer.current = setTimeout(() => { tapTimer.current = null; }, 150);
      } else if (touches.length >= 2) {
        lastPos.current = { x: touches[0].pageY, y: touches[0].pageY };
      }
    },

    onPanResponderMove: (evt) => {
      const touches = evt.nativeEvent.touches;

      if (isScroll.current && touches.length >= 2) {
        const cy = touches[0].pageY;
        const dy = cy - lastPos.current.y;
        if (Math.abs(dy) > 0.5) {
          send({ command: "scroll", dy });
          lastPos.current.y = cy;
        }
        return;
      }

      if (touches.length === 1) {
        if (tapTimer.current) clearTimeout(tapTimer.current);
        tapTimer.current = null;
        const cx = touches[0].pageX;
        const cy = touches[0].pageY;
        const dx = cx - lastPos.current.x;
        const dy = cy - lastPos.current.y;
        if (Math.abs(dx) > 0.3 || Math.abs(dy) > 0.3) {
          send({ command: "move", dx, dy });
          lastPos.current = { x: cx, y: cy };
        }
      }
    },

    onPanResponderRelease: () => {
      if (tapTimer.current && !isScroll.current) {
        clearTimeout(tapTimer.current);
        tapTimer.current = null;
        clickBtn("left");
      }
    },
  })).current;

  // ---- keyboard ----
  const SPACER = " ";
  const openKeyboard = () => {
    setShowKB(true);
    setTimeout(() => hiddenRef.current?.focus(), 100);
  };

  const onInputChange = (e) => {
    const { nativeEvent: { inputType, data } } = e;
    if (data) {
      send({ command: "type", text: data });
    } else if (inputType === "deleteContentBackward") {
      sendKey("BACKSPACE");
    }
    // reset spacer
    if (hiddenRef.current) hiddenRef.current.setNativeProps({ text: SPACER });
  };

  return (
    <View style={styles.root}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.replace("Connect")} style={styles.backBtn}>
          <Text style={styles.backText}>← Disconnect</Text>
        </TouchableOpacity>
        <View style={styles.statusPill}>
          <View style={[styles.dot, { backgroundColor: C.green }]} />
          <Text style={styles.statusText}>{mode === "wifi" ? "WiFi" : "Bluetooth"}</Text>
        </View>
      </View>

      {/* Speed slider */}
      <View style={styles.sliderBox}>
        <Text style={styles.sliderLabel}>SPEED</Text>
        <Slider
          style={{ flex: 1 }}
          minimumValue={0.5}
          maximumValue={5.0}
          step={0.1}
          value={speed}
          onValueChange={onSpeedChange}
          minimumTrackTintColor={C.accent}
          maximumTrackTintColor={C.btn}
          thumbTintColor={C.accent}
        />
        <Text style={styles.sliderVal}>{speed.toFixed(1)}×</Text>
      </View>

      {/* Media controls */}
      <View style={styles.row}>
        {["vol_down","mute","vol_up"].map((k, i) => (
          <TouchableOpacity key={k} style={styles.iconBtn} onPress={() => sendKey(k)}>
            <Text style={styles.iconBtnText}>{["Vol -","Mute","Vol +"][i]}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.row}>
        {["prev","play","next"].map((k, i) => (
          <TouchableOpacity key={k} style={styles.iconBtn} onPress={() => sendKey(k)}>
            <Text style={styles.iconBtnText}>{["⏮","⏯","⏭"][i]}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Touchpad */}
      <View style={styles.touchpad} {...panResponder.panHandlers}>
        <Text style={styles.padHint}>TRACKPAD</Text>
        <Text style={styles.padHint2}>tap · drag · 2-finger scroll</Text>
      </View>

      {/* Mouse buttons */}
      <View style={styles.mouseRow}>
        <TouchableOpacity style={styles.mouseBtn} onPress={() => clickBtn("left")}>
          <Text style={styles.mouseBtnText}>L</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.mouseBtn, isDragging && styles.mouseBtnActive]}
          onPress={toggleDrag}>
          <Text style={styles.mouseBtnText}>{isDragging ? "🔒 Hold" : "🔓 Drag"}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.mouseBtn} onPress={() => clickBtn("right")}>
          <Text style={styles.mouseBtnText}>R</Text>
        </TouchableOpacity>
      </View>

      {/* Modifier keys */}
      <View style={styles.mouseRow}>
        <TouchableOpacity
          style={[styles.mouseBtn, ctrlActive && styles.mouseBtnActive]}
          onPress={() => toggleMod("ctrl", ctrlActive, setCtrl)}>
          <Text style={styles.mouseBtnText}>Ctrl</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.mouseBtn, altActive && styles.mouseBtnActive]}
          onPress={() => toggleMod("alt", altActive, setAlt)}>
          <Text style={styles.mouseBtnText}>Alt</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.mouseBtn} onPress={() => sendKey("win")}>
          <Text style={styles.mouseBtnText}>⊞ Win</Text>
        </TouchableOpacity>
      </View>

      {/* Tools */}
      <View style={styles.toolGrid}>
        <TouchableOpacity style={[styles.toolBtn, { backgroundColor: C.accent }]} onPress={openKeyboard}>
          <Text style={[styles.toolBtnText, { color: "#fff" }]}>⌨ Type</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={() => sendKey("ENTER")}>
          <Text style={styles.toolBtnText}>Enter</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={() => sendKey("BACKSPACE")}>
          <Text style={styles.toolBtnText}>⌫</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={() => sendKey("ESC")}>
          <Text style={styles.toolBtnText}>Esc</Text>
        </TouchableOpacity>
      </View>

      {/* Hidden text input for keyboard */}
      <TextInput
        ref={hiddenRef}
        style={styles.hidden}
        defaultValue={SPACER}
        autoCorrect={false}
        autoCapitalize="none"
        onChangeText={() => {}}
        onChange={onInputChange}
        onSubmitEditing={() => sendKey("ENTER")}
        onBlur={() => setShowKB(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root:     { flex: 1, backgroundColor: C.bg, padding: 14, paddingTop: Platform.OS === "ios" ? 52 : 20 },
  header:   { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  backBtn:  { padding: 6 },
  backText: { color: C.muted, fontSize: 14 },
  statusPill:  { flexDirection: "row", alignItems: "center", gap: 6,
                 backgroundColor: C.panel, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  dot:         { width: 8, height: 8, borderRadius: 4 },
  statusText:  { color: C.text, fontSize: 12, fontWeight: "600" },

  sliderBox:   { flexDirection: "row", alignItems: "center", backgroundColor: C.panel,
                 borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8,
                 marginBottom: 12, borderWidth: 1, borderColor: "#333" },
  sliderLabel: { fontSize: 11, color: C.muted, fontWeight: "700", marginRight: 8, width: 42 },
  sliderVal:   { fontSize: 11, color: C.muted, width: 32, textAlign: "right" },

  row:     { flexDirection: "row", gap: 8, marginBottom: 8 },
  iconBtn: { flex: 1, backgroundColor: C.btn, borderRadius: 12, paddingVertical: 12, alignItems: "center" },
  iconBtnText: { color: C.text, fontWeight: "600", fontSize: 13 },

  touchpad: { flex: 1, backgroundColor: C.panel, borderRadius: 16, marginBottom: 10,
              borderWidth: 1, borderColor: "#333", alignItems: "center", justifyContent: "center" },
  padHint:  { color: "#ffffff20", fontSize: 22, fontWeight: "700" },
  padHint2: { color: "#ffffff15", fontSize: 11, marginTop: 4 },

  mouseRow:    { flexDirection: "row", gap: 10, height: 52, marginBottom: 8 },
  mouseBtn:    { flex: 1, backgroundColor: C.btn, borderRadius: 12,
                 alignItems: "center", justifyContent: "center" },
  mouseBtnActive: { backgroundColor: C.green },
  mouseBtnText:   { color: C.text, fontWeight: "700", fontSize: 14 },

  toolGrid:    { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 6 },
  toolBtn:     { flex: 1, minWidth: "45%", backgroundColor: "#222",
                 borderWidth: 1, borderColor: "#333", borderRadius: 10,
                 paddingVertical: 12, alignItems: "center" },
  toolBtnText: { color: C.muted, fontWeight: "600", fontSize: 13 },

  hidden: { position: "absolute", top: -200, left: 0, width: 1, height: 1, opacity: 0 },
});
