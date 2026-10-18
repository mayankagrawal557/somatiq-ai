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
  sttMode: 'dual',
  patientSummaries: { en: '', hinglish: '' },
  currentSummaryLang: 'en',
  letterheadConfig: {
    preprinted_letterhead: false,
    top_margin_mm: 45,
    bottom_margin_mm: 30,
    include_summary_page2: false
  },
  currentEditFocusIndex: -1,
  lastSuggestedImpression: null,
  collaboratorLoading: false,
  worklistQueue: [],
  activeStudyId: null,
  currentWorklistFilter: 'ALL',
  isWorklistDrawerOpen: false,
  activeWhatsAppStudy: null
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
  initLetterheadSettings();

  // STEP 3: Live Worklist & SLA Timers
  fetchWorklistQueue();
  setInterval(updateAllSLATimers, 1000);
  setInterval(fetchWorklistQueue, 15000);
  populateNewPatientTemplates();
  
  // Word count & AI diff highlight tracker
  richEditor.addEventListener('input', () => {
    updateWordCount();
    updatePendingEditsCount();
  });

  // Clinical history two-way synchronization
  const clinicalHistInput = document.getElementById('clinicalHistory');
  const collabHistInput = document.getElementById('collabClinicalHistoryInput');
  if (clinicalHistInput) {
    clinicalHistInput.addEventListener('input', () => {
      if (collabHistInput) collabHistInput.value = clinicalHistInput.value;
    });
  }
  if (collabHistInput) {
    collabHistInput.addEventListener('input', () => {
      if (clinicalHistInput) clinicalHistInput.value = collabHistInput.value;
    });
  }

  // Global & Editor Keyboard Shortcuts (Alt+S, Alt+C, Alt+W, Ctrl+Shift+C, Ctrl+Shift+S, Ctrl+Enter, Tab)
  window.addEventListener('keydown', (e) => {
    // 1. One-Shot Smart AI Merge: Alt + S
    if (e.altKey && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      triggerSmartAIMerge();
      return;
    }

    // 2. RadOne AI Clinical Collaborator: Alt + C
    if (e.altKey && (e.key === 'c' || e.key === 'C')) {
      e.preventDefault();
      toggleCollaboratorDrawer();
      return;
    }

    // 3. Live Teleradiology Worklist: Alt + W
    if (e.altKey && (e.key === 'w' || e.key === 'W')) {
      e.preventDefault();
      toggleWorklistDrawer();
      return;
    }

    // 4. 1-Click Clean Copy for RIS / PACS / Word: Ctrl + Shift + C
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'c' || e.key === 'C')) {
      e.preventDefault();
      copyCleanReportForRIS();
      return;
    }

    // 5. Approve, Sign & Auto-Advance to Next Patient: Ctrl + Shift + S
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      signAndAutoAdvance();
      return;
    }

    // 6. Accept All AI Edits: Ctrl + Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      const marks = richEditor.querySelectorAll('mark');
      if (marks.length > 0) {
        e.preventDefault();
        acceptAllEdits();
        return;
      }
    }

    // 7. Next AI Edit Navigation: Tab
    if (e.key === 'Tab' && !e.shiftKey) {
      const marks = richEditor.querySelectorAll('mark');
      if (marks.length > 0 && (document.activeElement === richEditor || richEditor.contains(document.activeElement))) {
        e.preventDefault();
        focusNextEdit();
        return;
      }
    }
  });

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

  const clinicalHistInput = document.getElementById('clinicalHistory');
  const collabHistInput = document.getElementById('collabClinicalHistoryInput');
  if (clinicalHistInput) clinicalHistInput.value = t.indication_default || '';
  if (collabHistInput) collabHistInput.value = t.indication_default || '';

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

// 8. 1-Click Clean Copy to Any Hospital RIS / PACS / Word (Ctrl + Shift + C)
async function copyCleanReportForRIS() {
  if (!richEditor) return;

  // 1. Clone editor DOM node to sanitize without mutating live editor view
  const clone = richEditor.cloneNode(true);

  // 2. Unwrap all <mark> tags (ai-diff-highlight, phonetic-diff-highlight, etc.) keeping clean text
  const marks = clone.querySelectorAll('mark');
  marks.forEach(mark => {
    mark.replaceWith(...mark.childNodes);
  });

  // 3. Strip all dark PACS styling classes, IDs, and custom attributes
  const elements = clone.querySelectorAll('*');
  elements.forEach(el => {
    el.removeAttribute('class');
    el.removeAttribute('id');
    el.removeAttribute('contenteditable');
    el.removeAttribute('style');
    if (el.tagName === 'STRONG' || el.tagName === 'B') {
      el.style.fontWeight = 'bold';
      el.style.color = '#000000';
    } else if (el.tagName === 'P' || el.tagName === 'DIV') {
      el.style.margin = '0 0 6px 0';
      el.style.lineHeight = '1.4';
      el.style.color = '#000000';
    }
  });

  // 4. Wrap with universal hospital inline CSS (Arial 11pt, #000000)
  const universalHtml = `<div style="font-family: Arial, Helvetica, sans-serif; font-size: 11pt; color: #000000; line-height: 1.4; background-color: #ffffff;">${clone.innerHTML}</div>`;

  // 5. Clean plain text with uppercase section headers and clean line breaks
  const cleanPlainText = (clone.innerText || clone.textContent || '').trim();

  // 6. Write simultaneously to Clipboard: text/html AND text/plain
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      const blobHtml = new Blob([universalHtml], { type: 'text/html' });
      const blobText = new Blob([cleanPlainText], { type: 'text/plain' });
      const clipboardItem = new ClipboardItem({
        'text/html': blobHtml,
        'text/plain': blobText
      });
      await navigator.clipboard.write([clipboardItem]);
      showToast('📋 Clean Report Copied for RIS / PACS / Word!');
      return;
    }
  } catch (err) {
    console.warn('ClipboardItem HTML write error, falling back to plain text:', err);
  }

  // Graceful fallback for non-ClipboardItem environments
  try {
    await navigator.clipboard.writeText(cleanPlainText);
    showToast('📋 Clean report copied to clipboard for RIS/PACS!');
  } catch (err) {
    showToast('❌ Failed to copy to clipboard.');
  }
}

// Backward-compatible alias
function copyReportText() {
  copyCleanReportForRIS();
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
    const collabDrawer = document.getElementById('collaboratorDrawer');
    if (collabDrawer) collabDrawer.classList.add('translate-x-full');
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

// =========================================================================
// UPGRADE 2: "One-Shot" Smart AI Structuring Mode (Alt + S)
// =========================================================================
async function triggerSmartAIMerge() {
  const rawDictation = richEditor.innerText.trim();
  if (!rawDictation) {
    showToast('Please dictate or type findings first before running Smart AI Merge.');
    return;
  }

  const btnLeft = document.getElementById('btnSmartMerge');
  const btnToolbar = document.getElementById('btnSmartMergeToolbar');
  const spinnerLeft = document.getElementById('smartMergeSpinner');
  const spinnerToolbar = document.getElementById('smartMergeToolbarSpinner');
  const iconLeft = document.getElementById('smartMergeIcon');

  // Activate loading spinners
  if (spinnerLeft) spinnerLeft.classList.remove('hidden');
  if (spinnerToolbar) spinnerToolbar.classList.remove('hidden');
  if (iconLeft) iconLeft.classList.add('hidden');
  if (btnLeft) btnLeft.disabled = true;
  if (btnToolbar) btnToolbar.disabled = true;

  showToast('✨ Surgically merging dictation into template (Alt+S)...');

  try {
    const payload = {
      template_key: selectTemplate ? selectTemplate.value : 'ct_brain',
      current_template_html: richEditor.innerHTML,
      raw_dictation: rawDictation,
      patient_age_gender: patientAgeSex ? patientAgeSex.value : '45Y / M',
      modality: patientModality ? patientModality.value : 'CT'
    };

    const res = await fetch('/api/smart-structure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Smart AI merge failed.');
      return;
    }

    const data = await res.json();
    if (data.merged_report_html) {
      richEditor.innerHTML = data.merged_report_html;
    }

    // Patient summary storage & presentation
    state.patientSummaries.en = data.patient_summary_en || '';
    state.patientSummaries.hinglish = data.patient_summary_hinglish || '';
    state.currentSummaryLang = 'en';

    const summaryContainer = document.getElementById('patientSummaryContainer');
    const summaryText = document.getElementById('patientSummaryText');
    const printSummaryText = document.getElementById('printPage2SummaryText');

    if (summaryContainer && summaryText && data.patient_summary_en) {
      summaryText.textContent = data.patient_summary_en;
      summaryContainer.classList.remove('hidden');
      if (printSummaryText) {
        printSummaryText.textContent = data.patient_summary_en;
      }
    }

    updateWordCount();
    updatePendingEditsCount();

    if (data.gender_pruned && data.gender_pruned.length > 0) {
      showToast(`✨ Smart Merge complete! Biological pruning applied for: ${data.gender_pruned.join(', ')}.`);
    } else {
      showToast(`✨ Smart Merge complete! Verified with ${data.engine || 'Gemini 2.5 Flash'}.`);
    }

  } catch (err) {
    console.error('Smart AI Merge failed:', err);
    showToast('Error during Smart AI merge.');
  } finally {
    if (spinnerLeft) spinnerLeft.classList.add('hidden');
    if (spinnerToolbar) spinnerToolbar.classList.add('hidden');
    if (iconLeft) iconLeft.classList.remove('hidden');
    if (btnLeft) btnLeft.disabled = false;
    if (btnToolbar) btnToolbar.disabled = false;
  }
}

function togglePatientSummaryCard() {
  const body = document.getElementById('patientSummaryBody');
  const icon = document.getElementById('summaryToggleIcon');
  if (body) {
    body.classList.toggle('hidden');
    if (icon) {
      icon.style.transform = body.classList.contains('hidden') ? 'rotate(-90deg)' : 'rotate(0deg)';
    }
  }
}

function switchPatientSummaryLang(lang) {
  state.currentSummaryLang = lang;
  const btnEn = document.getElementById('btnLangEn');
  const btnHinglish = document.getElementById('btnLangHinglish');
  const summaryText = document.getElementById('patientSummaryText');

  if (lang === 'hinglish') {
    if (btnHinglish) btnHinglish.className = 'px-2 py-0.5 rounded bg-emerald-600 text-white font-bold transition';
    if (btnEn) btnEn.className = 'px-2 py-0.5 rounded text-slate-400 hover:text-white transition';
    if (summaryText) summaryText.textContent = state.patientSummaries.hinglish || state.patientSummaries.en;
  } else {
    if (btnEn) btnEn.className = 'px-2 py-0.5 rounded bg-emerald-600 text-white font-bold transition';
    if (btnHinglish) btnHinglish.className = 'px-2 py-0.5 rounded text-slate-400 hover:text-white transition';
    if (summaryText) summaryText.textContent = state.patientSummaries.en;
  }
}

function copyPatientSummary(e) {
  if (e) e.stopPropagation();
  const summaryText = document.getElementById('patientSummaryText');
  if (!summaryText) return;
  navigator.clipboard.writeText(summaryText.textContent).then(() => {
    showToast('Patient summary copied to clipboard!');
  }).catch(() => {
    showToast('Failed to copy patient summary.');
  });
}

// =========================================================================
// UPGRADE 3: Visual AI Diff Highlighting & Keyboard Sign-Off Workflow
// =========================================================================
function updatePendingEditsCount() {
  const marks = richEditor.querySelectorAll('mark.ai-diff-highlight, mark.phonetic-diff-highlight, mark');
  const count = marks.length;
  const countBadge = document.getElementById('aiEditsPendingBadge');
  const countSpan = document.getElementById('pendingEditsCount');
  const btnNext = document.getElementById('btnNextEdit');
  const btnAccept = document.getElementById('btnAcceptAllEdits');
  const verifiedBadge = document.getElementById('clinicianVerifiedBadge');
  const container = document.getElementById('safetyFlagsContainer');

  if (count > 0) {
    if (container) container.classList.remove('hidden');
    if (countBadge) countBadge.classList.remove('hidden');
    if (countSpan) countSpan.textContent = count;
    if (btnNext) btnNext.classList.remove('hidden');
    if (btnAccept) btnAccept.classList.remove('hidden');
    if (verifiedBadge) verifiedBadge.classList.add('hidden');
  } else {
    if (countBadge) countBadge.classList.add('hidden');
    if (btnNext) btnNext.classList.add('hidden');
    if (btnAccept) btnAccept.classList.add('hidden');
    // If editor has content and no marks remain, show verified
    if (richEditor.innerText.trim().length > 50 && verifiedBadge) {
      verifiedBadge.classList.remove('hidden');
    }
  }
}

function focusNextEdit() {
  const marks = richEditor.querySelectorAll('mark.ai-diff-highlight, mark.phonetic-diff-highlight, mark');
  if (!marks || marks.length === 0) {
    showToast('No highlighted AI edits remaining.');
    return;
  }

  // Remove previous focus highlight
  marks.forEach(m => m.classList.remove('current-focus'));

  state.currentEditFocusIndex = (state.currentEditFocusIndex + 1) % marks.length;
  const current = marks[state.currentEditFocusIndex];
  current.classList.add('current-focus');
  current.scrollIntoView({ behavior: 'smooth', block: 'center' });

  // Move selection / caret inside current mark
  try {
    const range = document.createRange();
    const sel = window.getSelection();
    range.selectNodeContents(current);
    sel.removeAllRanges();
    sel.addRange(range);
  } catch (e) {
    current.focus();
  }

  showToast(`Navigated to AI edit ${state.currentEditFocusIndex + 1} of ${marks.length}`);
}

function acceptAllEdits() {
  const marks = richEditor.querySelectorAll('mark.ai-diff-highlight, mark.phonetic-diff-highlight, mark');
  const count = marks.length;
  if (count === 0) {
    showToast('No pending AI edits to accept.');
    return;
  }

  // Cleanly unwrap all <mark> tags preserving inner text
  marks.forEach(mark => {
    mark.replaceWith(...mark.childNodes);
  });

  state.currentEditFocusIndex = -1;
  updatePendingEditsCount();

  const verifiedBadge = document.getElementById('clinicianVerifiedBadge');
  if (verifiedBadge) verifiedBadge.classList.remove('hidden');

  showToast(`✅ Accepted and verified ${count} AI edits (Verified by Clinician).`);
}

function handlePrintRequest() {
  const marks = richEditor.querySelectorAll('mark.ai-diff-highlight, mark.phonetic-diff-highlight, mark');
  if (marks && marks.length > 0) {
    const modal = document.getElementById('unverifiedEditsModal');
    const modalCount = document.getElementById('modalUnverifiedCount');
    if (modalCount) modalCount.textContent = marks.length;
    if (modal) modal.classList.remove('hidden');
  } else {
    executePrint();
  }
}

function closeUnverifiedEditsModal() {
  const modal = document.getElementById('unverifiedEditsModal');
  if (modal) modal.classList.add('hidden');
}

function acceptEditsAndPrint() {
  acceptAllEdits();
  closeUnverifiedEditsModal();
  setTimeout(() => {
    executePrint();
  }, 100);
}

function executePrint() {
  applyLetterheadPrintStyles();
  window.print();
}

// =========================================================================
// UPGRADE 4: Hospital Pre-Printed Letterhead Calibration Engine
// =========================================================================
async function initLetterheadSettings() {
  // Load local settings first
  try {
    const stored = localStorage.getItem('somatiq_letterhead_settings');
    if (stored) {
      state.letterheadConfig = Object.assign(state.letterheadConfig, JSON.parse(stored));
    }
  } catch (e) {
    console.warn('LocalStorage letterhead load error:', e);
  }

  // Sync with backend API
  try {
    const res = await fetch('/api/letterhead-settings');
    if (res.ok) {
      const data = await res.json();
      if (data) {
        state.letterheadConfig.preprinted_letterhead = Boolean(data.preprinted_letterhead);
        state.letterheadConfig.top_margin_mm = Number(data.top_margin_mm) || 45;
        state.letterheadConfig.bottom_margin_mm = Number(data.bottom_margin_mm) || 30;
        state.letterheadConfig.include_summary_page2 = Boolean(data.include_summary_page2);
      }
    }
  } catch (e) {
    console.warn('Backend letterhead sync error:', e);
  }

  applyLetterheadPrintStyles();
}

function openLetterheadModal() {
  const chkPre = document.getElementById('chkPreprintedLetterhead');
  const rngTop = document.getElementById('rngTopMargin');
  const lblTop = document.getElementById('lblTopMargin');
  const rngBottom = document.getElementById('rngBottomMargin');
  const lblBottom = document.getElementById('lblBottomMargin');
  const chkPage2 = document.getElementById('chkIncludeSummaryPage2');
  const modal = document.getElementById('letterheadModal');

  if (chkPre) chkPre.checked = Boolean(state.letterheadConfig.preprinted_letterhead);
  if (rngTop) rngTop.value = state.letterheadConfig.top_margin_mm || 45;
  if (lblTop) lblTop.textContent = `${rngTop.value} mm`;
  if (rngBottom) rngBottom.value = state.letterheadConfig.bottom_margin_mm || 30;
  if (lblBottom) lblBottom.textContent = `${rngBottom.value} mm`;
  if (chkPage2) chkPage2.checked = Boolean(state.letterheadConfig.include_summary_page2);

  if (modal) modal.classList.remove('hidden');
}

function closeLetterheadModal() {
  const modal = document.getElementById('letterheadModal');
  if (modal) modal.classList.add('hidden');
}

function onLetterheadConfigChange() {
  const rngTop = document.getElementById('rngTopMargin');
  const lblTop = document.getElementById('lblTopMargin');
  const rngBottom = document.getElementById('rngBottomMargin');
  const lblBottom = document.getElementById('lblBottomMargin');
  if (rngTop && lblTop) lblTop.textContent = `${rngTop.value} mm`;
  if (rngBottom && lblBottom) lblBottom.textContent = `${rngBottom.value} mm`;
}

function resetLetterheadDefaults() {
  const chkPre = document.getElementById('chkPreprintedLetterhead');
  const rngTop = document.getElementById('rngTopMargin');
  const lblTop = document.getElementById('lblTopMargin');
  const rngBottom = document.getElementById('rngBottomMargin');
  const lblBottom = document.getElementById('lblBottomMargin');
  const chkPage2 = document.getElementById('chkIncludeSummaryPage2');

  if (chkPre) chkPre.checked = false;
  if (rngTop) rngTop.value = 45;
  if (lblTop) lblTop.textContent = '45 mm';
  if (rngBottom) rngBottom.value = 30;
  if (lblBottom) lblBottom.textContent = '30 mm';
  if (chkPage2) chkPage2.checked = false;
}

async function saveAndApplyLetterheadModal() {
  const chkPre = document.getElementById('chkPreprintedLetterhead');
  const rngTop = document.getElementById('rngTopMargin');
  const rngBottom = document.getElementById('rngBottomMargin');
  const chkPage2 = document.getElementById('chkIncludeSummaryPage2');

  state.letterheadConfig = {
    preprinted_letterhead: chkPre ? chkPre.checked : false,
    top_margin_mm: rngTop ? parseInt(rngTop.value, 10) : 45,
    bottom_margin_mm: rngBottom ? parseInt(rngBottom.value, 10) : 30,
    include_summary_page2: chkPage2 ? chkPage2.checked : false
  };

  try {
    localStorage.setItem('somatiq_letterhead_settings', JSON.stringify(state.letterheadConfig));
  } catch (e) {}

  try {
    await fetch('/api/letterhead-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.letterheadConfig)
    });
  } catch (e) {
    console.warn('Backend letterhead save error:', e);
  }

  applyLetterheadPrintStyles();
  closeLetterheadModal();
  showToast('🖨️ Letterhead calibration saved and applied.');
}

function applyLetterheadPrintStyles() {
  let styleEl = document.getElementById('dynamicLetterheadStyle');
  if (!styleEl) {
    styleEl = document.createElement('style');
    styleEl.id = 'dynamicLetterheadStyle';
    document.head.appendChild(styleEl);
  }

  const { preprinted_letterhead, top_margin_mm, bottom_margin_mm, include_summary_page2 } = state.letterheadConfig;

  styleEl.textContent = `
    @media print {
      .print-hospital-header {
        display: ${preprinted_letterhead ? 'none !important' : 'block !important'};
      }
      .rich-editor-content {
        padding-top: ${top_margin_mm || 45}mm !important;
        padding-bottom: ${bottom_margin_mm || 30}mm !important;
      }
      .print-page2-summary {
        display: ${include_summary_page2 ? 'block !important' : 'none !important'};
      }
    }
  `;

  // Update Page 2 print container text
  const printPage2El = document.getElementById('printPage2Summary');
  const printPage2Text = document.getElementById('printPage2SummaryText');
  if (printPage2El && printPage2Text) {
    if (include_summary_page2 && state.patientSummaries.en) {
      printPage2Text.textContent = state.patientSummaries.en;
      printPage2El.classList.remove('hidden');
    } else {
      printPage2El.classList.add('hidden');
    }
  }
}

// =========================================================================
// RADONE AI CLINICAL COLLABORATOR (Context-Aware Co-Pilot Drawer)
// =========================================================================

function toggleCollaboratorDrawer() {
  const drawer = document.getElementById('collaboratorDrawer');
  if (!drawer) return;

  const isClosed = drawer.classList.contains('translate-x-full');
  if (isClosed) {
    const vocabDrawer = document.getElementById('trainVocabDrawer');
    if (vocabDrawer) vocabDrawer.classList.add('translate-x-full');
    drawer.classList.remove('translate-x-full');
    updateCollaboratorContextBadge();
    const input = document.getElementById('collabCustomInput');
    if (input) setTimeout(() => input.focus(), 150);
  } else {
    drawer.classList.add('translate-x-full');
  }
}

function updateCollaboratorContextBadge() {
  const badge = document.getElementById('collabContextBadge');
  if (badge) {
    const modality = patientModality ? patientModality.value : 'Radiology';
    const study = selectTemplate && selectTemplate.selectedIndex >= 0 ? selectTemplate.options[selectTemplate.selectedIndex].text : 'Active Study';
    const ageSex = patientAgeSex ? patientAgeSex.value : '';
    badge.textContent = `${modality} • ${study} • ${ageSex}`.trim();
  }
}

function handleCustomCollaboratorSubmit(e) {
  if (e) e.preventDefault();
  const input = document.getElementById('collabCustomInput');
  if (!input) return;
  const query = input.value.trim();
  if (!query) {
    showToast('Please type a question or clinical query.');
    return;
  }
  runClinicalCollaborator('custom_ask', query);
}

async function runClinicalCollaborator(action, customQuery = null) {
  if (state.collaboratorLoading) return;

  const resultsContainer = document.getElementById('collabResultsContainer');
  const initialState = document.getElementById('collabInitialState');
  const loadingState = document.getElementById('collabLoadingState');
  const loadingText = document.getElementById('collabLoadingText');
  const contentBody = document.getElementById('collabContentBody');
  const modelBadge = document.getElementById('collabModelBadge');

  // Highlight active chip
  const chips = document.querySelectorAll('.collab-action-chip');
  chips.forEach(chip => {
    chip.classList.remove('bg-purple-900/60', 'border-purple-500', 'ring-1', 'ring-purple-400');
  });

  const chipMap = {
    'differentials': 'chipDifferentials',
    'history_check': 'chipHistoryCheck',
    'concise_impression': 'chipConciseImpression',
    'critical_alert': 'chipCriticalAlert'
  };
  if (chipMap[action]) {
    const activeChip = document.getElementById(chipMap[action]);
    if (activeChip) {
      activeChip.classList.add('bg-purple-900/60', 'border-purple-500', 'ring-1', 'ring-purple-400');
    }
  }

  // Set loading text based on action
  const loadingMessages = {
    'differentials': 'Analyzing findings for Differential Diagnoses & Evidence Guidelines...',
    'history_check': 'Correlating findings with Clinical History & Pertinent Negatives...',
    'concise_impression': 'Distilling findings into Senior-Consultant Crisp Impression...',
    'critical_alert': 'Scanning findings for Acute Panic Flags & Red Alerts...',
    'custom_ask': `Querying RadOne Co-Pilot: "${(customQuery || '').slice(0, 35)}..."`
  };

  if (loadingText) {
    loadingText.textContent = loadingMessages[action] || 'Analyzing clinical findings...';
  }

  // Switch UI states
  if (initialState) initialState.classList.add('hidden');
  if (contentBody) contentBody.classList.add('hidden');
  if (loadingState) loadingState.classList.remove('hidden');
  state.collaboratorLoading = true;

  // Extract clinical context from DOM & editor
  const collabHistInput = document.getElementById('collabClinicalHistoryInput');
  const clinicalHistInput = document.getElementById('clinicalHistory');
  let clinicalHistory = '';
  if (collabHistInput && collabHistInput.value.trim()) {
    clinicalHistory = collabHistInput.value.trim();
  } else if (clinicalHistInput && clinicalHistInput.value.trim()) {
    clinicalHistory = clinicalHistInput.value.trim();
  } else {
    const editorText = richEditor.innerText || '';
    const historyMatch = editorText.match(/CLINICAL INDICATION\s*:\s*([\s\S]*?)(?=\bFINDINGS|\bTECHNIQUE|\bPROCEDURE|\bIMPRESSION|$)/i);
    if (historyMatch && historyMatch[1].trim()) {
      clinicalHistory = historyMatch[1].trim();
    } else {
      clinicalHistory = 'Routine diagnostic evaluation / Not specified';
    }
  }

  const payload = {
    action: action,
    modality: patientModality ? patientModality.value : 'Radiology',
    study_name: selectTemplate && selectTemplate.selectedIndex >= 0 ? selectTemplate.options[selectTemplate.selectedIndex].text : 'Imaging Study',
    age_gender: patientAgeSex ? patientAgeSex.value : 'Adult',
    clinical_history: clinicalHistory,
    findings_html: richEditor.innerHTML || '',
    custom_query: customQuery,
    patient_name: patientName ? patientName.value : '',
    patient_phone: patientUHID ? patientUHID.value : ''
  };

  try {
    const res = await fetch('/api/clinical-collaborator', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Clinical Collaborator failed to respond.');
    }

    const data = await res.json();
    state.lastSuggestedImpression = data.suggested_impression_html || null;

    if (modelBadge && data.model_used) {
      modelBadge.textContent = data.model_used;
    }

    renderCollaboratorResults(data);

    if (loadingState) loadingState.classList.add('hidden');
    if (contentBody) contentBody.classList.remove('hidden');

    // Toast triage status
    if (data.triage_status === 'CRITICAL_PANIC') {
      showToast('🚨 CRITICAL / PANIC Alert: Immediate Clinician Communication Flagged!');
    } else {
      showToast('🧠 RadOne Clinical Analysis Complete');
    }

  } catch (err) {
    console.error('RadOne Collaborator error:', err);
    if (loadingState) loadingState.classList.add('hidden');
    if (contentBody) {
      contentBody.innerHTML = `
        <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-200 space-y-2">
          <div class="font-bold text-xs flex items-center gap-1.5">
            <span>❌</span> Clinical Co-Pilot Error
          </div>
          <p class="text-[11px] text-rose-300/90">${escapeHtml(err.message || 'Unable to connect to clinical collaborator.')}</p>
          <button onclick="runClinicalCollaborator('${action}', ${customQuery ? `'${escapeHtml(customQuery)}'` : 'null'})" class="mt-2 px-3 py-1 bg-rose-800 hover:bg-rose-700 text-white rounded text-xs font-semibold">
            Retry Analysis
          </button>
        </div>
      `;
      contentBody.classList.remove('hidden');
    }
    showToast('Failed to analyze with Clinical Collaborator.');
  } finally {
    state.collaboratorLoading = false;
  }
}

function renderCollaboratorResults(data) {
  const contentBody = document.getElementById('collabContentBody');
  if (!contentBody) return;

  // 1. Triage Badge
  let triageHtml = '';
  if (data.triage_status === 'CRITICAL_PANIC') {
    triageHtml = `
      <div class="px-3 py-2 rounded-xl bg-rose-950 border-2 border-rose-600 text-rose-200 font-bold text-xs flex items-center justify-between shadow-lg shadow-rose-900/40 animate-pulse">
        <span class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
          🚨 CRITICAL / PANIC FINDING ALERT
        </span>
        <span class="text-[10px] text-rose-300 font-mono font-bold bg-rose-900/60 px-2 py-0.5 rounded border border-rose-700">Immediate Action</span>
      </div>
    `;
  } else if (data.triage_status === 'ATTENTION') {
    triageHtml = `
      <div class="px-3 py-2 rounded-xl bg-amber-950/80 border border-amber-600 text-amber-200 font-bold text-xs flex items-center justify-between shadow-md">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-amber-400"></span>
          🟡 CLINICAL ATTENTION RECOMMENDED
        </span>
        <span class="text-[10px] text-amber-300 font-mono bg-amber-900/60 px-2 py-0.5 rounded border border-amber-700">Actionable</span>
      </div>
    `;
  } else {
    triageHtml = `
      <div class="px-3 py-2 rounded-xl bg-emerald-950/70 border border-emerald-700 text-emerald-200 font-bold text-xs flex items-center justify-between shadow-md">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          🟢 ROUTINE / NON-URGENT FINDINGS
        </span>
        <span class="text-[10px] text-emerald-300 font-mono bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-700">Standard Follow-up</span>
      </div>
    `;
  }

  // 2. Laterality / Hallucinated Measurement Safety Banner
  let safetyBannerHtml = '';
  if (data.laterality_and_number_check_passed === false) {
    safetyBannerHtml = `
      <div class="p-2.5 rounded-xl bg-amber-950/70 border border-amber-500 text-amber-200 text-[11px] leading-relaxed flex items-start gap-2 shadow-inner">
        <span class="text-base shrink-0">⚠️</span>
        <div>
          <strong class="text-amber-300">Deterministic Safety Alert:</strong>
          <span>Potential measurement unit discrepancy or laterality variation detected between raw dictated findings and AI output. Clinician must verify all sizes and sides.</span>
        </div>
      </div>
    `;
  }

  // 3. Summary Title Header
  const summaryTitleHtml = `
    <div class="border-b border-pacs-800 pb-2">
      <h3 class="font-bold text-white text-xs tracking-wide flex items-center gap-2">
        <span class="text-purple-400">✦</span> ${escapeHtml(data.summary_title)}
      </h3>
    </div>
  `;

  // 4. Clinical Evidence & Guideline Items
  const itemsHtml = (data.items || []).map(item => `
    <div class="bg-pacs-950 border border-pacs-800 rounded-xl p-3 space-y-1.5 hover:border-purple-800/80 transition shadow-inner">
      <div class="flex items-start justify-between gap-2">
        <span class="font-bold text-slate-100 text-xs">${escapeHtml(item.title)}</span>
        <span class="px-2 py-0.5 rounded text-[9px] font-mono bg-purple-950/90 border border-purple-800 text-purple-300 shrink-0 font-semibold">
          ${escapeHtml(item.confidence_or_guideline)}
        </span>
      </div>
      <p class="text-[11px] text-slate-300 leading-relaxed font-sans">${escapeHtml(item.detail)}</p>
    </div>
  `).join('');

  // 5. Suggested Structured Impression Box with 1-Click Insert
  let impressionBoxHtml = '';
  if (data.suggested_impression_html) {
    impressionBoxHtml = `
      <div class="bg-purple-950/30 border border-purple-700/60 rounded-xl p-3.5 space-y-2.5 shadow-lg">
        <div class="flex items-center justify-between">
          <span class="font-bold text-purple-300 text-[11px] uppercase tracking-wider flex items-center gap-1.5">
            <span>⚡</span> Suggested Structured Impression
          </span>
          <button id="btnInsertCollabImpression" onclick="insertCollaboratorImpression()" class="px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-[11px] flex items-center gap-1.5 shadow-md shadow-purple-600/30 transition active:scale-95" title="Insert directly into editor under IMPRESSION (Highlighted for clinician sign-off)">
            <span>📥</span> Insert into Report Impression
          </button>
        </div>
        <div class="bg-pacs-950 p-3 rounded-lg border border-pacs-800/90 text-xs text-slate-200 leading-relaxed font-sans shadow-inner">
          ${data.suggested_impression_html}
        </div>
      </div>
    `;
  }

  contentBody.innerHTML = `
    ${triageHtml}
    ${safetyBannerHtml}
    ${summaryTitleHtml}
    <div class="space-y-2.5">
      ${itemsHtml}
    </div>
    ${impressionBoxHtml}
  `;
}

function insertCollaboratorImpression() {
  if (!state.lastSuggestedImpression) {
    showToast('No suggested impression available to insert.');
    return;
  }

  const markedHtml = `<mark class="ai-diff-highlight">${state.lastSuggestedImpression}</mark>`;
  const html = richEditor.innerHTML;

  // Check if IMPRESSION header already exists in editor
  const impressionRegex = /(<p[^>]*><strong>\s*IMPRESSION\s*:?\s*<\/strong><\/p>|<strong>\s*IMPRESSION\s*:?\s*<\/strong>|\bIMPRESSION\s*:)/i;

  if (impressionRegex.test(html)) {
    const parts = html.split(impressionRegex);
    const matchedHeader = html.match(impressionRegex)[0];
    richEditor.innerHTML = `${parts[0]}${matchedHeader}<p>${markedHtml}</p>`;
  } else {
    // Append at the bottom
    richEditor.innerHTML += `<p><br></p><p><strong>IMPRESSION:</strong></p><p>${markedHtml}</p>`;
  }

  updateWordCount();
  updatePendingEditsCount();

  // Scroll to editor bottom
  richEditor.scrollTop = richEditor.scrollHeight;

  showToast('📥 Suggested impression inserted into report (Highlighted for clinician sign-off).');
}

// =========================================================================
// STEP 3: Live Teleradiology Worklist Queue, SLA Timers & WhatsApp Dispatch
// =========================================================================

function toggleWorklistDrawer() {
  const drawer = document.getElementById('worklistDrawer');
  if (!drawer) return;
  const isClosed = drawer.classList.contains('-translate-x-full');
  if (isClosed) {
    drawer.classList.remove('-translate-x-full');
    state.isWorklistDrawerOpen = true;
    fetchWorklistQueue();
  } else {
    drawer.classList.add('-translate-x-full');
    state.isWorklistDrawerOpen = false;
  }
}

async function fetchWorklistQueue() {
  try {
    const res = await fetch('/api/worklist');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.worklistQueue = data.studies || [];

    // Update KPI Ribbon counters
    const kpiStat = document.getElementById('kpiStatPending');
    const kpiQueue = document.getElementById('kpiQueuePending');
    const kpiSigned = document.getElementById('kpiSignedToday');
    const kpiTat = document.getElementById('kpiAvgTat');
    const headerBadge = document.getElementById('headerQueueBadge');

    if (data.stats) {
      if (kpiStat) kpiStat.textContent = data.stats.stat_pending;
      if (kpiQueue) kpiQueue.textContent = data.stats.queue_pending;
      if (kpiSigned) kpiSigned.textContent = data.stats.signed_today;
      if (kpiTat) kpiTat.textContent = `${data.stats.avg_tat_minutes}m`;
      if (headerBadge) headerBadge.textContent = data.stats.queue_pending;
    }

    renderWorklistCards();
    updateAllSLATimers();
  } catch (err) {
    console.warn('Failed to fetch worklist queue:', err);
  }
}

function setWorklistFilter(filter) {
  state.currentWorklistFilter = filter;
  const filterBtns = {
    ALL: document.getElementById('filterAll'),
    STAT: document.getElementById('filterSTAT'),
    URGENT: document.getElementById('filterURGENT'),
    ROUTINE: document.getElementById('filterROUTINE'),
    PENDING: document.getElementById('filterPENDING')
  };

  Object.entries(filterBtns).forEach(([key, btn]) => {
    if (!btn) return;
    if (key === filter) {
      btn.className = 'px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold transition';
    } else {
      btn.className = 'px-2 py-0.5 rounded bg-pacs-900 text-slate-300 border border-pacs-800 hover:bg-pacs-800 transition font-medium';
    }
  });

  renderWorklistCards();
}

function filterWorklistCards() {
  renderWorklistCards();
}

function renderWorklistCards() {
  const container = document.getElementById('worklistCardsContainer');
  if (!container) return;

  const searchTerm = (document.getElementById('worklistSearch')?.value || '').trim().toLowerCase();
  const filter = state.currentWorklistFilter;

  const filtered = state.worklistQueue.filter(study => {
    // 1. Status/Priority Filter
    if (filter === 'STAT' && study.priority !== 'STAT') return false;
    if (filter === 'URGENT' && study.priority !== 'URGENT') return false;
    if (filter === 'ROUTINE' && study.priority !== 'ROUTINE') return false;
    if (filter === 'PENDING' && !['PENDING', 'IN_PROGRESS'].includes(study.status)) return false;

    // 2. Search Text
    if (searchTerm) {
      const hay = `${study.patient_name} ${study.uhid} ${study.modality} ${study.study_name} ${study.referring_doctor} ${study.clinical_history}`.toLowerCase();
      if (!hay.includes(searchTerm)) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="py-12 text-center text-slate-500 text-xs">
        <span class="text-2xl block mb-2">📋</span>
        <p>No matching patient studies found.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(s => {
    const isActive = s.id === state.activeStudyId;
    let cardClasses = 'rounded-xl p-3 border transition-all duration-200 shadow-sm relative space-y-2 ';

    if (isActive) {
      cardClasses += 'bg-cyan-950/40 border-cyan-500 shadow-md shadow-cyan-950/60 ring-1 ring-cyan-500/50';
    } else if (s.priority === 'STAT') {
      cardClasses += 'bg-rose-950/20 border-rose-800/80 hover:border-rose-600';
    } else if (s.priority === 'URGENT') {
      cardClasses += 'bg-amber-950/20 border-amber-800/80 hover:border-amber-600';
    } else {
      cardClasses += 'bg-pacs-950/70 border-pacs-850 hover:border-pacs-700';
    }

    // Priority badge
    let priorityBadge = '';
    if (s.priority === 'STAT') {
      priorityBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-900/90 text-rose-200 border border-rose-600 animate-pulse">🚨 STAT</span>';
    } else if (s.priority === 'URGENT') {
      priorityBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-900/80 text-amber-200 border border-amber-600">⚡ URGENT</span>';
    } else {
      priorityBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-pacs-900 text-slate-400 border border-pacs-800">ROUTINE</span>';
    }

    // Status badge
    let statusBadge = '';
    if (s.status === 'SIGNED') {
      statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">✅ SIGNED</span>';
    } else if (s.status === 'DISPATCHED') {
      statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-teal-950 text-teal-300 border border-teal-800">📲 DISPATCHED</span>';
    } else if (s.status === 'IN_PROGRESS') {
      statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-950 text-blue-300 border border-blue-800 animate-pulse">⏳ IN PROGRESS</span>';
    } else {
      statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-pacs-900 text-slate-400 border border-pacs-800">PENDING</span>';
    }

    return `
      <div class="${cardClasses}">
        <!-- Top Badges Row -->
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            ${priorityBadge}
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800 font-mono">${escapeHtml(s.modality)}</span>
          </div>
          ${statusBadge}
        </div>

        <!-- Patient Demographics -->
        <div class="flex items-start justify-between gap-2">
          <div>
            <h4 class="font-bold text-white text-xs hover:text-cyan-400 transition cursor-pointer" onclick="loadWorklistStudy('${s.id}')">
              ${escapeHtml(s.patient_name)}
            </h4>
            <div class="text-[10px] text-slate-400 font-mono">
              UHID: <span class="text-cyan-400">${escapeHtml(s.uhid)}</span> • ${escapeHtml(s.age_gender)}
            </div>
          </div>
          <div class="text-right text-[10px] text-slate-400 shrink-0 font-mono">
            ${escapeHtml(s.patient_phone || '')}
          </div>
        </div>

        <!-- Study & History Preview -->
        <div class="space-y-0.5">
          <div class="text-[11px] font-semibold text-slate-200">${escapeHtml(s.study_name)}</div>
          <div class="text-[10px] text-slate-400 line-clamp-1 italic">${escapeHtml(s.clinical_history || 'Diagnostic examination')}</div>
        </div>

        <!-- Real-Time SLA Countdown Badge -->
        <div class="sla-timer-badge pt-1 flex items-center justify-between border-t border-pacs-850/80"
             data-study-id="${s.id}"
             data-created-at="${s.created_at}"
             data-sla-minutes="${s.sla_target_minutes}"
             data-signed-at="${s.signed_at || ''}"
             data-status="${s.status}">
          <span class="text-[10px] text-slate-400 font-mono">SLA Target: ${s.sla_target_minutes}m</span>
          <span class="sla-timer-display font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-pacs-900 border border-pacs-800">Calculating...</span>
        </div>

        <!-- Action Buttons -->
        <div class="pt-1.5 flex items-center justify-between gap-2">
          <button onclick="loadWorklistStudy('${s.id}')" class="flex-1 py-1 px-2.5 rounded-lg text-[11px] font-bold transition flex items-center justify-center gap-1.5 ${isActive ? 'bg-cyan-600 text-white' : 'bg-pacs-800 hover:bg-pacs-700 text-cyan-300 border border-pacs-700'}">
            <span>${isActive ? '● Active Study' : '📖 Load in Editor'}</span>
          </button>
          
          <button onclick="openWhatsAppModalForStudy('${s.id}')" class="px-2.5 py-1 rounded-lg bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 text-[11px] font-bold transition flex items-center gap-1" title="Send WhatsApp Notification">
            <span>📲</span>
          </button>

          ${s.status === 'SIGNED' || s.status === 'DISPATCHED' ? `
            <a href="/report/view/${s.id}" target="_blank" class="px-2.5 py-1 rounded-lg bg-blue-950/80 hover:bg-blue-900 border border-blue-800 text-blue-300 text-[11px] font-bold transition flex items-center gap-1" title="View Public Signed Letterhead Report">
              <span>🔗</span>
            </a>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  updateAllSLATimers();
}

function updateAllSLATimers() {
  const badges = document.querySelectorAll('.sla-timer-badge');
  badges.forEach(badge => {
    const createdAtStr = badge.getAttribute('data-created-at');
    const slaMinutes = parseInt(badge.getAttribute('data-sla-minutes') || '30', 10);
    const signedAtStr = badge.getAttribute('data-signed-at');
    const status = badge.getAttribute('data-status');
    const display = badge.querySelector('.sla-timer-display');
    if (!display || !createdAtStr) return;

    if (status === 'SIGNED' || status === 'DISPATCHED') {
      let tatText = 'Signed';
      if (signedAtStr && createdAtStr) {
        try {
          const cTime = new Date(createdAtStr).getTime();
          const sTime = new Date(signedAtStr).getTime();
          const tatMins = Math.max(1, Math.round((sTime - cTime) / 60000));
          const metOrBreached = tatMins <= slaMinutes ? 'SLA Met' : 'Breached';
          tatText = `Done in ${tatMins}m (${metOrBreached})`;
        } catch (e) {
          tatText = 'Signed';
        }
      }
      display.className = 'sla-timer-display font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800';
      display.textContent = `✅ ${tatText}`;
      return;
    }

    // Pending or In-Progress Studies
    try {
      const createdTime = new Date(createdAtStr).getTime();
      const now = Date.now();
      const elapsedSeconds = Math.max(0, Math.floor((now - createdTime) / 1000));
      const totalSlaSeconds = slaMinutes * 60;
      const remainingSeconds = totalSlaSeconds - elapsedSeconds;

      if (remainingSeconds > 300) {
        // Healthy state (> 5 mins remaining)
        const m = Math.floor(remainingSeconds / 60);
        const s = remainingSeconds % 60;
        display.className = 'sla-timer-display font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-950/70 text-emerald-400 border border-emerald-700/80';
        display.textContent = `⏳ ${m}m ${String(s).padStart(2, '0')}s remaining`;
      } else if (remainingSeconds > 0) {
        // Warning state (<= 5 mins remaining)
        const m = Math.floor(remainingSeconds / 60);
        const s = remainingSeconds % 60;
        display.className = 'sla-timer-display font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-600 animate-pulse';
        display.textContent = `⚠️ ${m}m ${String(s).padStart(2, '0')}s remaining`;
      } else {
        // Overdue / Breached state
        const overdueSecs = Math.abs(remainingSeconds);
        const m = Math.floor(overdueSecs / 60);
        const s = overdueSecs % 60;
        display.className = 'sla-timer-display font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-600 animate-pulse';
        display.textContent = `🚨 BREACHED +${m}m ${String(s).padStart(2, '0')}s`;
      }
    } catch (e) {
      display.textContent = `${slaMinutes}m SLA`;
    }
  });
}

async function loadWorklistStudy(studyId) {
  const study = state.worklistQueue.find(s => s.id === studyId);
  if (!study) {
    showToast('Study not found in worklist.');
    return;
  }

  state.activeStudyId = study.id;

  // 1. Populate Patient Metadata Header Inputs
  if (patientName) patientName.value = study.patient_name || '';
  if (patientAgeSex) patientAgeSex.value = study.age_gender || '';
  if (patientUHID) patientUHID.value = study.uhid || '';
  if (patientModality) patientModality.value = study.modality || '';

  const clinicalHistInput = document.getElementById('clinicalHistory');
  const collabHistInput = document.getElementById('collabClinicalHistoryInput');
  if (clinicalHistInput) clinicalHistInput.value = study.clinical_history || '';
  if (collabHistInput) collabHistInput.value = study.clinical_history || '';

  // 2. Select matching template if available
  if (selectTemplate && study.template_key) {
    const exists = Array.from(selectTemplate.options).some(opt => opt.value === study.template_key);
    if (exists) {
      selectTemplate.value = study.template_key;
      onTemplateSelect();
    }
  }

  // 3. Restore existing report HTML / Patient Summary if available
  if (study.final_report_html) {
    richEditor.innerHTML = study.final_report_html;
  }
  if (study.patient_summary) {
    state.patientSummaries.en = study.patient_summary;
    const summaryContainer = document.getElementById('patientSummaryContainer');
    const summaryText = document.getElementById('patientSummaryText');
    if (summaryContainer && summaryText) {
      summaryText.textContent = study.patient_summary;
      summaryContainer.classList.remove('hidden');
    }
  }

  updateWordCount();
  updatePendingEditsCount();

  // 4. Update Collaborator Context Badge
  const collabBadge = document.getElementById('collabContextBadge');
  if (collabBadge) {
    collabBadge.textContent = `${study.uhid} • ${study.patient_name} (${study.modality})`;
  }

  // 5. Update study status to IN_PROGRESS if currently PENDING
  if (study.status === 'PENDING') {
    study.status = 'IN_PROGRESS';
    try {
      fetch(`/api/worklist/${study.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'IN_PROGRESS' })
      }).catch(() => {});
    } catch (e) {}
  }

  renderWorklistCards();
  showToast(`📋 Loaded patient: ${study.patient_name} (${study.modality})`);
}

async function signAndAutoAdvance() {
  const btn = document.getElementById('btnSignAndNext');
  if (btn) btn.disabled = true;

  try {
    // 1. Identify active study or fallback to first pending/in_progress study
    let study = state.worklistQueue.find(s => s.id === state.activeStudyId);
    if (!study) {
      study = state.worklistQueue.find(s => ['IN_PROGRESS', 'PENDING'].includes(s.status));
      if (study) {
        state.activeStudyId = study.id;
      }
    }

    if (!study) {
      showToast('No active patient study loaded from worklist.');
      return;
    }

    // 2. Clear all diff highlights automatically upon sign-off
    acceptAllEdits();

    const finalReportHtml = richEditor.innerHTML;
    const patientSummaryText = state.patientSummaries.en || '';

    showToast(`✅ Signing and recording TAT for ${study.patient_name}...`);

    // 3. Call backend to update status to SIGNED
    const res = await fetch(`/api/worklist/${study.id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'SIGNED',
        final_report_html: finalReportHtml,
        patient_summary: patientSummaryText
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to sign report in worklist');
    }

    const data = await res.json();
    study.status = 'SIGNED';
    study.signed_at = data.study?.signed_at || new Date().toISOString();
    study.final_report_html = finalReportHtml;
    study.patient_summary = patientSummaryText;

    showToast(`✅ Report signed for ${study.patient_name}! Turnaround time recorded.`);

    // Refresh queue KPIs
    await fetchWorklistQueue();

    // 4. Auto-advance workflow if enabled
    const chkAutoAdvance = document.getElementById('chkAutoAdvance');
    if (chkAutoAdvance && chkAutoAdvance.checked) {
      // Find next pending or in_progress study (excluding current study)
      const nextStudy = state.worklistQueue.find(s => ['PENDING', 'IN_PROGRESS'].includes(s.status) && s.id !== study.id);
      if (nextStudy) {
        showToast(`🚀 Auto-advancing to next patient (${nextStudy.patient_name}) in 1.2s...`);
        setTimeout(() => {
          loadWorklistStudy(nextStudy.id);
        }, 1200);
      } else {
        showToast('🎉 All queued cases completed! Worklist fully reported.');
      }
    }

  } catch (err) {
    console.error('Sign & Auto-Advance error:', err);
    showToast(`Error signing report: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// -------------------------------------------------------------
// Add Patient Modal Controller
// -------------------------------------------------------------
function openAddPatientModal() {
  const modal = document.getElementById('addPatientModal');
  if (modal) {
    modal.classList.remove('hidden');
    onNewModalityChange();
  }
}

function closeAddPatientModal() {
  const modal = document.getElementById('addPatientModal');
  if (modal) modal.classList.add('hidden');
}

function onNewModalityChange() {
  const modSelect = document.getElementById('newPatientModality');
  const tplSelect = document.getElementById('newPatientTemplateKey');
  if (!modSelect || !tplSelect) return;

  const modality = modSelect.value;
  tplSelect.innerHTML = '';

  const modalityMap = {
    'USG': [
      { key: 'usg_abdomen', label: 'Ultrasound Whole Abdomen' }
    ],
    'CT': [
      { key: 'ct_brain', label: 'CT Brain Plain / Non-Contrast' },
      { key: 'ct_chest', label: 'CT Chest / HRCT Thorax' }
    ],
    'MRI': [
      { key: 'mri_brain', label: 'MRI Brain Multi-sequence' },
      { key: 'mri_lumbar_spine', label: 'MRI Lumbar Spine' }
    ],
    'X-RAY': [
      { key: 'chest_xray', label: 'Chest X-Ray PA View' }
    ],
    'PET-CT': [
      { key: 'petct_fdg_whole_body', label: 'Whole Body FDG PET-CT' },
      { key: 'petct_psma', label: 'PSMA PET-CT (Prostate)' },
      { key: 'petct_dotanoc', label: 'DOTANOC / DOTATATE PET-CT' },
      { key: 'petct_brain', label: 'Brain PET-CT' },
      { key: 'petct_cardiac', label: 'Cardiac PET-CT' }
    ],
    'SPECT': [
      { key: 'spect_bone_scan', label: 'Bone Scan (99mTc-MDP)' },
      { key: 'spect_renal_dtpa', label: 'Renal Scan - DTPA (Dynamic/GFR)' },
      { key: 'spect_renal_dmsa', label: 'Renal Scan - DMSA (Static)' },
      { key: 'spect_thyroid', label: 'Thyroid & Parathyroid Scan' },
      { key: 'spect_cardiac_perfusion', label: 'Myocardial Perfusion SPECT' },
      { key: 'spect_lung_vq', label: 'Lung Perfusion (V/Q Scan)' },
      { key: 'spect_hida', label: 'HIDA Scan' },
      { key: 'spect_brain', label: 'Brain SPECT' }
    ],
    'THERANOSTICS': [
      { key: 'thera_radioiodine_i131', label: 'Radioiodine Therapy (I-131)' },
      { key: 'thera_lu177_psma', label: 'Lu-177 PSMA Therapy' },
      { key: 'thera_lu177_dotatate', label: 'Lu-177 DOTATATE Therapy' },
      { key: 'thera_ac225_psma', label: 'Ac-225 PSMA Alpha Therapy' },
      { key: 'thera_bone_pain_palliation', label: 'Bone Pain Palliation' },
      { key: 'thera_radiosynovectomy', label: 'Radiosynovectomy' }
    ]
  };

  const templates = modalityMap[modality] || [{ key: 'ct_brain', label: 'CT Brain Plain' }];
  templates.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.key;
    opt.textContent = t.label;
    tplSelect.appendChild(opt);
  });
}

function populateNewPatientTemplates() {
  onNewModalityChange();
}

async function handleAddPatientSubmit(e) {
  e.preventDefault();

  const name = document.getElementById('newPatientName')?.value.trim();
  const ageGender = document.getElementById('newPatientAgeGender')?.value.trim();
  const phone = document.getElementById('newPatientPhone')?.value.trim();
  const uhid = document.getElementById('newPatientUHID')?.value.trim();
  const priority = document.getElementById('newPatientPriority')?.value || 'ROUTINE';
  const modality = document.getElementById('newPatientModality')?.value || 'CT';
  const templateKey = document.getElementById('newPatientTemplateKey')?.value || 'ct_brain';
  const doctor = document.getElementById('newPatientDoctor')?.value.trim() || 'Dr. Self-Referred / Duty Clinician';
  const history = document.getElementById('newPatientHistory')?.value.trim();

  if (!name || !ageGender || !phone || !history) {
    showToast('Please fill in all required patient fields.');
    return;
  }

  try {
    const payload = {
      patient_name: name,
      age_gender: ageGender,
      patient_phone: phone,
      uhid: uhid || undefined,
      priority: priority,
      modality: modality,
      template_key: templateKey,
      referring_doctor: doctor,
      clinical_history: history
    };

    const res = await fetch('/api/worklist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to enqueue patient');
    }

    const data = await res.json();
    closeAddPatientModal();
    showToast(`✅ Patient ${name} enqueued with ${data.study.sla_target_minutes}m SLA target!`);

    await fetchWorklistQueue();

    // If STAT or no study currently active, load immediately
    if (priority === 'STAT' || !state.activeStudyId) {
      loadWorklistStudy(data.study.id);
    }
  } catch (err) {
    console.error('Failed to add patient to worklist:', err);
    showToast(`Failed to add patient: ${err.message}`);
  }
}

// -------------------------------------------------------------
// WhatsApp Notification Modal Controller
// -------------------------------------------------------------
function openWhatsAppModalForStudy(studyId) {
  const study = state.worklistQueue.find(s => s.id === studyId);
  if (!study) {
    showToast('Study not found for WhatsApp dispatch.');
    return;
  }

  state.activeWhatsAppStudy = study;

  const modal = document.getElementById('whatsappModal');
  const phoneInput = document.getElementById('waRecipientPhone');
  const patientInfo = document.getElementById('waPatientInfo');
  const studyInfo = document.getElementById('waStudyInfo');
  const preview = document.getElementById('waMessagePreview');
  const directLink = document.getElementById('waDirectReportLink');

  if (phoneInput) phoneInput.value = (study.patient_phone || '').replace(/\D/g, '').slice(-10) || '9876543210';
  if (patientInfo) patientInfo.textContent = `Patient: ${study.patient_name} (${study.age_gender}) • UHID: ${study.uhid}`;
  if (studyInfo) studyInfo.textContent = `Study: ${study.modality} — ${study.study_name} • Dr: ${study.referring_doctor}`;
  if (directLink) directLink.href = `/report/view/${study.id}`;

  const reportUrl = `${window.location.origin}/report/view/${study.id}`;
  const summarySnippet = study.patient_summary || 'Diagnostic evaluation completed. Official report signed by Consultant Radiologist.';

  if (preview) {
    preview.textContent = 
`🏥 DEPARTMENT OF RADIOLOGY & IMAGING
OFFICIAL MEDICAL REPORT NOTIFICATION
━━━━━━━━━━━━━━━━━━━━━━
👤 Patient Name: ${study.patient_name} (${study.age_gender})
🆔 Patient UHID: ${study.uhid}
📋 Modality & Study: ${study.modality} — ${study.study_name}
👨‍⚕️ Referring Clinician: ${study.referring_doctor}
━━━━━━━━━━━━━━━━━━━━━━
📋 CLINICAL IMPRESSION / PATIENT GUIDE:
${summarySnippet}

🔗 View & Download Official Signed Report:
${reportUrl}
━━━━━━━━━━━━━━━━━━━━━━
This is an official digitally signed diagnostic imaging report. Please present this link to your consulting physician.`;
  }

  if (modal) modal.classList.remove('hidden');
}

function closeWhatsAppModal() {
  const modal = document.getElementById('whatsappModal');
  if (modal) modal.classList.add('hidden');
}

async function executeWhatsAppDispatch() {
  const study = state.activeWhatsAppStudy;
  if (!study) {
    showToast('No active study selected for WhatsApp dispatch.');
    return;
  }

  const phoneInput = document.getElementById('waRecipientPhone');
  const customPhone = phoneInput ? phoneInput.value.trim() : study.patient_phone;

  const btn = document.getElementById('btnDispatchWA');
  if (btn) btn.disabled = true;

  try {
    const payload = {
      recipient_type: 'both',
      custom_phone: customPhone,
      base_url: window.location.origin
    };

    const res = await fetch(`/api/worklist/${study.id}/send-whatsapp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'WhatsApp dispatch request failed');
    }

    const data = await res.json();
    closeWhatsAppModal();

    // Open WhatsApp Web Link in new tab
    if (data.whatsapp_web_url) {
      window.open(data.whatsapp_web_url, '_blank');
      showToast('📲 Official WhatsApp link generated! Opening WhatsApp...');
    } else {
      showToast('📲 WhatsApp notification dispatched via Green-API!');
    }

    // Refresh status
    await fetchWorklistQueue();

  } catch (err) {
    console.error('WhatsApp dispatch error:', err);
    showToast(`WhatsApp dispatch failed: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}
