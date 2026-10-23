#!/usr/bin/env python3
"""
=============================================================================
  OnAir Master MCP Server (Model Context Protocol) v2.5.0
  The 'Soul, Mind & Body' SDR Command Hub for AI Agents
=============================================================================
Protocol: JSON-RPC 2.0 over stdio (Model Context Protocol specification)
Usable by: Claude Code, Antigravity IDE, Cursor, Hermes, or any MCP client.
Features:
  - onair_autonomous_mission: Single-intent natural language execution (EN & AR)
  - onair_full_airspace_recon: Multi-band tactical electronic intelligence sweep
  - onair_query_learned_memory: Query HackVault persistent RF catalog & device memory
  - onair_annotate_memory: Label MACs or frequencies with friendly names or alerts
  - 13 Granular Protocol Decoders: BLE, DVB-T2, FM/RDS, Iridium, dPMR, Spectrum, PCAP, IQ
"""

import sys
import os
import json
import logging

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onair_bridge import OnAirBridge, COMMON_RF_BANDS, BLE_CHANNELS, format_table

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

SERVER_NAME = "onair-sdr-master"
SERVER_VERSION = "2.5.0"

bridge = OnAirBridge()

TOOLS = [
    {
        "name": "onair_autonomous_mission",
        "description": "MASTER SINGLE-INTENT DISPATCHER: Send one high-level instruction in English or Arabic (e.g. 'مسح شامل للجو', 'افحص البلوتوث واكشف الاجهزة', 'ابحث عن ريموتات 433', 'فحص الهاردوير', 'استرجع الذاكرة'). The system autonomously resolves radio locks, plans parameters, executes the exact PHY pipeline, updates persistent memory in HackVault, and returns an intelligence dossier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Natural language mission directive or high-level command (e.g., 'scan nearby bluetooth devices', 'مسح شامل للجو', 'inspect 433MHz remotes', 'hardware status', 'recall learned memory')."
                },
                "parameters": {
                    "type": "object",
                    "description": "Optional parameters to override defaults (e.g., {'secs': 6, 'gain': 45, 'quick': true, 'freq_mhz': 433.92})."
                }
            },
            "required": ["intent"]
        }
    },
    {
        "name": "onair_full_airspace_recon",
        "description": "Multi-Band Tactical Airspace Reconnaissance: Sequentially audits BLE advertising channels, Sub-GHz 433 MHz remotes, 315 MHz vehicle security, 868 MHz LoRa/Meshtastic, and FM radio carriers. Synthesizes a unified ELINT briefing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "quick": {
                    "type": "boolean",
                    "description": "Quick sweep mode for spectrum steps (default: true).",
                    "default": True
                },
                "gain": {
                    "type": "integer",
                    "description": "Receiver gain in dB (default: 44).",
                    "default": 44
                }
            },
            "required": []
        }
    },
    {
        "name": "onair_query_learned_memory",
        "description": "Retrieves the persistent learned RF intelligence memory stored in HackVault (ONAIR_LEARNED_MEMORY.json). Returns cataloged BLE MACs, historical sightings, carrier frequencies, FM stations, and raw captures.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "onair_annotate_memory",
        "description": "Labels a MAC address or frequency in persistent memory with a friendly name or alert status (e.g. 'User iPhone', 'Suspicious Tracker', 'Front Gate Remote').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "MAC address (e.g. '7B:44:03:E5:60:86') or frequency (e.g. '433.92')."
                },
                "note_or_name": {
                    "type": "string",
                    "description": "Friendly label or tactical note."
                },
                "alert": {
                    "type": "boolean",
                    "description": "Flag as alert item (default: false).",
                    "default": False
                }
            },
            "required": ["identifier", "note_or_name"]
        }
    },
    {
        "name": "onair_get_hardware_status",
        "description": "Probes ADALM-Pluto SDR connection, firmware, NVIDIA RTX 5060 Ti GPU acceleration, and OnAir.exe GUI conflict status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "onair_manage_gui_process",
        "description": "Manages OnAir.exe GUI process (check status, start, or stop it to release exclusive PlutoSDR USB handle for CLI/MCP tasks).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "start", "stop"],
                    "description": "Action to perform on OnAir.exe GUI process."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "onair_scan_bluetooth",
        "description": "Scans Bluetooth Low Energy (BLE) channels 37, 38, 39 using PlutoSDR. Discovers nearby devices, MACs, types, signal dBFS, packet counts, and SNR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "secs_per_channel": {
                    "type": "integer",
                    "description": "Duration in seconds to listen on each channel (default: 8).",
                    "default": 8
                },
                "channels": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of channels to scan (default: [37, 38, 39]).",
                    "default": [37, 38, 39]
                },
                "gain": {
                    "type": "integer",
                    "description": "Pluto receiver gain in dB (0-73, default: 44).",
                    "default": 44
                }
            },
            "required": []
        }
    },
    {
        "name": "onair_scan_spectrum",
        "description": "Sweeps an RF spectrum range with PlutoSDR. Discovers active transmitters, carrier peaks, occupancy levels, and signal strengths in dBFS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_mhz": {
                    "type": "number",
                    "description": "Starting frequency in MHz."
                },
                "to_mhz": {
                    "type": "number",
                    "description": "Ending frequency in MHz."
                },
                "step_mhz": {
                    "type": "number",
                    "description": "Sweep frequency step in MHz (default: 0.5).",
                    "default": 0.5
                },
                "quick": {
                    "type": "boolean",
                    "description": "Perform rapid sweep (default: true).",
                    "default": True
                }
            },
            "required": ["from_mhz", "to_mhz"]
        }
    },
    {
        "name": "onair_scan_preset_band",
        "description": "Instantly sweeps common radio bands (subghz_ism, subghz_315, lora_868, lora_915, tetra_390, ism_2400, broadcast_fm, marine_ais, aviation_vdl2).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "band_name": {
                    "type": "string",
                    "enum": list(COMMON_RF_BANDS.keys()),
                    "description": "Identifier of the predefined band to sweep."
                }
            },
            "required": ["band_name"]
        }
    },
    {
        "name": "onair_decode_broadcast_fm_rds",
        "description": "Demodulates Broadcast FM radio stations (88-108 MHz) and decodes RDS/RBDS subcarrier data (Station Name PS, RadioText RT, PI code, frequency deviation).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "FM station center frequency in MHz (e.g. 100.0)."
                },
                "secs": {
                    "type": "integer",
                    "description": "Listening and decoding duration in seconds (default: 5).",
                    "default": 5
                },
                "gain": {
                    "type": "integer",
                    "description": "Pluto receiver gain (default: 50).",
                    "default": 50
                }
            },
            "required": ["freq_mhz"]
        }
    },
    {
        "name": "onair_decode_digital_tv",
        "description": "Demodulates terrestrial digital television signals (DVB-T2, DVB-T, ATSC, ISDB-T) with GPU LDPC acceleration. Returns SNR, MER, pre-BER, locked status, and service names.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "UHF/VHF center frequency in MHz (e.g. 490.0)."
                },
                "standard": {
                    "type": "string",
                    "enum": ["t2", "t", "atsc", "atsc3", "isdbt", "dvbc"],
                    "description": "Digital TV standard (default: 't2').",
                    "default": "t2"
                },
                "secs": {
                    "type": "integer",
                    "description": "Acquisition duration in seconds (default: 6).",
                    "default": 6
                }
            },
            "required": ["freq_mhz"]
        }
    },
    {
        "name": "onair_satellite_decoder",
        "description": "Demodulates satellite constellations: Iridium bursts (1621.25 MHz) or Orbcomm VHF telemetry (137.5 MHz).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sat_type": {
                    "type": "string",
                    "enum": ["iridium", "orbcomm"],
                    "description": "Satellite network to target (default: 'iridium').",
                    "default": "iridium"
                },
                "secs": {
                    "type": "integer",
                    "description": "Burst listening duration in seconds (default: 10).",
                    "default": 10
                }
            },
            "required": ["sat_type"]
        }
    },
    {
        "name": "onair_dpmr_scanner",
        "description": "Scans and decodes Digital Private Mobile Radio (dPMR446 digital voice channels).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "Center frequency in MHz (default: 446.0).",
                    "default": 446.0
                },
                "secs": {
                    "type": "integer",
                    "description": "Monitoring duration in seconds (default: 10).",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "onair_stream_network_transport",
        "description": "Streams demodulated Transport Stream live over UDP or RTP to a network socket for playback in VLC or network receivers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "Center frequency in MHz."
                },
                "standard": {
                    "type": "string",
                    "enum": ["t2", "t", "atsc", "isdbt", "dvbc"],
                    "default": "t2"
                },
                "protocol": {
                    "type": "string",
                    "enum": ["udp", "rtp"],
                    "default": "udp"
                },
                "dest_ip": {
                    "type": "string",
                    "default": "127.0.0.1"
                },
                "dest_port": {
                    "type": "integer",
                    "default": 1234
                },
                "secs": {
                    "type": "integer",
                    "default": 30
                }
            },
            "required": ["freq_mhz"]
        }
    },
    {
        "name": "onair_extract_network_pcap",
        "description": "Extracts broadcast IP data packets (MPE / GSE) directly into PCAP format for Wireshark inspection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "Carrier frequency in MHz."
                },
                "standard": {
                    "type": "string",
                    "enum": ["t2", "t", "atsc"],
                    "default": "t2"
                },
                "pcap_file": {
                    "type": "string",
                    "description": "Output .pcap filename (default: 'traffic.pcap').",
                    "default": "traffic.pcap"
                },
                "secs": {
                    "type": "integer",
                    "default": 15
                }
            },
            "required": ["freq_mhz"]
        }
    },
    {
        "name": "onair_record_rf_capture",
        "description": "Captures raw SigMF CS8 IQ samples from PlutoSDR to disk for offline analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freq_mhz": {
                    "type": "number",
                    "description": "Center frequency in MHz (e.g. 433.92)."
                },
                "gain": {
                    "type": "integer",
                    "description": "Pluto gain (0-73, default: 50).",
                    "default": 50
                },
                "secs": {
                    "type": "integer",
                    "description": "Duration in seconds (default: 5).",
                    "default": 5
                },
                "bw": {
                    "type": "string",
                    "description": "Bandwidth (e.g. '1M', '2M', '4M', default: '2M').",
                    "default": "2M"
                },
                "output_file": {
                    "type": "string",
                    "description": "Destination file path (default: 'capture.cs8').",
                    "default": "capture.cs8"
                }
            },
            "required": ["freq_mhz"]
        }
    },
    {
        "name": "onair_execute_custom_pipeline",
        "description": "Total Atomic Control: Executes onair-cli.exe with ANY arbitrary flags (--sopt, --sval, --bw, --gain, --ref, etc.) and environment variables (DECT2_*). Allows testing custom modifications on the fly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "arguments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of command line arguments (e.g. ['--freq', '433.92', '--secs', '5', '--sopt', 'filter', '--sval', 'wide'])."
                },
                "env_vars": {
                    "type": "object",
                    "description": "Optional dictionary of environment variables (e.g. {'DECT2_GPU_ADAPTER': '0', 'DECT2_PLPLOG': '1'})."
                },
                "timeout_secs": {
                    "type": "integer",
                    "description": "Command timeout in seconds (default: 30).",
                    "default": 30
                }
            },
            "required": ["arguments"]
        }
    }
]


def handle_initialize(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION
            }
        }
    }


def handle_tools_list(req_id):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": TOOLS
        }
    }


def handle_tool_call(req_id, name, args):
    try:
        # Autonomous Master Intent Dispatcher
        if name == "onair_autonomous_mission":
            intent = args["intent"]
            params = args.get("parameters", {})
            res = bridge.autonomous_mission(intent, params)
            text = res.get("markdown") or json.dumps(res, indent=2, ensure_ascii=False)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_full_airspace_recon":
            res = bridge.full_airspace_recon(quick=args.get("quick", True), gain=args.get("gain", 44))
            from onair_bridge import format_recon_dossier
            md = format_recon_dossier(res)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": md}], "isError": False}}

        elif name == "onair_query_learned_memory":
            summary = bridge.memory.get_summary_report()
            text = json.dumps(summary, indent=2, ensure_ascii=False)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_annotate_memory":
            ident = args["identifier"]
            note = args["note_or_name"]
            alert = args.get("alert", False)
            bridge.memory.annotate(ident, note, alert=alert)
            msg = f"Annotation saved: '{ident}' -> '{note}' (Alert: {alert})"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": msg}], "isError": False}}

        elif name == "onair_get_hardware_status":
            res = bridge.get_hardware_status()
            text = (
                f"### PlutoSDR Hardware & OnAir Status:\n"
                f"- **Pluto Connected:** {res['pluto_connected']}\n"
                f"- **Endpoint:** {res.get('pluto_endpoint', 'N/A')}\n"
                f"- **Firmware:** {res.get('pluto_firmware', 'N/A')}\n"
                f"- **GPU LDPC Engine:** {res.get('gpu_accelerator', 'N/A')}\n"
                f"- **OnAir GUI Running:** {res['gui_running']} ({res['gui_note']})\n"
                f"- **Supported Standards:** {', '.join(res['supported_modes'])}"
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_manage_gui_process":
            action = args["action"]
            res = bridge.manage_gui(action)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}], "isError": False}}

        elif name == "onair_scan_bluetooth":
            secs = args.get("secs_per_channel", 8)
            chans = args.get("channels", [37, 38, 39])
            gain = args.get("gain", 44)
            res = bridge.scan_ble(channels=chans, secs_per_channel=secs, gain=gain)
            tbl = format_table(res["devices"])
            text = f"### Bluetooth Scan Results ({res['total_devices_discovered']} devices, {res['total_packets']} packets):\n\n```\n{tbl}\n```\n\n**Raw Details:**\n```json\n{json.dumps(res, indent=2, ensure_ascii=False)}\n```"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_scan_spectrum":
            res = bridge.scan_spectrum(args["from_mhz"], args["to_mhz"], step_mhz=args.get("step_mhz", 0.5), quick=args.get("quick", True))
            summary = f"### Spectrum Sweep: {args['from_mhz']} MHz -> {args['to_mhz']} MHz\n- **Total Bins:** {res['total_bins']}\n- **Active Signals:** {res['active_signals_count']}\n\n"
            if res["active_signals"]:
                summary += "| Frequency (MHz) | Signal Level (dBFS) | Occupancy (dB) | Status |\n|---|---|---|---|\n"
                for s in res["active_signals"]:
                    summary += f"| {s['freq_mhz']:.2f} | {s['level_dbfs']:.1f} | {s['occ_db']:+.1f} | {s['status']} |\n"
            else:
                summary += "No active signals above noise threshold detected."
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": summary}], "isError": False}}

        elif name == "onair_scan_preset_band":
            bname = args["band_name"]
            b = COMMON_RF_BANDS[bname]
            res = bridge.scan_spectrum(b["from"], b["to"], step_mhz=b["step"])
            summary = f"### Preset Band Scan: {bname} ({b['desc']})\n- Range: {b['from']} -> {b['to']} MHz\n- Active Transmitters Detected: {res['active_signals_count']}\n\n"
            if res["active_signals"]:
                summary += "| Frequency (MHz) | Level (dBFS) | Occupancy (dB) | Status |\n|---|---|---|---|\n"
                for s in res["active_signals"]:
                    summary += f"| {s['freq_mhz']:.2f} | {s['level_dbfs']:.1f} | {s['occ_db']:+.1f} | {s['status']} |\n"
            else:
                summary += "Band is quiet (all channels empty / below noise threshold)."
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": summary}], "isError": False}}

        elif name == "onair_decode_broadcast_fm_rds":
            res = bridge.decode_fm_rds(args["freq_mhz"], secs=args.get("secs", 5), gain=args.get("gain", 50))
            rds = res["rds"]
            text = (
                f"### FM Station Demodulation ({res['frequency_mhz']} MHz):\n"
                f"- **Station Name (PS):** {rds.get('program_service_ps') or 'N/A'}\n"
                f"- **PI Code:** {rds.get('pi_code') or 'N/A'}\n"
                f"- **RadioText (RT):** {rds.get('radio_text_rt') or 'N/A'}\n"
                f"- **Frequency Deviation:** {rds.get('frequency_deviation_khz') or 'N/A'} kHz\n\n"
                f"**Decoder Log Snippet:**\n```\n{res['raw_log_tail']}\n```"
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_decode_digital_tv":
            res = bridge.decode_digital_tv(args["freq_mhz"], standard=args.get("standard", "t2"), secs=args.get("secs", 6))
            m = res["metrics"]
            text = (
                f"### Digital TV Decoder ({res['standard'].upper()} on {res['frequency_mhz']} MHz):\n"
                f"- **Locked:** {m['lock']}\n"
                f"- **SNR:** {m['snr_db']} dB | **MER:** {m['mer_db']} dB | **pre-BER:** {m['pre_ber']}\n"
                f"- **Services:** {json.dumps(m['services'])}\n\n"
                f"**Receiver Log Snippet:**\n```\n{res['raw_log_tail']}\n```"
            )
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_satellite_decoder":
            res = bridge.decode_satellite(sat_type=args.get("sat_type", "iridium"), secs=args.get("secs", 10))
            text = f"### Satellite Decoder ({res['satellite'].upper()}):\n\n```\n{res['log']}\n```"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_dpmr_scanner":
            res = bridge.scan_dpmr(freq_mhz=args.get("freq_mhz", 446.0), secs=args.get("secs", 10))
            text = f"### dPMR Digital Voice Scanner ({args.get('freq_mhz', 446.0)} MHz):\n\n```\n{res['log']}\n```"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_stream_network_transport":
            res = bridge.start_network_stream(args["freq_mhz"], standard=args.get("standard", "t2"), protocol=args.get("protocol", "udp"), dest_ip=args.get("dest_ip", "127.0.0.1"), dest_port=args.get("dest_port", 1234), secs=args.get("secs", 30))
            text = f"### Network Transport Streaming Started:\n- Protocol: {res['protocol']}\n- Destination: {res['destination']}\n- Process PID: {res['pid']}\n- Command: `{res['command']}`"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_extract_network_pcap":
            res = bridge.dump_network_pcap(args["freq_mhz"], standard=args.get("standard", "t2"), pcap_file=args.get("pcap_file", "traffic.pcap"), secs=args.get("secs", 15))
            text = f"### Network IP-PCAP Extraction:\n- File: {res['pcap_file']}\n- Size: {res['size_bytes'] / 1024:.2f} KB\n- Status: {res['status']}"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": False}}

        elif name == "onair_record_rf_capture":
            res = bridge.record_iq(args["freq_mhz"], bw=args.get("bw", "2M"), gain=args.get("gain", 50), secs=args.get("secs", 5), output_file=args.get("output_file", "capture.cs8"))
            summary = f"### RF Recording Summary:\n- **File:** {res['file']}\n- **Size:** {res['size_bytes'] / (1024*1024):.2f} MB\n- **Status:** {res['status']}\n- **SigMF Metadata:** {res['meta_file']}"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": summary}], "isError": res["status"] != "success"}}

        elif name == "onair_execute_custom_pipeline":
            res = bridge.execute_custom_pipeline(args["arguments"], env_vars=args.get("env_vars"), timeout=args.get("timeout_secs", 30))
            text = f"### Custom Pipeline Execution Result:\n- Status: {res['status']}\n- Exit Code: {res.get('exit_code')}\n\n**Output:**\n```\n{res['output'][-1500:]}\n```"
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": text}], "isError": res["status"] != "success"}}

        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method {name} not found"}}

    except Exception as e:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            resp = handle_initialize(req_id)
        elif method == "notifications/initialized":
            continue
        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
        elif method == "tools/list":
            resp = handle_tools_list(req_id)
        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            resp = handle_tool_call(req_id, name, args)
        else:
            resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method {method} not supported"}}

        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
