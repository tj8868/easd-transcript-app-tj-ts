/**
 * Universal Transcription Module - Frontend Application Controller
 * Handles:
 * - Hardware Profile & Auto Engine Sync
 * - Live Studio (Microphone Recording, Audio Visualizer, WebSocket/Chunk Streaming)
 * - Batch Processing (Drag & Drop, Multi-file Queue, Progress Tracking)
 * - Custom API Configuration & Connection Testing
 * - Speaker Diarization & Timestamp Formatting & Exports (TXT, SRT, VTT, JSON)
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  const state = {
    systemStatus: null,
    isRecording: false,
    mediaRecorder: null,
    audioStream: null,
    audioContext: null,
    analyser: null,
    recordTimerInterval: null,
    recordSeconds: 0,
    liveSessionId: null,
    liveSegments: [],
    queuedFiles: [],
    activeBatchResults: null
  };

  // DOM Elements
  const badgeHw = document.getElementById('badgeHw');
  const hwLabel = document.getElementById('hwLabel');
  const activeEngineText = document.getElementById('activeEngineText');
  const engineModeSelect = document.getElementById('engineModeSelect');
  const languageSelect = document.getElementById('languageSelect');

  // Tabs
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  // Live Controls
  const recordBtn = document.getElementById('recordBtn');
  const recordBtnText = document.getElementById('recordBtnText');
  const recIcon = document.getElementById('recIcon');
  const timerDisplay = document.getElementById('timerDisplay');
  const visualizerCanvas = document.getElementById('visualizerCanvas');
  const micStatus = document.getElementById('micStatus');
  const liveTranscriptFeed = document.getElementById('liveTranscriptFeed');
  const btnClearLive = document.getElementById('btnClearLive');
  const btnCopyLive = document.getElementById('btnCopyLive');
  const btnExportLive = document.getElementById('btnExportLive');
  const exportDropdownLive = document.getElementById('exportDropdownLive');

  // Batch Controls
  const uploadDropzone = document.getElementById('uploadDropzone');
  const batchFileInput = document.getElementById('batchFileInput');
  const btnSelectFiles = document.getElementById('btnSelectFiles');
  const batchQueueSection = document.getElementById('batchQueueSection');
  const queueCount = document.getElementById('queueCount');
  const queueList = document.getElementById('queueList');
  const btnStartBatch = document.getElementById('btnStartBatch');
  const batchResultsSection = document.getElementById('batchResultsSection');
  const batchTranscriptView = document.getElementById('batchTranscriptView');
  const btnCopyBatch = document.getElementById('btnCopyBatch');
  const btnExportBatch = document.getElementById('btnExportBatch');
  const exportDropdownBatch = document.getElementById('exportDropdownBatch');

  // Custom API Modal
  const btnCustomApiModal = document.getElementById('btnCustomApiModal');
  const customApiModal = document.getElementById('customApiModal');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const apiEnabledCheckbox = document.getElementById('apiEnabledCheckbox');
  const apiName = document.getElementById('apiName');
  const apiProviderType = document.getElementById('apiProviderType');
  const apiBaseUrl = document.getElementById('apiBaseUrl');
  const apiKey = document.getElementById('apiKey');
  const apiMaskedHint = document.getElementById('apiMaskedHint');
  const apiModelName = document.getElementById('apiModelName');
  const btnTestApi = document.getElementById('btnTestApi');
  const btnSaveApi = document.getElementById('btnSaveApi');
  const testFeedback = document.getElementById('testFeedback');

  // ----------------------------------------------------
  // 1. System Status & Hardware Initialization
  // ----------------------------------------------------
  async function fetchSystemStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) throw new Error('Status failed');
      const data = await res.json();
      state.systemStatus = data;

      // Update Hardware Badge
      const hw = data.hardware;
      if (hw) {
        const tier = hw.is_low_end ? 'Low-End PC (INT8 Auto-Selected)' : 'High-End PC (Whisper Turbo)';
        hwLabel.textContent = `${hw.cpu_count} CPU Cores • ${hw.total_ram_gb}GB RAM • ${tier}`;
        badgeHw.title = hw.summary;
      }

      // Update Engine Text
      activeEngineText.textContent = data.active_engine || 'Auto';

      // Update Mode select
      if (data.settings && data.settings.default_mode) {
        engineModeSelect.value = data.settings.default_mode;
      }
      if (data.settings && data.settings.language) {
        languageSelect.value = data.settings.language;
      }
    } catch (err) {
      console.warn('Status fetch error:', err);
      hwLabel.textContent = 'Hardware Status Offline';
    }
  }

  engineModeSelect.addEventListener('change', async () => {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_mode: engineModeSelect.value,
          language: languageSelect.value
        })
      });
      fetchSystemStatus();
    } catch (e) {
      console.error(e);
    }
  });

  languageSelect.addEventListener('change', async () => {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_mode: engineModeSelect.value,
          language: languageSelect.value
        })
      });
    } catch (e) {
      console.error(e);
    }
  });

  // ----------------------------------------------------
  // 2. Tab Navigation
  // ----------------------------------------------------
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId).classList.add('active');
    });
  });

  // ----------------------------------------------------
  // 3. Audio Visualizer Setup
  // ----------------------------------------------------
  function startVisualizer(stream) {
    try {
      state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = state.audioContext.createMediaStreamSource(stream);
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 64;
      source.connect(state.analyser);

      const bufferLength = state.analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      const canvasCtx = visualizerCanvas.getContext('2d');

      function draw() {
        if (!state.isRecording) {
          canvasCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
          return;
        }
        requestAnimationFrame(draw);
        state.analyser.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = '#0b0e14';
        canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

        const barWidth = (visualizerCanvas.width / bufferLength) * 1.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          barHeight = (dataArray[i] / 255) * visualizerCanvas.height;
          canvasCtx.fillStyle = '#3b82f6';
          canvasCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth, barHeight);
          x += barWidth + 2;
        }
      }
      draw();
    } catch (e) {
      console.warn('Visualizer init failed:', e);
    }
  }

  // ----------------------------------------------------
  // 4. Live Record Studio (Record Button)
  // ----------------------------------------------------
  recordBtn.addEventListener('click', async () => {
    if (!state.isRecording) {
      await startRecording();
    } else {
      stopRecording();
    }
  });

  async function startRecording() {
    try {
      micStatus.textContent = 'Requesting Microphone...';
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.audioStream = stream;
      state.isRecording = true;

      // Update UI
      recordBtn.classList.add('recording');
      recordBtnText.textContent = 'Stop Recording';
      recIcon.textContent = '■';
      micStatus.textContent = 'Microphone Live';

      // Clear previous placeholder
      const placeholder = document.getElementById('livePlaceholder');
      if (placeholder) placeholder.style.display = 'none';

      // Start timer
      state.recordSeconds = 0;
      updateTimerDisplay();
      state.recordTimerInterval = setInterval(() => {
        state.recordSeconds++;
        updateTimerDisplay();
      }, 1000);

      // Start visualizer
      startVisualizer(stream);

      // Initialize session on server
      state.liveSessionId = 'live_' + Date.now();
      const startFormData = new FormData();
      startFormData.append('session_id', state.liveSessionId);
      startFormData.append('language', languageSelect.value);
      await fetch('/api/live/start', { method: 'POST', body: startFormData });

      // Start MediaRecorder with 3.5s chunk slicing
      let mimeType = 'audio/webm';
      if (!MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/wav';
      }

      state.mediaRecorder = new MediaRecorder(stream, { mimeType });
      state.mediaRecorder.ondataavailable = async (e) => {
        if (e.data && e.data.size > 200 && state.isRecording) {
          sendAudioChunk(e.data, mimeType);
        }
      };

      state.mediaRecorder.start(3500); // chunk every 3.5 seconds
    } catch (err) {
      alert('Could not access microphone: ' + err.message);
      micStatus.textContent = 'Microphone Access Denied';
      state.isRecording = false;
      recordBtn.classList.remove('recording');
      recordBtnText.textContent = 'Start Recording';
    }
  }

  async function sendAudioChunk(blob, mimeType) {
    if (!state.liveSessionId) return;
    try {
      const formData = new FormData();
      formData.append('session_id', state.liveSessionId);
      formData.append('file', blob, 'chunk.webm');
      formData.append('is_final', 'false');

      const res = await fetch('/api/live/chunk', { method: 'POST', body: formData });
      if (!res.ok) return;
      const data = await res.json();

      if (data.segments && data.segments.length > 0) {
        data.segments.forEach(seg => {
          state.liveSegments.push(seg);
          appendTranscriptLine(liveTranscriptFeed, seg);
        });
      }
    } catch (e) {
      console.warn('Chunk send failed:', e);
    }
  }

  function appendTranscriptLine(container, seg) {
    const row = document.createElement('div');
    row.className = 'transcript-line';

    const spkClass = `spk-${((seg.speaker_id - 1) % 4) + 1}`;
    row.innerHTML = `
      <span class="ts-badge">${seg.timestamp || '[00:00]'}</span>
      <span class="spk-badge ${spkClass}">${seg.speaker || 'Speaker 1'}</span>
      <span class="seg-text">${escapeHtml(seg.text)}</span>
    `;
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
  }

  async function stopRecording() {
    state.isRecording = false;
    clearInterval(state.recordTimerInterval);

    recordBtn.classList.remove('recording');
    recordBtnText.textContent = 'Start Recording';
    recIcon.textContent = '●';
    micStatus.textContent = 'Recording Stopped';

    if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
      state.mediaRecorder.stop();
    }
    if (state.audioStream) {
      state.audioStream.getTracks().forEach(t => t.stop());
    }
    if (state.audioContext) {
      state.audioContext.close();
    }

    // Finalize on server
    if (state.liveSessionId) {
      try {
        const formData = new FormData();
        formData.append('session_id', state.liveSessionId);
        await fetch('/api/live/stop', { method: 'POST', body: formData });
      } catch (e) {
        console.warn('Stop failed:', e);
      }
    }
  }

  function updateTimerDisplay() {
    const m = Math.floor(state.recordSeconds / 60);
    const s = state.recordSeconds % 60;
    timerDisplay.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  btnClearLive.addEventListener('click', () => {
    liveTranscriptFeed.innerHTML = `
      <div class="placeholder-notice" id="livePlaceholder">
        <div class="placeholder-icon">🎙️</div>
        <h3>Microphone Standby</h3>
        <p>Click <strong>Start Recording</strong> to transcribe live speech in real time with automatic speaker diarization and timestamps.</p>
      </div>
    `;
    state.liveSegments = [];
  });

  btnCopyLive.addEventListener('click', () => {
    const lines = state.liveSegments.map(s => `${s.timestamp} ${s.speaker}: ${s.text}`).join('\n');
    if (!lines) return alert('No transcript to copy.');
    navigator.clipboard.writeText(lines).then(() => alert('Live transcript copied to clipboard!'));
  });

  // Dropdown Export Live
  setupDropdown(btnExportLive, exportDropdownLive, () => state.liveSegments);

  // ----------------------------------------------------
  // 5. Batch Processing (Upload Button)
  // ----------------------------------------------------
  btnSelectFiles.addEventListener('click', () => batchFileInput.click());

  uploadDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadDropzone.classList.add('drag-over');
  });

  uploadDropzone.addEventListener('dragleave', () => {
    uploadDropzone.classList.remove('drag-over');
  });

  uploadDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadDropzone.classList.remove('drag-over');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  });

  batchFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesSelected(e.target.files);
    }
  });

  function handleFilesSelected(files) {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      state.queuedFiles.push({
        id: 'file_' + Date.now() + '_' + i,
        file: file,
        name: file.name,
        size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
        status: 'queued',
        progress: 0,
        result: null
      });
    }
    renderQueue();
  }

  function renderQueue() {
    if (state.queuedFiles.length === 0) {
      batchQueueSection.style.display = 'none';
      return;
    }
    batchQueueSection.style.display = 'block';
    queueCount.textContent = state.queuedFiles.length;
    queueList.innerHTML = '';

    state.queuedFiles.forEach(item => {
      const row = document.createElement('div');
      row.className = 'queue-item';
      row.id = `queue_${item.id}`;
      row.innerHTML = `
        <div class="queue-item-info">
          <span style="font-size: 1.4rem;">🎵</span>
          <div>
            <div class="queue-item-name">${escapeHtml(item.name)}</div>
            <div class="queue-item-size">${item.size} • <span class="q-status">${item.status}</span></div>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width: ${item.progress}%"></div>
        </div>
      `;
      queueList.appendChild(row);
    });
  }

  btnStartBatch.addEventListener('click', async () => {
    btnStartBatch.disabled = true;
    for (const item of state.queuedFiles) {
      if (item.status === 'completed') continue;
      await processSingleBatchFile(item);
    }
    btnStartBatch.disabled = false;
  });

  async function processSingleBatchFile(item) {
    const row = document.getElementById(`queue_${item.id}`);
    const statusText = row.querySelector('.q-status');
    const fill = row.querySelector('.progress-fill');

    statusText.textContent = 'Uploading...';
    fill.style.width = '20%';

    try {
      const formData = new FormData();
      formData.append('file', item.file);
      formData.append('language', languageSelect.value);

      const res = await fetch('/api/batch/upload', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload error');
      const data = await res.json();
      const jobId = data.job_id;

      statusText.textContent = 'Processing...';
      fill.style.width = '40%';

      // Poll for completion
      await new Promise((resolve, reject) => {
        const interval = setInterval(async () => {
          try {
            const pollRes = await fetch(`/api/batch/status/${jobId}`);
            if (!pollRes.ok) return;
            const pollData = await pollRes.json();

            fill.style.width = `${pollData.progress || 50}%`;
            statusText.textContent = pollData.message || pollData.stage;

            if (pollData.status === 'success') {
              clearInterval(interval);
              item.status = 'completed';
              item.result = pollData.result;
              fill.style.width = '100%';
              statusText.textContent = 'Completed!';
              renderBatchResults(pollData.result);
              resolve();
            } else if (pollData.status === 'error') {
              clearInterval(interval);
              item.status = 'failed';
              statusText.textContent = 'Failed: ' + (pollData.error || 'Unknown error');
              reject(new Error(pollData.error));
            }
          } catch (e) {
            clearInterval(interval);
            reject(e);
          }
        }, 1200);
      });
    } catch (e) {
      statusText.textContent = 'Error: ' + e.message;
    }
  }

  function renderBatchResults(result) {
    state.activeBatchResults = result;
    batchResultsSection.style.display = 'block';
    batchTranscriptView.innerHTML = '';

    if (result.segments && result.segments.length > 0) {
      result.segments.forEach(seg => {
        appendTranscriptLine(batchTranscriptView, seg);
      });
    } else {
      batchTranscriptView.innerHTML = `<p style="padding: 12px; color: #9ca3af;">${escapeHtml(result.formatted_transcript || result.clean_text)}</p>`;
    }
  }

  btnCopyBatch.addEventListener('click', () => {
    if (!state.activeBatchResults) return alert('No batch results available.');
    navigator.clipboard.writeText(state.activeBatchResults.formatted_transcript).then(() => {
      alert('Batch transcript copied to clipboard!');
    });
  });

  setupDropdown(btnExportBatch, exportDropdownBatch, () => {
    return state.activeBatchResults ? state.activeBatchResults.segments : [];
  });

  // ----------------------------------------------------
  // 6. Custom API Modal (Single API Configuration)
  // ----------------------------------------------------
  btnCustomApiModal.addEventListener('click', async () => {
    customApiModal.classList.add('active');
    testFeedback.style.display = 'none';
    try {
      const res = await fetch('/api/custom_api');
      if (res.ok) {
        const cfg = await res.json();
        apiEnabledCheckbox.checked = !!cfg.enabled;
        apiName.value = cfg.name || '';
        apiProviderType.value = cfg.provider_type || 'openai_compatible';
        apiBaseUrl.value = cfg.base_url || '';
        apiModelName.value = cfg.model_name || 'whisper-large-v3-turbo';
        if (cfg.masked_key) {
          apiMaskedHint.textContent = `Saved Key: ${cfg.masked_key}`;
        } else {
          apiMaskedHint.textContent = 'No key configured.';
        }
      }
    } catch (e) {
      console.warn(e);
    }
  });

  btnCloseModal.addEventListener('click', () => customApiModal.classList.remove('active'));

  btnTestApi.addEventListener('click', async () => {
    testFeedback.style.display = 'block';
    testFeedback.className = 'test-feedback';
    testFeedback.textContent = 'Testing connection...';

    // Temporarily save to test
    const payload = {
      enabled: apiEnabledCheckbox.checked,
      name: apiName.value || 'Custom API',
      provider_type: apiProviderType.value,
      base_url: apiBaseUrl.value,
      api_key: apiKey.value || undefined,
      model_name: apiModelName.value
    };

    try {
      await fetch('/api/custom_api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const testRes = await fetch('/api/custom_api/test', { method: 'POST' });
      const testData = await testRes.json();

      if (testData.ok) {
        testFeedback.className = 'test-feedback ok';
        testFeedback.textContent = `✓ ${testData.message}`;
      } else {
        testFeedback.className = 'test-feedback err';
        testFeedback.textContent = `✗ ${testData.message}`;
      }
    } catch (e) {
      testFeedback.className = 'test-feedback err';
      testFeedback.textContent = `✗ Error: ${e.message}`;
    }
  });

  btnSaveApi.addEventListener('click', async () => {
    const payload = {
      enabled: apiEnabledCheckbox.checked,
      name: apiName.value || 'Custom API',
      provider_type: apiProviderType.value,
      base_url: apiBaseUrl.value,
      api_key: apiKey.value,
      model_name: apiModelName.value
    };

    try {
      const res = await fetch('/api/custom_api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        alert('Custom API configuration saved successfully!');
        customApiModal.classList.remove('active');
        fetchSystemStatus();
      }
    } catch (e) {
      alert('Error saving API: ' + e.message);
    }
  });

  // ----------------------------------------------------
  // Helpers
  // ----------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function setupDropdown(btn, dropdown, getSegmentsFn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const parent = btn.parentElement;
      parent.classList.toggle('open');
    });

    document.addEventListener('click', () => {
      document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('open'));
    });

    dropdown.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const format = link.getAttribute('data-format');
        const segments = getSegmentsFn();
        exportFile(segments, format);
      });
    });
  }

  function exportFile(segments, format) {
    if (!segments || segments.length === 0) {
      return alert('No transcript segments available to export.');
    }

    let content = '';
    let mimeType = 'text/plain';
    let ext = 'txt';

    if (format === 'txt') {
      content = segments.map(s => `${s.timestamp} ${s.speaker}: ${s.text}`).join('\n');
      ext = 'txt';
    } else if (format === 'srt') {
      content = segments.map((s, idx) => {
        const start = formatSecondsSrt(s.start);
        const end = formatSecondsSrt(s.end);
        return `${idx + 1}\n${start} --> ${end}\n[${s.speaker}] ${s.text}\n`;
      }).join('\n');
      ext = 'srt';
    } else if (format === 'vtt') {
      content = 'WEBVTT\n\n' + segments.map((s, idx) => {
        const start = formatSecondsVtt(s.start);
        const end = formatSecondsVtt(s.end);
        return `${idx + 1}\n${start} --> ${end}\n<v ${s.speaker}>${s.text}\n`;
      }).join('\n');
      ext = 'vtt';
    } else if (format === 'json') {
      content = JSON.stringify(segments, null, 2);
      mimeType = 'application/json';
      ext = 'json';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript_${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function formatSecondsSrt(sec) {
    const s = Math.max(0, Number(sec) || 0);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sc = Math.floor(s % 60);
    const ms = Math.floor((s - Math.floor(s)) * 1000);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sc).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
  }

  function formatSecondsVtt(sec) {
    const s = Math.max(0, Number(sec) || 0);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sc = Math.floor(s % 60);
    const ms = Math.floor((s - Math.floor(s)) * 1000);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sc).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  }

  // Initial Fetch
  fetchSystemStatus();
});
