#!/usr/bin/env python3
"""
=============================================================================
  OnAir Master Control Bridge & SDR Autonomous Intelligence Suite
  Complete Automation, Protocol Decoders, RF Orchestration & Learned Memory
=============================================================================
Controls:
  - onair-cli.exe (Decoders: BLE, DVB-T/T2, ATSC, ISDB-T, FM/RDS, Iridium, Orbcomm, dPMR)
  - onair-scan.exe (Spectrum sweeping, signal discovery, occupancy analysis)
  - OnAir.exe GUI process lifecycle management
  - Network streaming: HTTP tuner (--serve), UDP/RTP transport stream, IP-PCAP dumping
  - PlutoSDR hardware parameters: Gain, Bandwidth, LNA, VGA, Amp, Compute (RTX GPU LDPC)
  - Raw SigMF CS8/CF32 recording & custom option injection (--sopt/--sval, DECT2_*)
  - Autonomous Single-Intent Mission Dispatcher (Natural language execution in EN & AR)
  - Persistent Learned Memory Engine (Fingerprinting, frequency catalog, historical tracking)
"""

import os
import sys
import re
import json
import time
import subprocess
from typing import Dict, List, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


try:
    from onair_memory import OnAirMemoryEngine
except ImportError:
    from .onair_memory import OnAirMemoryEngine

ONAIR_DIR = r"C:\Program Files\OnAir"
ONAIR_CLI = os.path.join(ONAIR_DIR, "onair-cli.exe")
ONAIR_SCAN = os.path.join(ONAIR_DIR, "onair-scan.exe")
ONAIR_GUI = os.path.join(ONAIR_DIR, "OnAir.exe")

BLE_CHANNELS = {
    37: {"freq": 2402, "name": "BLE-ADV-37"},
    38: {"freq": 2426, "name": "BLE-ADV-38"},
    39: {"freq": 2480, "name": "BLE-ADV-39"}
}

COMMON_RF_BANDS = {
    "subghz_ism":    {"from": 433.0, "to": 435.0, "step": 0.2, "desc": "ISM 433 MHz (Remotes, Keyfobs, IoT, Sensors)"},
    "subghz_315":    {"from": 314.0, "to": 316.0, "step": 0.2, "desc": "Car Keys, TPMS & Security 315 MHz"},
    "lora_868":      {"from": 867.0, "to": 870.0, "step": 0.2, "desc": "LoRa / Meshtastic EU 868 MHz"},
    "lora_915":      {"from": 902.0, "to": 928.0, "step": 0.5, "desc": "LoRa / Meshtastic US 915 MHz"},
    "tetra_390":     {"from": 390.0, "to": 395.0, "step": 0.2, "desc": "TETRA Emergency & Public Safety Radio"},
    "air_sonde":     {"from": 400.0, "to": 406.0, "step": 0.5, "desc": "Meteorological Radiosonde Band"},
    "ism_2400":      {"from": 2400.0, "to": 2484.0, "step": 2.0, "desc": "2.4 GHz ISM (WiFi / Bluetooth / Drones)"},
    "marine_ais":    {"from": 161.9, "to": 162.1, "step": 0.05, "desc": "Marine AIS Vessel Tracking (161.975/162.025 MHz)"},
    "aviation_vdl2": {"from": 136.9, "to": 137.1, "step": 0.05, "desc": "Aviation VDL Mode 2 Data Link (136.975 MHz)"},
    "broadcast_fm":  {"from": 88.0,  "to": 108.0, "step": 0.4, "desc": "FM Broadcast Radio Band (88-108 MHz)"},
    "broadcast_dab": {"from": 174.0, "to": 240.0, "step": 1.7, "desc": "DAB/DAB+ Digital Radio Band III"},
    "broadcast_dvbt":{"from": 470.0, "to": 694.0, "step": 8.0, "desc": "UHF Digital Terrestrial Television (DVB-T/T2)"}
}


class OnAirBridge:
    def __init__(self, onair_dir: str = ONAIR_DIR, memory_path: Optional[str] = None):
        self.onair_dir = onair_dir
        self.cli_exe = ONAIR_CLI
        self.scan_exe = ONAIR_SCAN
        self.gui_exe = ONAIR_GUI
        self._verify_installation()
        self.memory = OnAirMemoryEngine(memory_path)

    def _verify_installation(self):
        if not os.path.isfile(self.cli_exe):
            raise FileNotFoundError(f"onair-cli.exe not found at: {self.cli_exe}")
        if not os.path.isfile(self.scan_exe):
            raise FileNotFoundError(f"onair-scan.exe not found at: {self.scan_exe}")

    def is_gui_running(self) -> bool:
        """Checks if OnAir.exe GUI process is currently running."""
        try:
            out = subprocess.check_output('tasklist /FI "IMAGENAME eq OnAir.exe" /NH', shell=True, text=True)
            return "OnAir.exe" in out
        except Exception:
            return False

    def ensure_radio_available(self, auto_close_gui: bool = True) -> bool:
        """If OnAir.exe GUI is running, it holds exclusive Pluto USB lock. Closes it if auto_close_gui is True."""
        if self.is_gui_running():
            if auto_close_gui:
                subprocess.run("taskkill /F /IM OnAir.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1.0)
                return True
            return False
        return True

    def get_hardware_status(self) -> Dict[str, Any]:
        """Probes PlutoSDR, GPU LDPC acceleration, and GUI conflict status."""
        gui_active = self.is_gui_running()
        cmd = [self.cli_exe, "--freq", "2402", "--secs", "1"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        output = res.stdout

        info = {
            "pluto_connected": "PlutoSDR" in output,
            "gui_running": gui_active,
            "gui_note": "OnAir.exe GUI holds exclusive Pluto USB lock when open; CLI manages it automatically." if gui_active else "PlutoSDR is available for CLI & MCP control.",
            "gpu_accelerator": None,
            "pluto_firmware": None,
            "pluto_endpoint": None,
            "sample_rate_cap": "4.0 Msps (USB lossless) / 61.44 Msps (Radio)",
            "supported_modes": [
                "ble", "t2 (DVB-T2)", "t (DVB-T)", "atsc", "atsc3", "isdbt", "dab", "fm (with RDS)",
                "iridium (satellite)", "orbcomm (telemetry)", "dpmr (digital voice)", "dvbc", "spectrum-scan"
            ]
        }
        
        gpu_m = re.search(r'GpuLdpc:\s*using\s*"([^"]+)"', output)
        if gpu_m:
            info["gpu_accelerator"] = gpu_m.group(1)
            
        fw_m = re.search(r'PlutoSDR firmware:\s*([^\r\n]+)', output)
        if fw_m:
            info["pluto_firmware"] = fw_m.group(1).strip()
            
        dev_m = re.search(r'device:\s*PlutoSDR\s*\(([^)]+)\)', output)
        if dev_m:
            info["pluto_endpoint"] = dev_m.group(1).strip()

        # Update memory telemetry
        self.memory.data["hardware_profile"] = {
            "pluto_connected": info["pluto_connected"],
            "endpoint": info["pluto_endpoint"],
            "firmware": info["pluto_firmware"],
            "gpu": info["gpu_accelerator"]
        }
        self.memory.save()

        return info

    def manage_gui(self, action: str) -> Dict[str, Any]:
        """Manages OnAir GUI: 'status', 'start', or 'stop'."""
        if action == "status":
            running = self.is_gui_running()
            return {"status": "success", "gui_running": running}
        elif action == "stop":
            subprocess.run("taskkill /F /IM OnAir.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return {"status": "success", "gui_running": self.is_gui_running()}
        elif action == "start":
            if not self.is_gui_running():
                subprocess.Popen([self.gui_exe], cwd=self.onair_dir)
                time.sleep(1.0)
            return {"status": "success", "gui_running": True}
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    def scan_ble(self, channels: Optional[List[int]] = None, secs_per_channel: int = 8, gain: int = 44, amp: bool = True) -> Dict[str, Any]:
        """Scans BLE channels (37, 38, 39) using Pluto native engine and updates learned memory."""
        self.ensure_radio_available()
        if channels is None:
            channels = [37, 38, 39]

        devices: Dict[str, Dict[str, Any]] = {}
        channel_stats: Dict[int, Dict[str, Any]] = {}
        total_packets = 0

        for ch in channels:
            if ch not in BLE_CHANNELS:
                continue
            freq = BLE_CHANNELS[ch]["freq"]
            cmd = [
                self.cli_exe,
                "--freq", str(freq),
                "--standard", "ble",
                "--ble-channel", str(ch),
                "--bw", "2M",
                "--gain", str(gain),
                "--secs", str(secs_per_channel)
            ]
            if amp:
                cmd.append("--amp")

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
            out = res.stdout

            ch_packets = 0
            ch_snr = 0.0
            last_level = -99.0

            for line in out.splitlines():
                line = line.strip()
                dev_m = re.search(r'BLE:\s*new device\s+([0-9A-Fa-f:]{17})\s*\(([^)]+)\)', line)
                if dev_m:
                    mac = dev_m.group(1).upper()
                    addr_type = dev_m.group(2)
                    if mac not in devices:
                        devices[mac] = {
                            "mac": mac,
                            "type": addr_type,
                            "channels_seen": [ch],
                            "packets_seen": 0,
                            "best_level_dbfs": -99.0,
                            "best_snr": 0.0
                        }
                    else:
                        if ch not in devices[mac]["channels_seen"]:
                            devices[mac]["channels_seen"].append(ch)

                lvl_m = re.search(r'level\s+([-\d\.]+)\s*dBFS\s*\|\s*\d+\s*devices,\s*(\d+)\s*packets', line)
                if lvl_m:
                    last_level = float(lvl_m.group(1))
                    ch_packets = max(ch_packets, int(lvl_m.group(2)))

                snr_m = re.search(r'SNR\s+([-\d\.]+)\s*dB', line)
                if snr_m:
                    ch_snr = float(snr_m.group(1))

            for dev in devices.values():
                if ch in dev["channels_seen"]:
                    dev["packets_seen"] += ch_packets
                    dev["best_level_dbfs"] = max(dev["best_level_dbfs"], last_level)
                    dev["best_snr"] = max(dev["best_snr"], ch_snr)

            total_packets += ch_packets
            channel_stats[ch] = {
                "channel": ch,
                "frequency_mhz": freq,
                "packets_received": ch_packets,
                "last_level_dbfs": last_level,
                "snr_db": ch_snr
            }

        dev_list = list(devices.values())
        
        # Enrich and sync with Learned Memory
        memory_stats = self.memory.record_ble_devices(dev_list)
        for dev in dev_list:
            mac = dev["mac"]
            if mac in self.memory.data["ble_devices"]:
                mem_rec = self.memory.data["ble_devices"][mac]
                dev["vendor_fingerprint"] = mem_rec["vendor_fingerprint"]
                dev["friendly_name"] = mem_rec["friendly_name"]
                dev["historical_sightings"] = mem_rec["times_detected"]

        return {
            "status": "success",
            "total_devices_discovered": len(dev_list),
            "total_packets": total_packets,
            "devices": dev_list,
            "channel_stats": channel_stats,
            "memory_update": memory_stats
        }

    def scan_spectrum(self, from_mhz: float, to_mhz: float, step_mhz: float = 1.0, quick: bool = True, amp: bool = True) -> Dict[str, Any]:
        """Sweeps RF spectrum with onair-scan.exe and records active peaks."""
        self.ensure_radio_available()
        cmd = [self.scan_exe, "--from", str(from_mhz), "--to", str(to_mhz), "--step", str(step_mhz)]
        if quick:
            cmd.append("--quick")
        if amp:
            cmd.append("--amp")
        else:
            cmd.append("--noamp")

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        channels = []
        active_signals = []

        for line in res.stdout.splitlines():
            line = line.strip()
            m = re.search(r'([\d\.]+)\s*MHz\s*level\s*([-\d\.]+)\s*dBFS\s*occ\s*([-+\d\.]+)\s*dB\s*(\w+)?', line)
            if m:
                freq = float(m.group(1))
                level = float(m.group(2))
                occ = float(m.group(3))
                status = m.group(4) or "unknown"
                ch_entry = {"freq_mhz": freq, "level_dbfs": level, "occ_db": occ, "status": status}
                channels.append(ch_entry)
                if status != "empty" or occ > 3.0 or level > -70.0:
                    active_signals.append(ch_entry)

        # Record peaks to memory
        band_name = f"{from_mhz:.1f}-{to_mhz:.1f}MHz"
        mem_update = self.memory.record_spectrum_peaks(band_name, active_signals)

        return {
            "status": "success",
            "band_from_mhz": from_mhz,
            "band_to_mhz": to_mhz,
            "total_bins": len(channels),
            "active_signals_count": len(active_signals),
            "active_signals": active_signals,
            "bins": channels,
            "memory_update": mem_update
        }

    def scan_preset_band(self, preset_name: str, quick: bool = True, amp: bool = True) -> Dict[str, Any]:
        """Sweeps a named common RF band."""
        if preset_name not in COMMON_RF_BANDS:
            return {
                "status": "error",
                "message": f"Band '{preset_name}' unknown. Options: {list(COMMON_RF_BANDS.keys())}"
            }
        cfg = COMMON_RF_BANDS[preset_name]
        res = self.scan_spectrum(cfg["from"], cfg["to"], cfg["step"], quick=quick, amp=amp)
        res["preset_name"] = preset_name
        res["preset_desc"] = cfg["desc"]
        return res

    def decode_fm_rds(self, freq_mhz: float = 100.0, secs: int = 5, gain: int = 40) -> Dict[str, Any]:
        """Demodulates Broadcast FM and decodes RDS subcarrier."""
        self.ensure_radio_available()
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--standard", "fm", "--gain", str(gain), "--secs", str(secs)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        output = res.stdout

        rds_info = {
            "pi_code": None,
            "program_service_ps": None,
            "radio_text_rt": None,
            "frequency_deviation_khz": None
        }

        pi_m = re.search(r'RDS:\s*PI\s*=\s*(0x[0-9A-Fa-f]+)', output)
        if pi_m:
            rds_info["pi_code"] = pi_m.group(1)
        ps_m = re.search(r'RDS:\s*PS\s*=\s*"([^"]+)"', output)
        if ps_m:
            rds_info["program_service_ps"] = ps_m.group(1)
        rt_m = re.search(r'RDS:\s*RT\s*=\s*"([^"]+)"', output)
        if rt_m:
            rds_info["radio_text_rt"] = rt_m.group(1)
        dev_m = re.search(r'deviation\s*([\d\.]+)\s*kHz', output)
        if dev_m:
            rds_info["frequency_deviation_khz"] = float(dev_m.group(1))

        # Record to memory
        if rds_info["program_service_ps"] or rds_info["pi_code"]:
            self.memory.record_fm_station(freq_mhz, rds_info["program_service_ps"], rds_info["pi_code"], rds_info["radio_text_rt"])

        return {
            "status": "success",
            "frequency_mhz": freq_mhz,
            "rds": rds_info,
            "raw_log_tail": output[-800:]
        }

    def decode_digital_tv(self, freq_mhz: float, standard: str = "t2", secs: int = 6, plp: Optional[int] = None) -> Dict[str, Any]:
        """Demodulates DVB-T2 / DVB-T / ATSC / ISDB-T with GPU LDPC acceleration."""
        self.ensure_radio_available()
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--standard", standard, "--secs", str(secs)]
        if plp is not None:
            cmd.extend(["--plp", str(plp)])

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        output = res.stdout

        metrics = {
            "snr_db": None,
            "mer_db": None,
            "pre_ber": None,
            "lock": "locked" in output.lower(),
            "services": []
        }

        snr_m = re.search(r'SNR\s*([\d\.]+)\s*dB', output)
        if snr_m:
            metrics["snr_db"] = float(snr_m.group(1))
        mer_m = re.search(r'MER\s*([\d\.]+)\s*dB', output)
        if mer_m:
            metrics["mer_db"] = float(mer_m.group(1))
        ber_m = re.search(r'pre-BER\s*([0-9e\.\-]+)', output)
        if ber_m:
            metrics["pre_ber"] = ber_m.group(1)

        for s_m in re.finditer(r'service\s*(\d+):\s*"([^"]+)"', output):
            metrics["services"].append({"id": int(s_m.group(1)), "name": s_m.group(2)})

        return {
            "status": "success",
            "frequency_mhz": freq_mhz,
            "standard": standard,
            "metrics": metrics,
            "raw_log_tail": output[-1000:]
        }

    def decode_satellite(self, sat_type: str = "iridium", secs: int = 10) -> Dict[str, Any]:
        """Demodulates satellite bursts (Iridium at 1621.25 MHz or Orbcomm downlinks)."""
        self.ensure_radio_available()
        if sat_type.lower() == "iridium":
            cmd = [self.cli_exe, "--freq", "1621.25", "--iridium-bits", "--secs", str(secs), "--gain", "50", "--amp"]
        elif sat_type.lower() == "orbcomm":
            cmd = [self.cli_exe, "--freq", "137.5", "--orbcomm-downlinks", "--secs", str(secs), "--gain", "45", "--amp"]
        else:
            return {"status": "error", "message": f"Unsupported satellite type: {sat_type}"}

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        return {"status": "success", "satellite": sat_type, "log": res.stdout[-1500:]}

    def scan_dpmr(self, freq_mhz: float = 446.0, secs: int = 10) -> Dict[str, Any]:
        """Scans Digital Private Mobile Radio (dPMR446)."""
        self.ensure_radio_available()
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--standard", "dpmr", "--secs", str(secs), "--gain", "45", "--amp"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        return {"status": "success", "log": res.stdout[-1500:]}

    def start_network_stream(self, freq_mhz: float, standard: str = "t2", protocol: str = "udp", dest_ip: str = "127.0.0.1", dest_port: int = 1234, secs: int = 30) -> Dict[str, Any]:
        """Broadcasts live Transport Stream over UDP or RTP network socket."""
        self.ensure_radio_available()
        dest = f"{dest_ip}:{dest_port}"
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--standard", standard, "--secs", str(secs), "--no-null"]
        if protocol == "udp":
            cmd.extend(["--udp", dest])
        elif protocol == "rtp":
            cmd.extend(["--rtp", dest])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=self.onair_dir)
        return {
            "status": "streaming_started",
            "protocol": protocol,
            "destination": dest,
            "pid": proc.pid,
            "command": " ".join(cmd)
        }

    def dump_network_pcap(self, freq_mhz: float, standard: str = "t2", pcap_file: str = "traffic.pcap", secs: int = 15) -> Dict[str, Any]:
        """Slices broadcast IP network data (MPE / GSE) into PCAP format for Wireshark inspection."""
        self.ensure_radio_available()
        out_path = os.path.abspath(pcap_file)
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--standard", standard, "--ip-pcap", out_path, "--secs", str(secs)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        return {
            "status": "success" if os.path.exists(out_path) else "failed",
            "pcap_file": out_path,
            "size_bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0,
            "log": res.stdout[-1000:]
        }

    def record_iq(self, freq_mhz: float, bw: str = "2M", gain: int = 50, secs: int = 5, output_file: str = "capture.cs8", amp: bool = True) -> Dict[str, Any]:
        """Records raw SigMF CS8 samples for deep offline analysis."""
        self.ensure_radio_available()
        out_path = os.path.abspath(output_file)
        cmd = [self.cli_exe, "--freq", str(freq_mhz), "--bw", bw, "--gain", str(gain), "--secs", str(secs), "--record", out_path, "--format", "cs8"]
        if amp:
            cmd.append("--amp")

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir)
        file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0

        if file_size > 0:
            self.memory.record_rf_capture(out_path, freq_mhz, bw, gain, secs, file_size)

        return {
            "status": "success" if file_size > 0 else "failed",
            "file": out_path,
            "size_bytes": file_size,
            "meta_file": out_path + ".sigmf-meta" if os.path.exists(out_path + ".sigmf-meta") else None,
            "log": res.stdout[-1000:]
        }

    def execute_custom_pipeline(self, args_list: List[str], env_vars: Optional[Dict[str, str]] = None, timeout: int = 30) -> Dict[str, Any]:
        """Atomic Extensibility: Executes onair-cli.exe with any arbitrary options and env variables."""
        self.ensure_radio_available()
        cmd = [self.cli_exe] + args_list
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", cwd=self.onair_dir, env=env, timeout=timeout)
            return {"status": "success", "exit_code": res.returncode, "output": res.stdout}
        except subprocess.TimeoutExpired as e:
            return {"status": "timeout", "output": e.stdout if hasattr(e, "stdout") else str(e)}

    # =========================================================================
    #   Autonomous Single-Intent Mission Dispatcher & Full Airspace Recon
    # =========================================================================

    def full_airspace_recon(self, quick: bool = True, gain: int = 44) -> Dict[str, Any]:
        """
        Multi-Band Tactical Electronic Intelligence (ELINT) Sweep:
        Sequentially surveys BLE, Sub-GHz Remotes (433MHz), Vehicle TPMS (315MHz),
        LoRa/Meshtastic (868MHz), and FM Broadcast Radio. Synthesizes a unified dossier.
        """
        self.ensure_radio_available()
        start_time = time.time()
        recon_results = {}

        # 1. Bluetooth Low Energy
        ble_res = self.scan_ble(channels=[37, 38, 39], secs_per_channel=4, gain=gain, amp=True)
        recon_results["bluetooth"] = {
            "devices_found": ble_res.get("total_devices_discovered", 0),
            "devices": ble_res.get("devices", [])
        }

        # 2. Sub-GHz 433 MHz (Remotes & IoT)
        sub_res = self.scan_preset_band("subghz_ism", quick=quick, amp=True)
        recon_results["subghz_433"] = {
            "active_carriers": sub_res.get("active_signals_count", 0),
            "signals": sub_res.get("active_signals", [])
        }

        # 3. Security 315 MHz (Car Keys & TPMS)
        car_res = self.scan_preset_band("subghz_315", quick=quick, amp=True)
        recon_results["cars_315"] = {
            "active_carriers": car_res.get("active_signals_count", 0),
            "signals": car_res.get("active_signals", [])
        }

        # 4. LoRa 868 MHz (Meshtastic / Long Range IoT)
        lora_res = self.scan_preset_band("lora_868", quick=quick, amp=True)
        recon_results["lora_868"] = {
            "active_carriers": lora_res.get("active_signals_count", 0),
            "signals": lora_res.get("active_signals", [])
        }

        # 5. Broadcast FM Survey
        fm_res = self.scan_preset_band("broadcast_fm", quick=quick, amp=False)
        recon_results["fm_broadcast"] = {
            "active_stations": fm_res.get("active_signals_count", 0),
            "signals": fm_res.get("active_signals", [])
        }

        elapsed = round(time.time() - start_time, 2)
        memory_summary = self.memory.get_summary_report()

        dossier = {
            "mission": "full_airspace_recon",
            "elapsed_seconds": elapsed,
            "tactical_findings": {
                "ble_devices_in_air": recon_results["bluetooth"]["devices_found"],
                "active_remotes_433mhz": recon_results["subghz_433"]["active_carriers"],
                "active_car_keys_315mhz": recon_results["cars_315"]["active_carriers"],
                "active_lora_transmitters": recon_results["lora_868"]["active_carriers"],
                "active_fm_radio_carriers": recon_results["fm_broadcast"]["active_stations"]
            },
            "ble_devices": recon_results["bluetooth"]["devices"],
            "spectrum_spikes_433": recon_results["subghz_433"]["signals"],
            "spectrum_spikes_315": recon_results["cars_315"]["signals"],
            "spectrum_spikes_lora": recon_results["lora_868"]["signals"],
            "persistent_memory_status": memory_summary
        }

        return dossier

    def autonomous_mission(self, intent: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        The Unified 'Soul, Mind & Body' Autonomous Dispatcher:
        Accepts any high-level natural language instruction or structured command
        in English or Arabic, determines the optimal RF strategy, executes the PHY pipeline,
        updates persistent memory, and returns an actionable intelligence dossier.
        """
        cmd_text = intent.lower().strip()
        params = params or {}
        self.ensure_radio_available()

        # Mission 1: Full Airspace Recon
        if any(k in cmd_text for k in ["مسح شامل", "شامل", "recon", "full scan", "audit", "survey all", "كلشي", "الجو كامل", "airspace"]):
            dossier = self.full_airspace_recon(quick=params.get("quick", True), gain=params.get("gain", 44))
            return {
                "status": "success",
                "mission_mode": "full_airspace_recon",
                "summary": f"Completed full tactical electronic survey in {dossier['elapsed_seconds']}s.",
                "dossier": dossier,
                "markdown": format_recon_dossier(dossier)
            }

        # Mission 2: Bluetooth Reconnaissance
        if any(k in cmd_text for k in ["ble", "bluetooth", "بلوتوث", "beacon", "airtag", "سوار", "هاتف", "ماك", "ماكات"]):
            secs = params.get("secs", 6)
            gain = params.get("gain", 44)
            res = self.scan_ble(channels=[37, 38, 39], secs_per_channel=secs, gain=gain)
            tbl = format_table(res.get("devices", []))
            return {
                "status": "success",
                "mission_mode": "bluetooth_recon",
                "summary": f"Discovered {res['total_devices_discovered']} BLE devices across advertising channels.",
                "devices": res.get("devices", []),
                "memory_update": res.get("memory_update"),
                "markdown": f"### 📡 Bluetooth Tactical Discovery\n\n```\n{tbl}\n```\n\n*Total packets analyzed: {res['total_packets']}*"
            }

        # Mission 3: Sub-GHz 433 MHz (Remotes, Keyfobs, IoT)
        if any(k in cmd_text for k in ["433", "ريموت", "كراج", "حساس", "مستشعر", "remote", "garage"]):
            res = self.scan_preset_band("subghz_ism", quick=params.get("quick", True), amp=True)
            return {
                "status": "success",
                "mission_mode": "subghz_433_sweep",
                "summary": f"Found {res['active_signals_count']} active carriers in 433 MHz ISM band.",
                "signals": res.get("active_signals", []),
                "markdown": format_spectrum_table("433 MHz ISM Remotes & IoT", res.get("active_signals", []))
            }

        # Mission 4: Security 315 MHz (Car keys, TPMS)
        if any(k in cmd_text for k in ["315", "سيارة", "سيارات", "مفتاح", "tpms", "keyfob"]):
            res = self.scan_preset_band("subghz_315", quick=params.get("quick", True), amp=True)
            return {
                "status": "success",
                "mission_mode": "subghz_315_cars",
                "summary": f"Found {res['active_signals_count']} active carriers in 315 MHz Vehicle band.",
                "signals": res.get("active_signals", []),
                "markdown": format_spectrum_table("315 MHz Car Keys & TPMS", res.get("active_signals", []))
            }

        # Mission 5: LoRa / Meshtastic (868 / 915 MHz)
        if any(k in cmd_text for k in ["868", "915", "lora", "لورا", "meshtastic"]):
            band = "lora_868" if "868" in cmd_text or "915" not in cmd_text else "lora_915"
            res = self.scan_preset_band(band, quick=params.get("quick", True), amp=True)
            return {
                "status": "success",
                "mission_mode": "lora_survey",
                "summary": f"Found {res['active_signals_count']} active LoRa carriers in {band}.",
                "signals": res.get("active_signals", []),
                "markdown": format_spectrum_table(f"LoRa {band}", res.get("active_signals", []))
            }

        # Mission 6: 2.4 GHz WiFi & Drones
        if any(k in cmd_text for k in ["2.4", "wifi", "drone", "وايفاي", "درون", "طيارة", "تحكم"]):
            res = self.scan_preset_band("ism_2400", quick=params.get("quick", True), amp=True)
            return {
                "status": "success",
                "mission_mode": "ism_2400_wifi_drones",
                "summary": f"Found {res['active_signals_count']} active channels in 2.4 GHz ISM.",
                "signals": res.get("active_signals", []),
                "markdown": format_spectrum_table("2.4 GHz WiFi / Drones", res.get("active_signals", []))
            }

        # Mission 7: Broadcast FM & RDS
        if any(k in cmd_text for k in ["fm", "rds", "راديو", "اذاعة", "محطة", "صوت"]):
            freq = params.get("freq_mhz", 100.0)
            res = self.decode_fm_rds(freq_mhz=freq, secs=params.get("secs", 5))
            rds = res["rds"]
            md = f"### 📻 FM Radio & RDS Decoder ({freq} MHz)\n\n"
            md += f"- **Station Name (PS)**: `{rds.get('program_service_ps') or 'N/A'}`\n"
            md += f"- **PI Code**: `{rds.get('pi_code') or 'N/A'}`\n"
            md += f"- **RadioText (RT)**: `{rds.get('radio_text_rt') or 'N/A'}`\n"
            md += f"- **Deviation**: `{rds.get('frequency_deviation_khz') or 'N/A'} kHz`\n"
            return {
                "status": "success",
                "mission_mode": "fm_rds_decode",
                "frequency_mhz": freq,
                "rds": rds,
                "markdown": md
            }

        # Mission 8: Digital TV Demodulation
        if any(k in cmd_text for k in ["tv", "dvb", "t2", "atsc", "تلفزيون", "بث رقمي"]):
            freq = params.get("freq_mhz", 490.0)
            std = params.get("standard", "t2")
            res = self.decode_digital_tv(freq_mhz=freq, standard=std, secs=params.get("secs", 6))
            return {"status": "success", "mission_mode": "digital_tv", "details": res, "markdown": f"### 📺 Digital TV Decode ({std.upper()} @ {freq} MHz)\n- Lock: {res['metrics']['lock']}\n- SNR: {res['metrics']['snr_db']} dB\n- MER: {res['metrics']['mer_db']} dB"}

        # Mission 9: Satellite Monitoring
        if any(k in cmd_text for k in ["satellite", "iridium", "orbcomm", "ستالايت", "قمر صناعي", "فضاء"]):
            sat = "iridium" if "iridium" in cmd_text or "orbcomm" not in cmd_text else "orbcomm"
            res = self.decode_satellite(sat_type=sat, secs=params.get("secs", 10))
            return {"status": "success", "mission_mode": "satellite_decode", "satellite": sat, "log": res.get("log")}

        # Mission 10: Raw Capture
        if any(k in cmd_text for k in ["record", "capture", "iq", "تسجيل", "خام", "cs8"]):
            freq = params.get("freq_mhz", 433.92)
            secs = params.get("secs", 5)
            out_file = params.get("output_file", os.path.join(r"F:\HACKVAULT\08_RF_SIGNALS", f"capture_{int(freq)}mhz.cs8"))
            res = self.record_iq(freq_mhz=freq, secs=secs, output_file=out_file)
            return {"status": res["status"], "mission_mode": "raw_iq_capture", "file": res.get("file"), "size": res.get("size_bytes")}

        # Mission 11: Hardware Status
        if any(k in cmd_text for k in ["status", "health", "check", "pluto", "فحص", "هاردوير", "عتاد", "كارت", "حرارة"]):
            st = self.get_hardware_status()
            md = f"### ⚡ PlutoSDR Hardware & Acceleration Status\n\n"
            md += f"- **PlutoSDR Connected**: `{'YES' if st['pluto_connected'] else 'NO'}` ({st.get('pluto_endpoint', 'N/A')})\n"
            md += f"- **Firmware**: `{st.get('pluto_firmware', 'N/A')}`\n"
            md += f"- **GPU LDPC Accelerator**: `{st.get('gpu_accelerator', 'N/A')}`\n"
            md += f"- **GUI Conflict**: `{'Running (CLI manages lock)' if st['gui_running'] else 'Clean (Pluto exclusive to CLI/MCP)'}`\n"
            return {"status": "success", "mission_mode": "hardware_status", "hardware": st, "markdown": md}

        # Mission 12: Recall Learned Memory
        if any(k in cmd_text for k in ["memory", "ذاكرة", "سجل", "ماكات سابقة", "تاريخ", "ماذا تعرف"]):
            mem_summary = self.memory.get_summary_report()
            md = f"### 🧠 OnAir Learned Memory & Signal Intelligence Dossier\n\n"
            md += f"- **Total Unique BLE Devices Logged**: `{mem_summary['total_unique_ble_devices']}`\n"
            md += f"- **Active Carrier Frequencies Cataloged**: `{mem_summary['total_active_frequencies_cataloged']}`\n"
            md += f"- **Broadcast FM Stations Identified**: `{mem_summary['total_fm_stations_identified']}`\n"
            md += f"- **Vault Raw RF Captures**: `{mem_summary['total_rf_raw_captures_in_vault']}`\n"
            md += f"- **Memory File**: `{mem_summary['vault_memory_file']}`\n\n"
            if mem_summary["top_strongest_ble_devices"]:
                md += "#### Top Discovered Devices in Airspace:\n"
                md += format_table(mem_summary["top_strongest_ble_devices"])
            return {"status": "success", "mission_mode": "memory_recall", "memory": mem_summary, "markdown": md}

        # Fallback: General Spectrum Sweep
        from_m = params.get("from_mhz", 400.0)
        to_m = params.get("to_mhz", 500.0)
        res = self.scan_spectrum(from_m, to_m, step_mhz=params.get("step_mhz", 1.0))
        return {
            "status": "success",
            "mission_mode": "custom_spectrum_sweep",
            "summary": f"Swept {from_m}-{to_m} MHz, discovered {res['active_signals_count']} active carriers.",
            "signals": res.get("active_signals", []),
            "markdown": format_spectrum_table(f"Custom Sweep {from_m}-{to_m} MHz", res.get("active_signals", []))
        }


def format_table(devices: List[Dict[str, Any]]) -> str:
    if not devices:
        return "No devices discovered."
    hdr = f"{'MAC Address':<18} | {'Vendor / Device Label':<30} | {'Channels':<10} | {'Packets':<8} | {'Signal dBFS':<12}"
    sep = "-" * len(hdr)
    rows = [hdr, sep]
    for d in devices:
        ch_str = ",".join(str(c) for c in d.get("channels_seen", []))
        label = d.get("friendly_name") or d.get("vendor_fingerprint", d.get("type", "Unknown"))
        label = label[:30]
        sig = d.get("best_level_dbfs", d.get("max_signal_dbfs", -100.0))
        pkts = d.get("packets_seen", d.get("total_packets", 0))
        rows.append(f"{d.get('mac',''):<18} | {label:<30} | {ch_str:<10} | {pkts:<8} | {sig:<12.1f}")
    return "\n".join(rows)




def format_spectrum_table(title: str, signals: List[Dict[str, Any]]) -> str:
    md = f"### 📊 Spectrum Survey: {title}\n\n"
    if not signals:
        md += "No active carriers detected above noise floor.\n"
        return md
    hdr = f"{'Frequency (MHz)':<16} | {'Level (dBFS)':<14} | {'Occupancy (dB)':<16} | {'Status':<12}"
    sep = "-" * len(hdr)
    rows = [f"```", hdr, sep]
    for s in signals:
        rows.append(f"{s.get('freq_mhz',0.0):<16.3f} | {s.get('level_dbfs',-100.0):<14.1f} | {s.get('occ_db',0.0):<16.1f} | {s.get('status',''):<12}")
    rows.append("```")
    return md + "\n".join(rows)


def format_recon_dossier(dossier: Dict[str, Any]) -> str:
    md = f"## 🛡️ Unified Airspace Reconnaissance Dossier\n\n"
    md += f"**Execution Time**: `{dossier['elapsed_seconds']} seconds`\n\n"
    md += "### 🛰️ Airspace Overview\n"
    for k, v in dossier["tactical_findings"].items():
        md += f"- **{k.replace('_', ' ').title()}**: `{v}`\n"
    md += "\n"
    if dossier.get("ble_devices"):
        md += "### 📱 Discovered Bluetooth Devices\n```\n"
        md += format_table(dossier["ble_devices"])
        md += "\n```\n\n"
    if dossier.get("spectrum_spikes_433"):
        md += format_spectrum_table("433 MHz Remotes & IoT", dossier["spectrum_spikes_433"]) + "\n"
    if dossier.get("spectrum_spikes_315"):
        md += format_spectrum_table("315 MHz Vehicle TPMS & Keyfobs", dossier["spectrum_spikes_315"]) + "\n"
    if dossier.get("spectrum_spikes_lora"):
        md += format_spectrum_table("868 MHz LoRa / Meshtastic", dossier["spectrum_spikes_lora"]) + "\n"
    return md


def start_api_server(port: int = 8765, host: str = "127.0.0.1"):
    """
    Starts a lightweight HTTP REST micro-server for remote agents,
    webhooks, Telegram bots, Hermes, or curl to control OnAir effortlessly.
    """
    from http.server import HTTPServer, BaseHTTPRequestHandler
    bridge_inst = OnAirBridge()

    class OnAirHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, status_code: int, data: Any):
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))

        def do_OPTIONS(self):
            self._send_json(200, {"status": "ok"})

        def do_GET(self):
            parsed = self.path.split("?")[0].rstrip("/")
            if parsed in ["", "/status"]:
                hw = bridge_inst.get_hardware_status()
                mem = bridge_inst.memory.get_summary_report()
                self._send_json(200, {"status": "success", "hardware": hw, "memory_summary": mem})
            elif parsed == "/memory":
                self._send_json(200, bridge_inst.memory.data)
            else:
                self._send_json(404, {"status": "error", "message": f"Route '{parsed}' not found"})

        def do_POST(self):
            parsed = self.path.split("?")[0].rstrip("/")
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
            try:
                payload = json.loads(body)
            except Exception:
                payload = {}

            if parsed in ["/mission", "/api/mission", "/exec"]:
                intent = payload.get("intent", "").strip()
                if not intent:
                    self._send_json(400, {"status": "error", "message": "Missing 'intent' field"})
                    return
                params = payload.get("parameters", {})
                res = bridge_inst.autonomous_mission(intent, params)
                self._send_json(200, res)

            elif parsed in ["/annotate", "/api/annotate"]:
                ident = payload.get("identifier")
                note = payload.get("note", payload.get("note_or_name", ""))
                alert = payload.get("alert", False)
                if not ident or not note:
                    self._send_json(400, {"status": "error", "message": "Missing 'identifier' or 'note'"})
                    return
                bridge_inst.memory.annotate(ident, note, alert=alert)
                self._send_json(200, {"status": "success", "message": f"Annotated '{ident}' as '{note}'"})
            else:
                self._send_json(404, {"status": "error", "message": f"Route '{parsed}' not found"})

    server = HTTPServer((host, port), OnAirHTTPHandler)
    print(f"\n[OnAir HTTP API] Server listening on http://{host}:{port}")
    print(f"  - GET  /status   : Hardware & memory telemetry")
    print(f"  - GET  /memory   : Full learned intelligence store")
    print(f"  - POST /mission  : Execute single-intent mission (e.g. {{'intent': 'افحص البلوتوث'}})")
    print(f"  - POST /annotate : Label device (e.g. {{'identifier': 'MAC', 'note': 'Label'}})")
    print(f"[OnAir HTTP API] Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OnAir HTTP API] Stopped.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["--api", "--serve", "-s"]:
        port_num = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
        start_api_server(port=port_num)
    elif len(sys.argv) > 1:
        # Autonomous intent execution from command line
        intent_arg = " ".join(sys.argv[1:])
        bridge = OnAirBridge()
        print(f"\n[OnAir Autonomous Mind] Executing Intent: '{intent_arg}'...")
        res = bridge.autonomous_mission(intent_arg)
        if "markdown" in res:
            print(res["markdown"])
        else:
            print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        bridge = OnAirBridge()
        st = bridge.get_hardware_status()
        mem_sum = bridge.memory.get_summary_report()
        print("="*65)
        print("  OnAir Master Autonomous Intelligence Bridge & Engine")
        print("="*65)
        print(f"  PlutoSDR:      {st['pluto_connected']} ({st.get('pluto_endpoint', 'N/A')})")
        print(f"  GPU Engine:    {st.get('gpu_accelerator', 'N/A')}")
        print(f"  Firmware:      {st.get('pluto_firmware', 'N/A')}")
        print(f"  Memory File:   {mem_sum['vault_memory_file']}")
        print(f"  Known BLE:     {mem_sum['total_unique_ble_devices']} devices logged")
        print(f"  Known Peaks:   {mem_sum['total_active_frequencies_cataloged']} frequencies")
        print("="*65)
        print("Usage:")
        print("  1. CLI Directive:  python onair_bridge.py \"<intent in EN or AR>\"")
        print("  2. HTTP REST API:  python onair_bridge.py --api 8765")
        print("Examples:")
        print("  python onair_bridge.py \"افحص البلوتوث واكشف الاجهزة\"")
        print("  python onair_bridge.py \"مسح شامل للجو كامل\"")
        print("  python onair_bridge.py \"استرجع الذاكرة المسجلة\"")
        print("="*65)

