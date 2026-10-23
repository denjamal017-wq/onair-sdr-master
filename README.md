# 📡 OnAir SDR Master Web Control & Intelligence Suite

**Tactical Electronic Intelligence (ELINT) Dashboard & Autonomous Agent Controller for OnAir SDR + ADALM-Pluto**

---

## 🌟 Features

- **🎯 Single-Intent Autonomous Mind**: Send any directive in Arabic or English (`"مسح شامل للجو كامل"`, `"افحص البلوتوث"`, `"ابحث عن ريموتات 433"`).
- **📊 Real-Time Spectrum Sweeper & Waterfall**: Sweeps 70 MHz to 6 GHz with peak detection, occupancy measurement, and FFT canvas.
- **📱 Bluetooth Low Energy Tactical Matrix**: Intercepts BLE channels 37, 38, 39, fingerprints device vendors (Apple, Samsung, Espressif IoT), measures dBFS RSSI, and saves friendly tags.
- **📻 Protocol Decoders Lab**:
  - FM Broadcast Radio with RDS Subcarrier (PI, PS Station Name, RT RadioText).
  - Terrestrial Digital Television (DVB-T2 / ATSC) accelerated by **NVIDIA GeForce RTX 5060 Ti GPU LDPC**.
  - Satellite constellations (Iridium 1621MHz bursts & Orbcomm telemetry).
  - Raw SigMF CS8 IQ recording directly to HackVault.
- **🧠 Persistent Learned Memory**: Automatically catalogs all historical devices and carrier frequencies in `F:\HACKVAULT\08_RF_SIGNALS\ONAIR_LEARNED_MEMORY.json`.
- **🤖 Universal Cross-Agent Control**: Accessible via MCP (Model Context Protocol), local CLI, or HTTP REST API on port `8765`.

---

## 🚀 Quick Start (Running Locally)

### 1. Launch the Local SDR API Bridge
```powershell
python F:\HACKVAULT\04_TOOLS\onair_bridge.py --api 8765
```

### 2. Open the Web Dashboard
Simply open `index.html` in any web browser, or serve it with Python/Node:
```powershell
npx serve c:\bridge-work\onair-web-control
```

---

## ☁️ Deployment

### Deploy to Vercel
```bash
cd c:\bridge-work\onair-web-control
npx vercel deploy --prod
```

### Deploy to GitHub Pages
1. Push to your GitHub repository.
2. Under **Settings -> Pages**, select `main` branch `/ (root)`.
3. Your control dashboard will be live at `https://<username>.github.io/<repo>/`.

---

## 📡 Hardware & Environment

- **SDR Radio**: ADALM-Pluto (`usb:4.11.5`) with `plutoplus_with_timestamping` firmware.
- **GPU Accelerator**: NVIDIA GeForce RTX 5060 Ti (7891 MB VRAM) for LDPC matrix calculations.
- **Native Engine**: `onair-cli.exe` & `onair-scan.exe` located at `C:\Program Files\OnAir\`.
