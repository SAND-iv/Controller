# Controller
Control a pc from a mobile phone
Controller/
├── server.py              ← updated (WiFi + BLE)
├── controller.html        ← kept for fallback
└── ControllerApp/         ← new React Native project
    ├── App.js
    ├── screens/
    │   ├── ConnectScreen.js
    │   └── ControllerScreen.js
    └── utils/
        ├── wifiClient.js
        └── bleClient.js
