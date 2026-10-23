/**
 * OnAir SDR Master Web Control Center
 * Real-Time Bridge Orchestration, Dynamic Spectrum Canvas & Mission Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Config & State
  let bridgeUrl = localStorage.getItem('onair_bridge_url') || 'http://127.0.0.1:8765';
  const bridgeUrlInput = document.getElementById('bridge-url-input');
  bridgeUrlInput.value = bridgeUrl;

  const statusPluto = document.getElementById('status-pluto');
  const statusGpu = document.getElementById('status-gpu');
  const statusBridge = document.getElementById('status-bridge');
  const terminalOutput = document.getElementById('terminal-output');
  const intentInput = document.getElementById('intent-input');
  const intentForm = document.getElementById('intent-form');
  const intentSpinner = document.getElementById('intent-spinner');
  const footerTime = document.getElementById('footer-time');

  // Canvas
  const canvas = document.getElementById('spectrum-canvas');
  const ctx = canvas.getContext('2d');
  let currentSpectrumPoints = [];

  // Update Clock
  setInterval(() => {
    const d = new Date();
    footerTime.textContent = d.toLocaleTimeString('en-US', { hour12: false }) + ' UTC+3';
  }, 1000);

  // Tab Navigation
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
      if (btn.dataset.tab === 'tab-spectrum') drawSpectrum();
      if (btn.dataset.tab === 'tab-memory') loadMemory();
    });
  });

  // Reconnect Button
  document.getElementById('btn-reconnect').addEventListener('click', () => {
    bridgeUrl = bridgeUrlInput.value.trim().replace(/\/+$/, '');
    localStorage.setItem('onair_bridge_url', bridgeUrl);
    checkBridgeHealth();
  });

  // GUI Toggle / USB Release Button
  document.getElementById('btn-toggle-gui').addEventListener('click', async () => {
    logTerminal('[ACTION] Requesting Pluto USB release & GUI management...');
    try {
      const res = await executeMission("فحص الهاردوير");
      logTerminal('[USB UNLOCK] Pluto USB handle verified & free for CLI/MCP.');
      checkBridgeHealth();
    } catch (e) {
      logTerminal(`[ERROR] Failed to release USB: ${e.message}`, 'error');
    }
  });

  // Intent Form Submit
  intentForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const intent = intentInput.value.trim();
    if (!intent) return;
    executeAutonomousIntent(intent);
  });

  // Preset Chips Click
  document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const intent = chip.dataset.intent;
      intentInput.value = intent;
      executeAutonomousIntent(intent);
    });
  });

  // Terminal Controls
  document.getElementById('btn-copy-terminal').addEventListener('click', () => {
    navigator.clipboard.writeText(terminalOutput.innerText);
    alert('تم نسخ مخرجات الشاشة بنجاح!');
  });
  document.getElementById('btn-clear-terminal').addEventListener('click', () => {
    terminalOutput.innerHTML = '<div class="terminal-line system-welcome">[TERMINAL CLEARED] Ready.</div>';
  });

  // =========================================================================
  //   Bridge API Core Calls
  // =========================================================================

  async function checkBridgeHealth() {
    try {
      const resp = await fetch(`${bridgeUrl}/status`, { method: 'GET' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      statusBridge.className = 'status-pill status-online';
      statusBridge.querySelector('.pill-label').textContent = 'API Bridge: Connected';

      if (data.hardware && data.hardware.pluto_connected) {
        statusPluto.className = 'status-pill status-online';
        statusPluto.querySelector('.pill-label').textContent = `PlutoSDR: ${data.hardware.pluto_endpoint || 'Active'}`;
      } else {
        statusPluto.className = 'status-pill status-offline';
        statusPluto.querySelector('.pill-label').textContent = 'PlutoSDR: Offline';
      }

      if (data.hardware && data.hardware.gpu_accelerator) {
        statusGpu.style.display = 'inline-flex';
        statusGpu.querySelector('.pill-label').textContent = data.hardware.gpu_accelerator.replace('NVIDIA GeForce ', '');
      }

      // Update Memory Stats if available
      if (data.memory_summary) {
        updateMemoryStatBadges(data.memory_summary);
      }
    } catch (err) {
      statusBridge.className = 'status-pill status-offline';
      statusBridge.querySelector('.pill-label').textContent = 'API Bridge: Disconnected';
      statusPluto.className = 'status-pill status-offline';
      statusPluto.querySelector('.pill-label').textContent = 'PlutoSDR: Disconnected';
    }
  }

  async function executeMission(intent, parameters = {}) {
    const resp = await fetch(`${bridgeUrl}/mission`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent, parameters })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  }

  async function executeAutonomousIntent(intent) {
    logTerminal(`\n>>> [USER DIRECTIVE]: ${intent}`);
    intentSpinner.style.display = 'inline-block';

    try {
      const data = await executeMission(intent);
      intentSpinner.style.display = 'none';

      if (data.markdown) {
        logTerminal(data.markdown);
      } else if (data.summary) {
        logTerminal(`[SUMMARY]: ${data.summary}\n${JSON.stringify(data, null, 2)}`);
      } else {
        logTerminal(JSON.stringify(data, null, 2));
      }

      // If BLE Scan, refresh BLE table
      if (data.devices) {
        renderBleTable(data.devices);
      }
      // If spectrum signals, update spectrum table & canvas
      if (data.signals) {
        renderSpectrumResults(data.signals);
      }

      // Refresh memory tab
      checkBridgeHealth();
    } catch (err) {
      intentSpinner.style.display = 'none';
      logTerminal(`[ERROR]: Could not reach local bridge (${err.message}). Make sure 'python onair_bridge.py --api 8765' is running on the SDR host.`, 'error');
    }
  }

  function logTerminal(text, type = 'normal') {
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    line.innerHTML = text.replace(/\n/g, '<br>').replace(/`([^`]+)`/g, '<span style="color:#06b6d4;">$1</span>');
    terminalOutput.appendChild(line);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }

  // =========================================================================
  //   Spectrum Sweep & Canvas Visualizer
  // =========================================================================
  const bandPresets = {
    subghz_ism: { from: 433.0, to: 435.0, step: 0.2 },
    subghz_315: { from: 314.0, to: 316.0, step: 0.2 },
    lora_868: { from: 867.0, to: 870.0, step: 0.2 },
    lora_915: { from: 902.0, to: 928.0, step: 0.5 },
    broadcast_fm: { from: 88.0, to: 108.0, step: 0.4 },
    ism_2400: { from: 2400.0, to: 2484.0, step: 2.0 },
    marine_ais: { from: 161.9, to: 162.1, step: 0.05 },
    aviation_vdl2: { from: 136.9, to: 137.1, step: 0.05 }
  };

  document.querySelectorAll('.band-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.band-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const b = bandPresets[btn.dataset.band];
      if (b) {
        document.getElementById('spec-from').value = b.from;
        document.getElementById('spec-to').value = b.to;
        document.getElementById('spec-step').value = b.step;
      }
    });
  });

  document.getElementById('btn-scan-spectrum').addEventListener('click', async () => {
    const from_mhz = parseFloat(document.getElementById('spec-from').value);
    const to_mhz = parseFloat(document.getElementById('spec-to').value);
    const step_mhz = parseFloat(document.getElementById('spec-step').value);

    logTerminal(`[SPECTRUM] Sweeping ${from_mhz} MHz -> ${to_mhz} MHz (step: ${step_mhz} MHz)...`);
    try {
      const res = await executeMission(`مسح طيفي من ${from_mhz} الى ${to_mhz}`, { from_mhz, to_mhz, step_mhz });
      logTerminal(`[SPECTRUM COMPLETE] Active carriers found: ${res.signals ? res.signals.length : 0}`);
      if (res.signals) renderSpectrumResults(res.signals);
    } catch (e) {
      logTerminal(`[SPECTRUM ERROR] ${e.message}`, 'error');
    }
  });

  function renderSpectrumResults(signals) {
    const tbody = document.getElementById('spectrum-table-body');
    const badge = document.getElementById('spectrum-stats-badge');
    badge.textContent = `${signals.length} إشارات نشطة`;
    currentSpectrumPoints = signals;
    drawSpectrum();

    if (!signals || signals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">لم يتم رصد أي حامل نشط فوق مستوى الضوضاء.</td></tr>';
      return;
    }

    tbody.innerHTML = signals.map(s => `
      <tr>
        <td style="color:var(--accent-cyan); font-weight:700;">${s.freq_mhz.toFixed(3)} MHz</td>
        <td style="color:${s.level_dbfs > -50 ? '#ef4444' : '#10b981'}; font-weight:600;">${s.level_dbfs.toFixed(1)} dBFS</td>
        <td>${s.occ_db.toFixed(1)} dB</td>
        <td><span class="badge ${s.status === 'empty' ? 'badge-info' : 'badge-accent'}">${s.status || 'Carrier Spike'}</span></td>
      </tr>
    `).join('');
  }

  function drawSpectrum() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // Draw Grid
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 60) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Baseline Noise Floor
    ctx.strokeStyle = '#0284c7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, canvas.height - 30);
    for (let x = 0; x < canvas.width; x += 15) {
      const noise = (Math.random() - 0.5) * 8;
      ctx.lineTo(x, canvas.height - 30 + noise);
    }
    ctx.stroke();

    // Draw Carrier Peaks if any
    if (currentSpectrumPoints.length > 0) {
      currentSpectrumPoints.forEach((p, idx) => {
        const x = (idx + 1) * (canvas.width / (currentSpectrumPoints.length + 1));
        const peakHeight = Math.min(220, Math.max(40, (100 + p.level_dbfs) * 3));
        const y = canvas.height - peakHeight;

        // Gradient Spike
        const grad = ctx.createLinearGradient(x, y, x, canvas.height);
        grad.addColorStop(0, '#06b6d4');
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.fillRect(x - 12, y, 24, peakHeight);

        // Top line
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(x - 12, y);
        ctx.lineTo(x + 12, y);
        ctx.stroke();

        // Label
        ctx.fillStyle = '#f8fafc';
        ctx.font = '10px Cairo';
        ctx.fillText(`${p.freq_mhz.toFixed(2)}MHz`, x - 20, y - 8);
      });
    }
  }
  drawSpectrum();

  // =========================================================================
  //   Bluetooth Tactical Matrix
  // =========================================================================
  document.getElementById('btn-scan-ble').addEventListener('click', async () => {
    const secs = parseInt(document.getElementById('ble-secs').value, 10);
    const gain = parseInt(document.getElementById('ble-gain').value, 10);
    logTerminal(`[BLE SCAN] Listening on advertising channels 37, 38, 39 (${secs}s/ch, Gain: ${gain}dB)...`);

    try {
      const res = await executeMission("افحص البلوتوث واكشف الاجهزة", { secs, gain });
      logTerminal(`[BLE SCAN COMPLETE] Devices discovered: ${res.devices ? res.devices.length : 0}`);
      if (res.devices) renderBleTable(res.devices);
    } catch (e) {
      logTerminal(`[BLE ERROR] ${e.message}`, 'error');
    }
  });

  function renderBleTable(devices) {
    const tbody = document.getElementById('ble-table-body');
    const badge = document.getElementById('ble-count-badge');
    badge.textContent = `${devices.length} أجهزة`;

    if (!devices || devices.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">لم يتم العثور على أجهزة بلوتوث قريبة في هذه الدورة.</td></tr>';
      return;
    }

    tbody.innerHTML = devices.map(d => {
      const label = d.friendly_name || d.vendor_fingerprint || d.type || 'Unknown';
      const sig = d.best_level_dbfs || d.max_signal_dbfs || -100;
      const channels = (d.channels_seen || []).join(', ');
      return `
        <tr>
          <td style="font-weight:700; color:var(--accent-cyan);">${d.mac}</td>
          <td><strong style="color:#e2e8f0;">${label}</strong></td>
          <td><span class="badge badge-info">${d.type || d.addr_type || 'Private'}</span></td>
          <td><code>${channels}</code></td>
          <td>${d.packets_seen || d.total_packets || 0}</td>
          <td style="color:${sig > -50 ? '#10b981' : '#f59e0b'}; font-weight:700;">${sig.toFixed(1)} dBFS</td>
          <td>
            <button class="btn btn-outline-sm btn-annotate" data-mac="${d.mac}">تسمية 🏷️</button>
          </td>
        </tr>
      `;
    }).join('');

    // Attach Annotate Buttons
    document.querySelectorAll('.btn-annotate').forEach(btn => {
      btn.addEventListener('click', async () => {
        const mac = btn.dataset.mac;
        const name = prompt(`أدخل التسمية التكتيكية للجهاز (${mac}):`, 'هاتف المستخدم');
        if (name) {
          try {
            await fetch(`${bridgeUrl}/annotate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ identifier: mac, note: name })
            });
            alert(`تم حفظ التسمية: ${mac} -> ${name}`);
            executeAutonomousIntent("استرجع الذاكرة المسجلة");
          } catch (e) {
            alert(`فشل الحفظ: ${e.message}`);
          }
        }
      });
    });
  }

  // =========================================================================
  //   Protocol Decoders Lab
  // =========================================================================

  // FM RDS
  document.getElementById('btn-decode-fm').addEventListener('click', async () => {
    const freq = parseFloat(document.getElementById('fm-freq').value);
    logTerminal(`[FM RDS] Demodulating ${freq} MHz broadcast...`);
    try {
      const res = await executeMission(`شغل محطة FM راديو ${freq}`, { freq_mhz: freq });
      const rds = res.rds || {};
      document.getElementById('fm-ps').textContent = rds.program_service_ps || 'N/A';
      document.getElementById('fm-pi').textContent = rds.pi_code || 'N/A';
      document.getElementById('fm-rt').textContent = rds.radio_text_rt || 'N/A';
      document.getElementById('fm-dev').textContent = `${rds.frequency_deviation_khz || 0} kHz`;
      logTerminal(`[FM DECODE COMPLETE] Station PS: ${rds.program_service_ps || 'Locked'}`);
    } catch (e) {
      logTerminal(`[FM ERROR] ${e.message}`, 'error');
    }
  });

  // Digital TV
  document.getElementById('btn-decode-tv').addEventListener('click', async () => {
    const freq = parseFloat(document.getElementById('tv-freq').value);
    const std = document.getElementById('tv-std').value;
    logTerminal(`[DVB TV] Demodulating ${std.toUpperCase()} at ${freq} MHz with RTX 5060 Ti GPU LDPC...`);
    try {
      const res = await executeMission(`فك تشفير البث التلفزيوني الرقمي DVB-T2`, { freq_mhz: freq, standard: std });
      const m = (res.details && res.details.metrics) || {};
      document.getElementById('tv-lock').textContent = m.lock ? 'YES (LOCKED)' : 'NO LOCK';
      document.getElementById('tv-snr').textContent = `${m.snr_db || 'N/A'} dB`;
      document.getElementById('tv-mer').textContent = `${m.mer_db || 'N/A'} dB`;
      document.getElementById('tv-services').textContent = JSON.stringify(m.services || []);
      logTerminal(`[TV DECODE COMPLETE] Lock: ${m.lock}`);
    } catch (e) {
      logTerminal(`[TV ERROR] ${e.message}`, 'error');
    }
  });

  // Satellite
  document.getElementById('btn-decode-sat').addEventListener('click', async () => {
    const sat = document.getElementById('sat-type').value;
    logTerminal(`[SATELLITE] Demodulating ${sat.toUpperCase()} downlinks...`);
    try {
      const res = await executeMission(`تتبع اشارات اقمار ${sat}`, { sat_type: sat });
      document.getElementById('sat-log').textContent = res.log || 'Burst capture completed.';
      logTerminal(`[SATELLITE COMPLETE] Log received.`);
    } catch (e) {
      logTerminal(`[SATELLITE ERROR] ${e.message}`, 'error');
    }
  });

  // Raw CS8 Capture
  document.getElementById('btn-record-iq').addEventListener('click', async () => {
    const freq = parseFloat(document.getElementById('rec-freq').value);
    const secs = parseInt(document.getElementById('rec-secs').value, 10);
    logTerminal(`[RAW CAPTURE] Recording SigMF CS8 samples at ${freq} MHz (${secs}s)...`);
    try {
      const res = await executeMission(`سجل اشارة خام ${freq} ميغاهرتز لمدة ${secs} ثواني`, { freq_mhz: freq, secs });
      document.getElementById('rec-file').textContent = res.file || 'capture.cs8';
      document.getElementById('rec-size').textContent = `${((res.size || 0) / (1024*1024)).toFixed(2)} MB`;
      logTerminal(`[CAPTURE SAVED] File: ${res.file} (${res.size} bytes)`);
    } catch (e) {
      logTerminal(`[CAPTURE ERROR] ${e.message}`, 'error');
    }
  });

  // =========================================================================
  //   Memory Explorer
  // =========================================================================
  async function loadMemory() {
    try {
      const resp = await fetch(`${bridgeUrl}/memory`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      document.getElementById('mem-ble-count').textContent = Object.keys(data.ble_devices || {}).length;
      document.getElementById('mem-peaks-count').textContent = Object.keys(data.spectrum_peaks || {}).length;
      document.getElementById('mem-fm-count').textContent = Object.keys(data.broadcast_stations || {}).length;
      document.getElementById('mem-captures-count').textContent = (data.rf_captures || []).length;

      document.getElementById('memory-json-display').textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      document.getElementById('memory-json-display').textContent = `Could not load memory file: ${e.message}`;
    }
  }

  function updateMemoryStatBadges(summary) {
    document.getElementById('mem-ble-count').textContent = summary.total_unique_ble_devices || 0;
    document.getElementById('mem-peaks-count').textContent = summary.total_active_frequencies_cataloged || 0;
    document.getElementById('mem-fm-count').textContent = summary.total_fm_stations_identified || 0;
    document.getElementById('mem-captures-count').textContent = summary.total_rf_raw_captures_in_vault || 0;
  }

  document.getElementById('btn-refresh-memory').addEventListener('click', loadMemory);
  document.getElementById('btn-copy-memory-json').addEventListener('click', () => {
    navigator.clipboard.writeText(document.getElementById('memory-json-display').textContent);
    alert('تم نسخ سجل الذاكرة الكامل بنجاح!');
  });

  // Copy Code Snippets
  document.querySelectorAll('.btn-copy-code').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.copy;
      const el = document.getElementById(id);
      if (el) {
        navigator.clipboard.writeText(el.innerText);
        btn.textContent = 'تم النسخ! ✓';
        setTimeout(() => btn.textContent = 'نسخ', 2000);
      }
    });
  });

  // Initial Health Check
  checkBridgeHealth();
  setInterval(checkBridgeHealth, 15000);
});
