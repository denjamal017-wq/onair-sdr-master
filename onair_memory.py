#!/usr/bin/env python3
"""
=============================================================================
  OnAir SDR Learned Memory Engine & Signal Intelligence Store
  Persistent Memory, MAC Fingerprinting, Frequency Catalog & Triage History
=============================================================================
Stores and correlates all RF discoveries across missions in:
  F:\\HACKVAULT\\08_RF_SIGNALS\\ONAIR_LEARNED_MEMORY.json
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

PRIMARY_MEMORY_PATH = r"F:\HACKVAULT\08_RF_SIGNALS\ONAIR_LEARNED_MEMORY.json"
FALLBACK_MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ONAIR_LEARNED_MEMORY.json")

# Vendor / OUI Signature table for common IoT, mobile, and RF hardware
MAC_VENDORS = {
    "apple": ["F0:F6:1C", "DC:A9:04", "AC:BC:32", "A4:D1:D2", "9C:20:7B", "84:FC:AC", "7C:04:D0", "70:3E:AC", "68:DB:CA", "5C:96:9D", "44:4C:0C", "3C:07:54", "28:CF:DA", "18:AF:61", "00:F7:6F"],
    "samsung": ["CC:07:AB", "BC:D1:1F", "AC:5F:3E", "94:65:2D", "84:25:DB", "78:47:1D", "68:27:37", "50:01:D9", "40:4E:36", "34:82:C5", "24:4B:03", "14:BB:6E", "00:12:47"],
    "espressif_iot": ["24:0A:C4", "30:AE:A4", "24:6F:28", "84:F3:EB", "A4:CF:12", "C4:4F:33", "D8:A0:1D", "40:22:D8", "8C:AA:B5", "E8:68:E7", "7C:DF:A1", "34:B4:72"],
    "nordic_ble": ["F4:CE:36", "E0:E5:CF", "C0:98:E5", "00:1B:DC", "A4:C1:38", "54:6C:0E"],
    "xiaomi": ["78:11:DC", "64:CC:2E", "50:8F:4C", "38:64:07", "28:6C:07", "18:87:96", "04:CF:8C"],
    "huawei": ["00:E0:FC", "04:25:C5", "20:0B:C7", "34:CD:BE", "48:46:FB", "70:7B:E8", "88:CF:98"],
    "fitbit_garmin": ["D4:81:CA", "48:A1:95", "00:1A:7D", "00:1C:88"],
    "raspberry_pi": ["B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1"],
}

KNOWN_FREQ_DESCRIPTIONS = {
    315.0: "Car Keyfobs, TPMS Tire Pressure, Security Alarms (315 MHz)",
    433.92: "ISM Sub-GHz (Garage Remotes, Weather Sensors, Smart Plugs)",
    868.1: "LoRa EU Channel 0 (868.1 MHz BW125)",
    868.3: "LoRa EU Channel 1 (868.3 MHz BW125)",
    868.5: "LoRa EU Channel 2 (868.5 MHz BW125)",
    915.0: "LoRa US ISM 915 MHz Band",
    1090.0: "ADS-B Commercial Aviation Aircraft Transponders",
    1575.42: "GPS L1 Civilian Satellite Navigation",
    1621.25: "Iridium Satellite Network Uplink/Downlink",
    2402.0: "BLE Advertising Channel 37",
    2426.0: "BLE Advertising Channel 38",
    2480.0: "BLE Advertising Channel 39",
    2412.0: "WiFi 2.4 GHz Channel 1 / Drone Video Downlink",
    2437.0: "WiFi 2.4 GHz Channel 6 / Drone Video Downlink",
    2462.0: "WiFi 2.4 GHz Channel 11 / Drone Video Downlink",
}


class OnAirMemoryEngine:
    def __init__(self, memory_path: Optional[str] = None):
        if memory_path:
            self.memory_path = memory_path
        elif os.path.exists(os.path.dirname(PRIMARY_MEMORY_PATH)):
            self.memory_path = PRIMARY_MEMORY_PATH
        else:
            self.memory_path = FALLBACK_MEMORY_PATH

        self.data: Dict[str, Any] = {
            "version": "2.0.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "hardware_profile": {},
            "ble_devices": {},
            "spectrum_peaks": {},
            "broadcast_stations": {},
            "rf_captures": [],
            "annotations": {
                "friendly_names": {},
                "alert_macs": [],
                "monitored_frequencies": []
            },
            "mission_log": []
        }
        self.load()

    def load(self):
        """Loads memory from disk if file exists."""
        if os.path.isfile(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
            except Exception as e:
                print(f"[OnAirMemory] Warning: Failed to load memory file: {e}", file=sys.stderr)

    def save(self):
        """Persists current learned memory to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[OnAirMemory] Error saving memory: {e}", file=sys.stderr)

    def identify_mac_vendor(self, mac: str) -> str:
        """Fingerprints device manufacturer from MAC OUI or patterns."""
        mac_clean = mac.upper().replace("-", ":")
        prefix = ":".join(mac_clean.split(":")[:3]) if len(mac_clean.split(":")) >= 3 else ""

        for vendor, prefixes in MAC_VENDORS.items():
            for p in prefixes:
                if mac_clean.startswith(p):
                    return vendor.replace("_", " ").title()

        # Check address type heuristics
        if len(mac_clean) == 17:
            first_byte = int(mac_clean.split(":")[0], 16)
            is_random = (first_byte & 0x02) != 0
            if is_random:
                bits = (first_byte & 0xC0) >> 6
                if bits == 0b11:
                    return "BLE Random Static (IoT/Tracker)"
                elif bits == 0b01:
                    return "BLE Resolvable Private (Apple/Android/Wearable)"
                elif bits == 0b00:
                    return "BLE Non-Resolvable Private"

        return "Unknown / Generic Vendor"

    def record_ble_devices(self, devices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Records scanned BLE devices, correlates historical counts, and updates memory."""
        now = datetime.now().isoformat()
        new_count = 0
        updated_count = 0

        for d in devices:
            mac = d.get("mac", "").upper()
            if not mac:
                continue

            vendor = self.identify_mac_vendor(mac)
            friendly = self.data["annotations"]["friendly_names"].get(mac)

            if mac not in self.data["ble_devices"]:
                new_count += 1
                self.data["ble_devices"][mac] = {
                    "mac": mac,
                    "addr_type": d.get("type", "Unknown"),
                    "vendor_fingerprint": vendor,
                    "friendly_name": friendly,
                    "first_seen": now,
                    "last_seen": now,
                    "times_detected": 1,
                    "max_signal_dbfs": d.get("best_level_dbfs", -100.0),
                    "best_snr": d.get("best_snr", 0.0),
                    "channels_seen": d.get("channels_seen", []),
                    "total_packets": d.get("packets_seen", 0)
                }
            else:
                updated_count += 1
                rec = self.data["ble_devices"][mac]
                rec["last_seen"] = now
                rec["times_detected"] += 1
                rec["total_packets"] += d.get("packets_seen", 0)
                if d.get("best_level_dbfs", -100.0) > rec.get("max_signal_dbfs", -100.0):
                    rec["max_signal_dbfs"] = d.get("best_level_dbfs")
                if d.get("best_snr", 0.0) > rec.get("best_snr", 0.0):
                    rec["best_snr"] = d.get("best_snr")
                for ch in d.get("channels_seen", []):
                    if ch not in rec.get("channels_seen", []):
                        rec["channels_seen"].append(ch)

        self.save()
        return {
            "total_in_memory": len(self.data["ble_devices"]),
            "new_devices_logged": new_count,
            "existing_updated": updated_count
        }

    def record_spectrum_peaks(self, band_name: str, peaks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Records RF carrier frequency peaks into persistent memory."""
        now = datetime.now().isoformat()
        recorded = 0

        for p in peaks:
            freq = round(p.get("freq_mhz", 0.0), 3)
            key = f"{freq:.3f}"
            dbfs = p.get("level_dbfs", -100.0)

            label = KNOWN_FREQ_DESCRIPTIONS.get(round(freq, 2))
            if not label:
                label = f"Active carrier in {band_name}"

            if key not in self.data["spectrum_peaks"]:
                self.data["spectrum_peaks"][key] = {
                    "freq_mhz": freq,
                    "band": band_name,
                    "description": label,
                    "first_seen": now,
                    "last_seen": now,
                    "detections": 1,
                    "peak_power_dbfs": dbfs
                }
                recorded += 1
            else:
                rec = self.data["spectrum_peaks"][key]
                rec["last_seen"] = now
                rec["detections"] += 1
                if dbfs > rec.get("peak_power_dbfs", -100.0):
                    rec["peak_power_dbfs"] = dbfs

        self.save()
        return {"total_peaks_in_memory": len(self.data["spectrum_peaks"]), "new_peaks": recorded}

    def record_fm_station(self, freq_mhz: float, ps_name: str, pi_code: str, rt_text: str):
        """Records FM broadcast RDS telemetry."""
        key = f"{freq_mhz:.1f}"
        self.data["broadcast_stations"][key] = {
            "freq_mhz": freq_mhz,
            "station_ps": ps_name.strip() if ps_name else None,
            "pi_code": pi_code.strip() if pi_code else None,
            "radio_text": rt_text.strip() if rt_text else None,
            "last_heard": datetime.now().isoformat()
        }
        self.save()

    def record_rf_capture(self, filepath: str, freq_mhz: float, bw: str, gain: int, secs: int, size_bytes: int):
        """Catalogs an IQ recording file in HackVault."""
        self.data["rf_captures"].append({
            "path": filepath,
            "filename": os.path.basename(filepath),
            "freq_mhz": freq_mhz,
            "bandwidth": bw,
            "gain_db": gain,
            "duration_secs": secs,
            "size_bytes": size_bytes,
            "timestamp": datetime.now().isoformat()
        })
        self.save()

    def annotate(self, identifier: str, note_or_name: str, alert: bool = False):
        """Adds custom label or alert status to a MAC address or frequency."""
        mac_key = identifier.upper().strip()
        self.data["annotations"]["friendly_names"][mac_key] = note_or_name
        if mac_key in self.data["ble_devices"]:
            self.data["ble_devices"][mac_key]["friendly_name"] = note_or_name
        if alert and mac_key not in self.data["annotations"]["alert_macs"]:
            self.data["annotations"]["alert_macs"].append(mac_key)
        self.save()


    def get_summary_report(self) -> Dict[str, Any]:
        """Generates an executive intelligence dossier of all learned knowledge."""
        ble_devs = list(self.data["ble_devices"].values())
        ble_devs.sort(key=lambda x: x.get("max_signal_dbfs", -100.0), reverse=True)

        peaks = list(self.data["spectrum_peaks"].values())
        peaks.sort(key=lambda x: x.get("detections", 0), reverse=True)

        return {
            "total_unique_ble_devices": len(ble_devs),
            "total_active_frequencies_cataloged": len(peaks),
            "total_fm_stations_identified": len(self.data["broadcast_stations"]),
            "total_rf_raw_captures_in_vault": len(self.data["rf_captures"]),
            "top_strongest_ble_devices": ble_devs[:10],
            "most_persistent_frequencies": peaks[:10],
            "known_broadcast_stations": self.data["broadcast_stations"],
            "vault_memory_file": self.memory_path,
            "last_updated": self.data.get("last_updated")
        }


if __name__ == "__main__":
    mem = OnAirMemoryEngine()
    summary = mem.get_summary_report()
    print("=" * 60)
    print("  OnAir Learned Memory Store - Active")
    print("=" * 60)
    print(f"  Storage File:   {summary['vault_memory_file']}")
    print(f"  BLE Devices:    {summary['total_unique_ble_devices']}")
    print(f"  Active Freqs:   {summary['total_active_frequencies_cataloged']}")
    print(f"  FM Stations:    {summary['total_fm_stations_identified']}")
    print(f"  RF Captures:    {summary['total_rf_raw_captures_in_vault']}")
    print("=" * 60)
