/**
 * Somatiq AI - Radiology Voice Dictation Assistant (V1)
 * Client-Side Controller
 * - Real-time WebSocket connection to /ws/dictate
 * - Microphone capture & AudioContext real-time waveform visualizer
 * - Spoken voice commands & macro interception with live ghost-text indicator
 * - AI Report Auto-Structuring (POST /api/format-report via Gemini / safety engine)
 * - Word counter, print export & RIS/PACS clipboard copy
 */

// Application State
const state = {
  isRecording: false,
  ws: null,
  recognition: null,
  audioContext: null,
  analyser: null,
  microphone: null,
  animationId: null,
  recTimerInterval: null,
  recSeconds: 0,
  templates: [],
  currentReportId: null,
  reconnectAttempts: 0,
  reconnectTimer: null,
  heartbeatInterval: null,
  offlineBuffer: [],
  sttMode: 'dual'
};

// DOM References
const btnMicToggle = document.getElementById('btnMicToggle');
const micPulseRing = document.getElementById('micPulseRing');
const micStatusDot = document.getElementById('micStatusDot');
const micStatusText = document.getElementById('micStatusText');
const recTimer = document.getElementById('recTimer');
const richEditor = document.getElementById('richEditor');
const ghostText = document.getElementById('ghostText');
const selectTemplate = document.getElementById('selectTemplate');
const selectSttEngine = document.getElementById('selectSttEngine');
const patientName = document.getElementById('patientName');
const patientUHID = document.getElementById('patientUHID');
const patientAgeSex = document.getElementById('patientAgeSex');
const patientModality = document.getElementById('patientModality');
const studyDateText = document.getElementById('studyDateText');
const wordCount = document.getElementById('wordCount');
const toastNotification = document.getElementById('toastNotification');
const wsStatusDot = document.getElementById('wsStatusDot');
const wsStatusText = document.getElementById('wsStatusText');
const waveformCanvas = document.getElementById('waveformCanvas');

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  // Set current study date
  studyDateText.textContent = new Date().toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric'
  });

  initWebSocket();
  initSpeechRecognition();
  loadTemplates();
  initCanvasWaveform();
  checkServerHealth();
  
  // Word count tracker
  richEditor.addEventListener('input', updateWordCount);

  // STT Engine Selector
  if (selectSttEngine) {
    selectSttEngine.addEventListener('change', (e) => {
      state.sttMode = e.target.value;
      const label = e.target.options[e.target.selectedIndex].text;
      showToast(`Speech Engine set to: ${label}`);
    });
  }
});

async function checkServerHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();
    const pass2Badge = document.getElementById('pass2Badge');
    if (pass2Badge) {
      if (data.gemini_api_configured) {
        pass2Badge.className = 'px-2 py-1 rounded bg-purple-950/80 border border-purple-800 text-purple-300';
        pass2Badge.textContent = 'Pass-2 Gemini Flash: ON';
      } else {
        pass2Badge.className = 'px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-400';
        pass2Badge.textContent = 'Pass-2: Local Fallback';
      }
    }
  } catch (e) {
    console.warn('Health check error:', e);
  }
}

// 1. WebSocket Live Stream Connection (/ws/dictate) with Auto-Reconnect & Offline Buffering
function initWebSocket() {
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  if (state.heartbeatInterval) {
    clearInterval(state.heartbeatInterval);
    state.heartbeatInterval = null;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/dictate`;

  try {
    state.ws = new WebSocket(wsUrl);
  } catch (err) {
    scheduleReconnect();
    return;
  }

  state.ws.onopen = () => {
    state.reconnectAttempts = 0;
    wsStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500';
    wsStatusText.textContent = 'WS Live';

    // Start keepalive heartbeat ping every 20 seconds
    state.heartbeatInterval = setInterval(() => {
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        try {
          state.ws.send(JSON.stringify({ type: 'ping' }));
        } catch (e) {}
      }
    }, 20000);

    // Flush offline buffer if any dictations were queued during network blip
    if (state.offlineBuffer && state.offlineBuffer.length > 0) {
      const bufferCount = state.offlineBuffer.length;
      while (state.offlineBuffer.length > 0) {
        const item = state.offlineBuffer.shift();
        try {
          state.ws.send(JSON.stringify(item));
        } catch (e) {
          state.offlineBuffer.unshift(item);
          break;
        }
      }
      showToast(`Network restored. Synced ${bufferCount} offline dictation segment(s) to server.`);
    }
  };

  state.ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'pong' || data.type === 'connection_ready') {
        return;
      }
      if (data.type === 'transcription_result' || data.type === 'audio_chunk_transcribed') {
        const textToInsert = data.formatted_text || data.text;
        if (data.command === 'clear_last_sentence') {
          deleteLastSentence();
        } else if (textToInsert) {
          insertTextAtCursor(textToInsert);
          ghostText.textContent = textToInsert;
        }

        // Render live correction badges in feed
        if (data.corrections_applied && data.corrections_applied.length > 0) {
          renderCorrectionsInFeed(data.corrections_applied);
        }

        // Render live clinical safety flags (Handbook Boundaries)
        if (data.quality_flags || data.uncertain_terms) {
          renderSafetyFlags(data.quality_flags, data.uncertain_terms, data.split_function_check);
        }
      }
    } catch (e) {
      console.warn('WS message parse error:', e);
    }
  };

  state.ws.onclose = () => {
    scheduleReconnect();
  };

  state.ws.onerror = (e) => {
    console.warn('WebSocket encountered error:', e);
  };
}

function scheduleReconnect() {
  if (state.heartbeatInterval) {
    clearInterval(state.heartbeatInterval);
    state.heartbeatInterval = null;
  }

  state.reconnectAttempts++;
  // Exponential backoff with jitter: min(30s, 1s * 1.5^attempts) + random jitter (0-1s)
  const baseDelay = Math.min(30000, 1000 * Math.pow(1.5, state.reconnectAttempts));
  const jitter = Math.random() * 1000;
  const delay = Math.round(baseDelay + jitter);

  if (state.offlineBuffer && state.offlineBuffer.length > 0) {
    wsStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse';
    wsStatusText.textContent = `Offline (Buffering ${state.offlineBuffer.length})`;
  } else {
    wsStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse';
    wsStatusText.textContent = `Reconnecting (${state.reconnectAttempts})...`;
  }

  state.reconnectTimer = setTimeout(initWebSocket, delay);
}

// 2. Real-Time AudioContext Waveform Visualizer
function initCanvasWaveform() {
  const canvas = waveformCanvas;
  const canvasCtx = canvas.getContext('2d');
  canvas.width = canvas.parentElement.clientWidth || 320;
  canvas.height = 48;

  function drawEmpty() {
    canvasCtx.fillStyle = '#111827';
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    canvasCtx.strokeStyle = '#1f2937';
    canvasCtx.lineWidth = 1;
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, canvas.height / 2);
    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
  }
  drawEmpty();
}

async function startAudioWaveform() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    state.analyser = state.audioContext.createAnalyser();
    state.analyser.fftSize = 256;
    state.microphone = state.audioContext.createMediaStreamSource(stream);
    state.microphone.connect(state.analyser);

    const canvas = waveformCanvas;
    const canvasCtx = canvas.getContext('2d');
    const bufferLength = state.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
      if (!state.isRecording) return;
      state.animationId = requestAnimationFrame(draw);
      state.analyser.getByteTimeDomainData(dataArray);

      canvasCtx.fillStyle = '#111827';
      canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

      canvasCtx.lineWidth = 2;
      canvasCtx.strokeStyle = '#06b6d4'; // PACS Cyan
      canvasCtx.beginPath();

      const sliceWidth = canvas.width * 1.0 / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = v * (canvas.height / 2);

        if (i === 0) canvasCtx.moveTo(x, y);
        else canvasCtx.lineTo(x, y);

        x += sliceWidth;
      }

      canvasCtx.lineTo(canvas.width, canvas.height / 2);
      canvasCtx.stroke();
    }
    draw();
  } catch (err) {
    console.warn('AudioContext mic access error:', err);
  }
}

function stopAudioWaveform() {
  if (state.animationId) cancelAnimationFrame(state.animationId);
  if (state.microphone) state.microphone.disconnect();
  if (state.audioContext) state.audioContext.close();
  initCanvasWaveform();
}

// 3. Speech Recognition (Web Speech API with WebSocket Sync)
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-IN'; // Indian English medical accent tuning

  recognition.onresult = (event) => {
    let interimText = '';
    let finalChunk = '';

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalChunk += event.results[i][0].transcript + ' ';
      } else {
        interimText += event.results[i][0].transcript;
      }
    }

    if (interimText) {
      ghostText.textContent = interimText;
    }

    if (finalChunk.trim()) {
      const payload = {
        type: 'text_segment',
        text: finalChunk.trim(),
        template_id: selectTemplate.value
      };

      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(payload));
      } else {
        // Offline resilience: buffer packet and insert locally so dictation continues uninterrupted
        state.offlineBuffer.push(payload);
        insertTextAtCursor(finalChunk.trim());
        wsStatusDot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse';
        wsStatusText.textContent = `Offline (Buffering ${state.offlineBuffer.length})`;
        showToast(`Offline mode: Dictation saved locally (${state.offlineBuffer.length} queued).`);
      }
    }
  };

  recognition.onerror = (e) => {
    console.error('Recognition error:', e);
    if (e.error === 'not-allowed') {
      showToast('Microphone access denied in browser.');
      stopDictation();
    }
  };

  recognition.onend = () => {
    if (state.isRecording) {
      try { recognition.start(); } catch (e) { stopDictation(); }
    }
  };

  state.recognition = recognition;
}

// 4. Toggle Microphone Dictation
function toggleDictation() {
  if (!state.isRecording) {
    startDictation();
  } else {
    stopDictation();
  }
}

function startDictation() {
  state.isRecording = true;
  btnMicToggle.className = 'w-20 h-20 rounded-full bg-gradient-to-tr from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white flex items-center justify-center shadow-lg shadow-rose-600/30 transition-all transform active:scale-95 group relative';
  micPulseRing.classList.remove('opacity-0');
  micPulseRing.classList.add('animate-ping');
  micStatusDot.className = 'w-2 h-2 rounded-full bg-rose-500 animate-pulse';
  micStatusText.textContent = 'Recording (Live)...';
  micStatusText.className = 'text-xs font-semibold uppercase tracking-wider text-rose-400';

  // Start timer
  state.recSeconds = 0;
  clearInterval(state.recTimerInterval);
  state.recTimerInterval = setInterval(() => {
    state.recSeconds++;
    const m = String(Math.floor(state.recSeconds / 60)).padStart(2, '0');
    const s = String(state.recSeconds % 60).padStart(2, '0');
    recTimer.textContent = `${m}:${s}`;
  }, 1000);

  // Start Visualizer & Recognition
  startAudioWaveform();
  if (state.recognition) {
    try { state.recognition.start(); } catch (e) {}
  }
  showToast('Microphone live. Speak findings or voice commands.');
}

function stopDictation() {
  state.isRecording = false;
  btnMicToggle.className = 'w-20 h-20 rounded-full bg-gradient-to-tr from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white flex items-center justify-center shadow-lg shadow-cyan-500/25 transition-all transform active:scale-95 group relative';
  micPulseRing.classList.add('opacity-0');
  micPulseRing.classList.remove('animate-ping');
  micStatusDot.className = 'w-2 h-2 rounded-full bg-slate-500';
  micStatusText.textContent = 'Click to Dictate';
  micStatusText.className = 'text-xs font-semibold uppercase tracking-wider text-slate-300';

  clearInterval(state.recTimerInterval);
  stopAudioWaveform();
  if (state.recognition) {
    try { state.recognition.stop(); } catch (e) {}
  }
  ghostText.textContent = 'Listening stopped.';
}

// 5. Editor Insertion & Command Execution
function insertTextAtCursor(text) {
  richEditor.focus();
  // Check if string contains HTML tags (like <h3> or <br>)
  if (/<[a-z][\s\S]*>/i.test(text)) {
    document.execCommand('insertHTML', false, text + ' ');
  } else {
    document.execCommand('insertText', false, text + ' ');
  }
  updateWordCount();
}

function deleteLastSentence() {
  const html = richEditor.innerHTML;
  // Match the last sentence ending with a punctuation mark
  const cleaned = html.replace(/[^.!?]+[.!?]\s*$/, '');
  richEditor.innerHTML = cleaned || '<p></p>';
  showToast('Voice Command: Cleared last sentence.');
  updateWordCount();
}

function formatDoc(command, value = null) {
  document.execCommand(command, false, value);
  richEditor.focus();
}

function insertHeader(headerName) {
  richEditor.focus();
  const html = `<br><h3><strong>${headerName.toUpperCase()}:</strong></h3><p></p>`;
  document.execCommand('insertHTML', false, html);
  updateWordCount();
}

function updateWordCount() {
  const text = richEditor.innerText.trim();
  const count = text ? text.split(/\s+/).length : 0;
  wordCount.textContent = `Words: ${count}`;
}

// 6. Template Management
async function loadTemplates() {
  try {
    const res = await fetch('/api/templates');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.templates = data.starter_templates || [];
    onTemplateSelect();
  } catch (e) {
    console.error('Failed to load templates:', e);
    showToast('Failed to load clinical templates.');
  }
}

function onTemplateSelect() {
  const tid = selectTemplate.value;
  const t = state.templates.find(item => item.id === tid);
  if (!t) return;

  patientModality.value = `${t.modality} (${t.body_part})`;

  // Header metadata block if present (e.g. Radiopharmaceutical, Injected Dose, Uptake time)
  let headerHtml = '';
  if (t.header_fields && t.header_fields.length > 0) {
    headerHtml = `
<div style="background: rgba(6, 182, 212, 0.08); border-left: 3px solid #06b6d4; padding: 8px 12px; margin-bottom: 12px; border-radius: 4px;">
  <strong>EXAMINATION PARAMETERS:</strong><br>
  ${t.header_fields.map(f => `<span style="display:inline-block; margin-right: 14px; font-size: 11px;">• ${escapeHtml(f)}</span>`).join('')}
</div>
`;
  }

  // Quantitative table for renal / cardiac / thyroid if applicable
  let quantTableHtml = '';
  if (tid.includes('renal_dtpa') || tid.includes('renal_dmsa')) {
    quantTableHtml = `
<table style="width:100%; border-collapse: collapse; margin: 10px 0; font-size: 11px; border: 1px solid #374151;">
  <tr style="background:#1f2937; color:#38bdf8;">
    <th style="padding:6px; border:1px solid #374151;">Parameter</th>
    <th style="padding:6px; border:1px solid #374151;">Left Kidney</th>
    <th style="padding:6px; border:1px solid #374151;">Right Kidney</th>
    <th style="padding:6px; border:1px solid #374151;">Reference Normal</th>
  </tr>
  <tr>
    <td style="padding:6px; border:1px solid #374151;">Split Renal Function (%)</td>
    <td style="padding:6px; border:1px solid #374151;">51%</td>
    <td style="padding:6px; border:1px solid #374151;">49%</td>
    <td style="padding:6px; border:1px solid #374151;">45% - 55%</td>
  </tr>
  <tr>
    <td style="padding:6px; border:1px solid #374151;">GFR (mL/min)</td>
    <td style="padding:6px; border:1px solid #374151;">48 mL/min</td>
    <td style="padding:6px; border:1px solid #374151;">46 mL/min</td>
    <td style="padding:6px; border:1px solid #374151;">Total > 80 mL/min</td>
  </tr>
</table>
`;
  } else if (tid.includes('cardiac_perfusion')) {
    quantTableHtml = `
<table style="width:100%; border-collapse: collapse; margin: 10px 0; font-size: 11px; border: 1px solid #374151;">
  <tr style="background:#1f2937; color:#38bdf8;">
    <th style="padding:6px; border:1px solid #374151;">Parameter</th>
    <th style="padding:6px; border:1px solid #374151;">Calculated Value</th>
    <th style="padding:6px; border:1px solid #374151;">Reference Normal</th>
  </tr>
  <tr>
    <td style="padding:6px; border:1px solid #374151;">LVEF (Rest / Post-Stress)</td>
    <td style="padding:6px; border:1px solid #374151;">60%</td>
    <td style="padding:6px; border:1px solid #374151;">≥ 50%</td>
  </tr>
  <tr>
    <td style="padding:6px; border:1px solid #374151;">Summed Stress Score (SSS)</td>
    <td style="padding:6px; border:1px solid #374151;">0 (Normal)</td>
    <td style="padding:6px; border:1px solid #374151;">< 4</td>
  </tr>
</table>
`;
  }

  // Build clean starter layout
  richEditor.innerHTML = `
<h3><strong>EXAMINATION:</strong></h3>
<p>${t.title}</p>

${headerHtml}

<h3><strong>TECHNIQUE:</strong></h3>
<p>${t.technique}</p>

<h3><strong>CLINICAL INDICATION:</strong></h3>
<p>${t.indication_default}</p>

<h3><strong>COMPARISON:</strong></h3>
<p>${t.comparison_default}</p>

<h3><strong>FINDINGS:</strong></h3>
${quantTableHtml}
<p>[Dictate or click AI Auto-Format to populate specific observations]</p>

<h3><strong>IMPRESSION:</strong></h3>
<p>[Draft pending review]</p>
`;
  updateWordCount();
}

// 7. AI Auto-Format (POST /api/format-report via Gemini / Fallback Engine)
async function triggerAIStructuring() {
  const rawText = richEditor.innerText.trim();
  if (!rawText) {
    showToast('Editor is empty. Dictate some findings first.');
    return;
  }

  // Strip placeholders before checking if meaningful findings were entered
  const strippedText = rawText
    .replace(/\[Dictate or click AI Auto-Format to populate specific observations\]/gi, '')
    .replace(/\[Draft pending review\]/gi, '')
    .replace(/\[No specific findings dictated\]/gi, '')
    .replace(/\[Normal study summary\]/gi, '')
    .trim();

  // Check if findings section has content beyond template headers
  const tid = selectTemplate.value;
  const t = state.templates.find(item => item.id === tid);
  let hasUserContent = false;
  if (t) {
    let checkText = strippedText;
    if (t.title) checkText = checkText.replace(t.title, '');
    if (t.technique) checkText = checkText.replace(t.technique, '');
    if (t.indication_default) checkText = checkText.replace(t.indication_default, '');
    if (t.comparison_default) checkText = checkText.replace(t.comparison_default, '');
    checkText = checkText.replace(/EXAMINATION:|TECHNIQUE:|CLINICAL INDICATION:|COMPARISON:|FINDINGS:|IMPRESSION:|EXAMINATION PARAMETERS:/gi, '').trim();
    hasUserContent = checkText.length > 5;
  } else {
    hasUserContent = strippedText.length > 15;
  }

  if (!hasUserContent) {
    showToast('Please dictate or type findings first before running AI Auto-Format.');
    return;
  }

  showToast('✨ AI structuring report via Gemini...');

  try {
    const res = await fetch('/api/format-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dictation_text: rawText,
        template_id: selectTemplate.value
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'AI auto-formatting failed.');
      return;
    }

    const data = await res.json();
    const s = data.sections || {};

    // Render formatted sections in rich editor (5 Core Handbook Sections)
    richEditor.innerHTML = `
<h3><strong>EXAMINATION:</strong></h3>
<p>${escapeHtml(s.examination || '')}</p>

<h3><strong>CLINICAL INDICATION:</strong></h3>
<p>${escapeHtml(s.clinical_indication || s.indication || '')}</p>

<h3><strong>PROCEDURE / TECHNIQUE:</strong></h3>
<p>${escapeHtml(s.procedure_technique || s.technique || '')}</p>

<h3><strong>FINDINGS:</strong></h3>
<p>${s.findings ? s.findings.replace(/\n/g, '<br>') : '[No specific findings dictated]'}</p>

<h3><strong>IMPRESSION:</strong></h3>
<p>${s.impression ? s.impression.replace(/\n/g, '<br>') : '[Normal study summary]'}</p>

<h3><strong>LIMITATIONS / ADDITIONAL NOTES:</strong></h3>
<p>${escapeHtml(s.limitations_additional_notes || s.comparison || 'No technical motion artefact described.')}</p>
`;
    updateWordCount();

    if (data.quality_flags || data.uncertain_terms) {
      renderSafetyFlags(data.quality_flags, data.uncertain_terms, data.split_function_check);
    }

    showToast(`✨ Report structured into 5 standard sections (${data.engine_used || 'safety engine'})!`);
  } catch (err) {
    console.error('AI formatting failed:', err);
    showToast('Error running AI auto-formatter.');
  }
}

// 8. Copy to Clipboard for Hospital RIS/PACS
function copyReportText() {
  const text = richEditor.innerText;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Full report copied to clipboard for RIS/PACS!');
  }).catch(() => {
    showToast('Failed to copy to clipboard.');
  });
}

// 9. Save Draft to SQLite
async function saveReportDraft() {
  const payload = {
    id: state.currentReportId,
    patient_name: patientName.value,
    patient_uhid: patientUHID.value,
    patient_age_sex: patientAgeSex.value,
    modality: selectTemplate.value.split('_')[0].toUpperCase(),
    body_part: selectTemplate.value,
    template_id: selectTemplate.value,
    examination: selectTemplate.options[selectTemplate.selectedIndex].text,
    full_report: richEditor.innerText,
    status: 'VERIFIED_DRAFT'
  };

  try {
    const res = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'Failed to save report.');
      return;
    }
    const d = await res.json();
    state.currentReportId = d.report_id;
    showToast(`Report #${d.report_id} saved securely to SQLite!`);
  } catch (e) {
    showToast('Failed to save report.');
  }
}

// 10. Handle Audio File Upload
async function handleAudioUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  document.getElementById('uploadFileName').textContent = file.name;
  showToast(`Uploading ${file.name} for medical speech transcription...`);

  const formData = new FormData();
  formData.append('file', file);
  formData.append('template_id', selectTemplate.value);
  formData.append('stt_mode', state.sttMode || 'dual');

  try {
    const res = await fetch('/api/transcribe-audio', {
      method: 'POST',
      body: formData
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      showToast(data.detail || data.message || 'Audio file transcription failed.');
      return;
    }
    if (data.transcription) {
      insertTextAtCursor(data.transcription);
      showToast('Audio file transcribed with medical vocabulary booster!');
    }
    if (data.corrections_applied && data.corrections_applied.length > 0) {
      renderCorrectionsInFeed(data.corrections_applied);
    }
    if (data.quality_flags || data.uncertain_terms) {
      renderSafetyFlags(data.quality_flags, data.uncertain_terms, data.split_function_check);
    }
  } catch (err) {
    showToast('Failed to process audio file.');
  }
}

function clearEditor() {
  if (confirm('Clear the entire report editor?')) {
    richEditor.innerHTML = '<p></p>';
    updateWordCount();
    showToast('Editor cleared.');
  }
}

function showToast(msg) {
  toastNotification.textContent = msg;
  toastNotification.classList.remove('opacity-0', 'pointer-events-none', 'translate-y-3');
  setTimeout(() => {
    toastNotification.classList.add('opacity-0', 'pointer-events-none', 'translate-y-3');
  }, 3500);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ==========================================
// LAYER 3: DOCTOR'S TRAIN VOCABULARY MODULE
// ==========================================

const trainVocabDrawer = document.getElementById('trainVocabDrawer');
const trainCorrectTerm = document.getElementById('trainCorrectTerm');
const trainMisheardTerm = document.getElementById('trainMisheardTerm');
const trainModality = document.getElementById('trainModality');
const trainedWordsList = document.getElementById('trainedWordsList');
const trainedWordsCount = document.getElementById('trainedWordsCount');

function toggleTrainVocabDrawer() {
  if (trainVocabDrawer.classList.contains('translate-x-full')) {
    trainVocabDrawer.classList.remove('translate-x-full');
    loadTrainedWords();
  } else {
    trainVocabDrawer.classList.add('translate-x-full');
  }
}

async function loadTrainedWords() {
  try {
    const res = await fetch('/api/trained-words');
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'Failed to load trained words.');
      return;
    }
    const data = await res.json();
    const words = data.trained_words || [];
    trainedWordsCount.textContent = `${words.length} terms`;

    if (words.length === 0) {
      trainedWordsList.innerHTML = `<p class="text-slate-500 italic">No custom words trained yet. Add your first word above.</p>`;
      return;
    }

    trainedWordsList.innerHTML = words.map(w => `
      <div class="bg-pacs-950 border border-pacs-800 rounded-lg p-2.5 flex items-center justify-between">
        <div>
          <span class="font-bold text-cyan-400 block">${escapeHtml(w.term)}</span>
          ${w.misheard ? `<span class="text-[10px] text-amber-400 block font-mono">Misheard as: "${escapeHtml(w.misheard)}"</span>` : ''}
          <span class="text-[9px] text-slate-500 block uppercase font-semibold">${escapeHtml(w.modality || 'all')}</span>
        </div>
        <button onclick="deleteTrainedWord('${escapeHtml(w.term)}')" class="text-rose-400 hover:text-rose-300 p-1 text-xs" title="Delete word">
          ✕
        </button>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load trained words:', err);
    showToast('Failed to load trained words.');
  }
}

async function submitTrainWord() {
  const term = trainCorrectTerm.value.trim();
  const misheard = trainMisheardTerm.value.trim();
  const modality = trainModality.value;

  if (!term) {
    showToast('Please enter the correct medical term.');
    return;
  }

  try {
    const res = await fetch('/api/train-word', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term, misheard, modality })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'Failed to train word.');
      return;
    }
    const data = await res.json();
    showToast(`🎯 Trained: "${term}" added to active vocabulary!`);
    trainCorrectTerm.value = '';
    trainMisheardTerm.value = '';
    loadTrainedWords();
  } catch (e) {
    showToast('Error saving custom word.');
  }
}

async function deleteTrainedWord(term) {
  try {
    const res = await fetch('/api/trained-words', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'Failed to delete word.');
      return;
    }
    showToast(`Removed "${term}" from vocabulary.`);
    loadTrainedWords();
  } catch (e) {
    showToast('Failed to delete word.');
  }
}

// Speak directly to capture misheard pronunciation
function recordMisheardSample() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast('Speech recognition not supported in this browser.');
    return;
  }
  const btn = document.getElementById('btnRecordMisheard');
  btn.textContent = '🔴';
  showToast('Speak the word now into the mic...');

  const tempRec = new SpeechRecognition();
  tempRec.lang = 'en-IN';
  tempRec.interimResults = false;
  tempRec.maxAlternatives = 1;

  tempRec.onresult = (event) => {
    const spoken = event.results[0][0].transcript;
    trainMisheardTerm.value = spoken.trim();
    showToast(`Captured phonetic sound: "${spoken}"`);
    btn.textContent = '🎤';
  };
  tempRec.onerror = () => {
    btn.textContent = '🎤';
  };
  tempRec.onend = () => {
    btn.textContent = '🎤';
  };
  tempRec.start();
}

// ==========================================
// LIVE CORRECTION LOG FEED & QUICK RULES
// ==========================================

function renderCorrectionsInFeed(corrections) {
  const feed = document.getElementById('correctionLogFeed');
  if (!feed) return;

  // Clear placeholder text if present
  if (feed.querySelector('p')) {
    feed.innerHTML = '';
  }

  corrections.forEach(c => {
    const fromTerm = c.from || c.original || '';
    const toTerm = c.to || c.corrected || '';
    const stage = c.stage || 'Pass-1 Phonetic';
    if (!fromTerm || !toTerm || fromTerm.toLowerCase() === toTerm.toLowerCase()) return;

    const item = document.createElement('div');
    item.className = 'py-1 px-1.5 rounded bg-pacs-900 border border-cyan-900/60 flex items-center justify-between text-[10px] animate-pulse';
    item.innerHTML = `
      <span>⚡ <span class="text-rose-400 line-through">${escapeHtml(fromTerm)}</span> → <strong class="text-emerald-400">${escapeHtml(toTerm)}</strong></span>
      <span class="text-[8px] text-cyan-400/80 font-mono">${escapeHtml(stage)}</span>
    `;
    feed.insertBefore(item, feed.firstChild);

    // Keep feed trimmed to 25 entries
    while (feed.children.length > 25) {
      feed.removeChild(feed.lastChild);
    }
  });
}

function clearCorrectionFeed() {
  const feed = document.getElementById('correctionLogFeed');
  if (feed) {
    feed.innerHTML = '<p class="text-slate-600 italic text-[10px]">Listening for medical speech...</p>';
  }
}

async function submitQuickCustomRule() {
  const patInput = document.getElementById('quickRulePattern');
  const repInput = document.getElementById('quickRuleReplacement');
  const pattern = patInput.value.trim();
  const replacement = repInput.value.trim();

  if (!pattern || !replacement) {
    showToast('Please provide both the misheard pattern and the correct spelling.');
    return;
  }

  try {
    const res = await fetch('/api/custom-rule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern, replacement, category: 'Quick Rule' })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      showToast(errData.detail || 'Failed to save pronunciation rule.');
      return;
    }
    const d = await res.json();
    showToast(`⚡ Instant rule saved: "${pattern}" → "${replacement}"!`);
    patInput.value = '';
    repInput.value = '';
  } catch (err) {
    showToast('Failed to save pronunciation rule.');
  }
}

// 10. Clinical Safety & Uncertainty Flags Renderer (Handbook Boundaries)
function renderSafetyFlags(qualityFlags, uncertainTerms, splitCheck) {
  const container = document.getElementById('safetyFlagsContainer');
  const list = document.getElementById('safetyBadgesList');
  if (!container || !list) return;

  const allFlags = qualityFlags || [];
  const allTerms = uncertainTerms || [];

  if (allFlags.length === 0 && allTerms.length === 0 && !splitCheck) {
    return;
  }

  list.innerHTML = '';
  let count = 0;

  // Render Renal Split Quality Check if present
  if (splitCheck) {
    count++;
    const badge = document.createElement('span');
    badge.className = splitCheck.is_balanced
      ? 'px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800'
      : 'px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 animate-pulse';
    badge.innerHTML = `⚖️ Renal Split: Right=${splitCheck.right_pct}%, Left=${splitCheck.left_pct}% (Sum: ${splitCheck.total_sum}%)`;
    badge.title = splitCheck.message;
    list.appendChild(badge);
  }

  // Render Quality Flags
  allFlags.forEach(f => {
    count++;
    const badge = document.createElement('span');
    let bgStyle = 'bg-slate-800 text-slate-300 border-slate-700';

    if (f.severity === 'CRITICAL_ALERT') {
      bgStyle = 'bg-rose-950 text-rose-300 border-rose-800 animate-pulse font-bold';
    } else if (f.severity === 'WARNING') {
      bgStyle = 'bg-amber-950 text-amber-300 border-amber-800 font-semibold';
    } else if (f.type === 'LATERALITY_CONFIRMED') {
      bgStyle = 'bg-cyan-950 text-cyan-300 border-cyan-800';
    } else if (f.type === 'NEGATION_POLARITY_GUARD') {
      bgStyle = 'bg-indigo-950 text-indigo-300 border-indigo-800';
    } else if (f.type === 'ACTIVITY_UNIT_CHECK') {
      bgStyle = 'bg-purple-950 text-purple-300 border-purple-800';
    }

    badge.className = `px-2 py-0.5 rounded border text-[10px] ${bgStyle} cursor-help`;
    const label = f.pair || f.message || f.term || (f.units_detected ? f.units_detected.join(', ') : f.type);
    badge.textContent = `⚠️ ${label}`;
    badge.title = f.guidance || f.message || 'Clinical safety guardrail active';
    list.appendChild(badge);
  });

  if (count > 0) {
    container.classList.remove('hidden');
  }
}

function dismissSafetyFlags() {
  const container = document.getElementById('safetyFlagsContainer');
  if (container) {
    container.classList.add('hidden');
  }
}

// 11. Nuclear Medicine Terminology Handbook Modal Controller
let handbookDataCache = null;
let currentHandbookTab = 'pet_ct';

async function openHandbookModal() {
  const modal = document.getElementById('handbookModal');
  if (!modal) return;
  modal.classList.remove('hidden');

  if (!handbookDataCache) {
    try {
      const res = await fetch('/api/handbook/vocabulary');
      handbookDataCache = await res.json();
    } catch (e) {
      document.getElementById('handbookContentArea').innerHTML = '<p class="text-rose-400">Failed to load handbook vocabulary.</p>';
      return;
    }
  }
  switchHandbookTab(currentHandbookTab);
}

function closeHandbookModal() {
  const modal = document.getElementById('handbookModal');
  if (modal) modal.classList.add('hidden');
}

function switchHandbookTab(tabKey) {
  currentHandbookTab = tabKey;
  const tabIds = ['pet_ct', 'gamma_camera_spect', 'therapeutic_theranostics', 'high_risk_confusables', 'abbreviations_and_units'];
  tabIds.forEach(id => {
    const btn = document.getElementById(`tab_${id}`);
    if (btn) {
      if (id === tabKey) {
        btn.className = 'px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-800';
      } else {
        btn.className = 'px-3 py-1.5 rounded-lg text-slate-400 hover:text-white';
      }
    }
  });
  renderHandbookTerms();
}

function renderHandbookTerms(filterQuery = '') {
  const container = document.getElementById('handbookContentArea');
  if (!container || !handbookDataCache) return;

  const q = filterQuery.toLowerCase();
  const items = handbookDataCache.sections[currentHandbookTab] || [];

  if (currentHandbookTab === 'high_risk_confusables') {
    const filtered = items.filter(i => !q || i.pair.toLowerCase().includes(q) || i.danger_type.toLowerCase().includes(q) || i.safe_usage_guidance.toLowerCase().includes(q));
    container.innerHTML = `
      <div class="grid grid-cols-1 gap-3">
        ${filtered.map(item => `
          <div class="bg-pacs-950 border border-amber-900/60 rounded-xl p-3 flex flex-col gap-1.5">
            <div class="flex items-center justify-between">
              <span class="font-bold text-amber-400 text-sm font-mono">⚠️ ${escapeHtml(item.pair)}</span>
              <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800">${escapeHtml(item.category)}</span>
            </div>
            <p class="text-xs text-rose-300 font-medium">Danger: ${escapeHtml(item.danger_type)}</p>
            <p class="text-[11px] text-slate-300 bg-slate-900/60 p-2 rounded border border-slate-800">🛡️ <strong>Safety Guidance:</strong> ${escapeHtml(item.safe_usage_guidance)}</p>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  if (currentHandbookTab === 'abbreviations_and_units') {
    const filtered = items.filter(i => !q || i.abbreviation.toLowerCase().includes(q) || i.expansion.toLowerCase().includes(q));
    container.innerHTML = `
      <div class="grid grid-cols-2 gap-2">
        ${filtered.map(item => `
          <div class="bg-pacs-950 border border-pacs-800 rounded-lg p-2.5 flex flex-col gap-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-cyan-400 font-mono text-xs">${escapeHtml(item.abbreviation)}</span>
              <span class="text-[10px] text-slate-400">${escapeHtml(item.expansion)}</span>
            </div>
            <p class="text-[10px] text-slate-400">${escapeHtml(item.usage_note)}</p>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  // Standard terms tabs (pet_ct, gamma_camera_spect, therapeutic_theranostics)
  const filtered = items.filter(i => !q || i.term.toLowerCase().includes(q) || i.definition.toLowerCase().includes(q) || (i.sound_alikes && i.sound_alikes.join(' ').toLowerCase().includes(q)));

  container.innerHTML = `
    <div class="grid grid-cols-1 gap-2.5">
      ${filtered.map(item => `
        <div class="bg-pacs-950 border border-pacs-800 rounded-xl p-3 flex flex-col gap-1 hover:border-cyan-800/80 transition">
          <div class="flex items-center justify-between">
            <span class="font-bold text-white text-xs">${escapeHtml(item.term)}</span>
            <span class="text-[9px] uppercase font-mono px-2 py-0.5 rounded bg-pacs-900 text-cyan-400 border border-pacs-800">${escapeHtml(item.category)}</span>
          </div>
          <p class="text-[11px] text-slate-300">${escapeHtml(item.definition)}</p>
          ${item.safe_usage ? `<p class="text-[10px] text-emerald-400/90 font-mono"><strong>Safe Usage:</strong> ${escapeHtml(item.safe_usage)}</p>` : ''}
          ${item.sound_alikes ? `<p class="text-[9px] text-slate-500 font-mono">ASR Variants: ${escapeHtml(item.sound_alikes.join(', '))}</p>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

function filterHandbookTerms() {
  const input = document.getElementById('handbookSearch');
  if (input) {
    renderHandbookTerms(input.value);
  }
}
