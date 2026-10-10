/* ==========================================================================
   Apertus Invoice Assistant - Main JavaScript (v5 CLEAN)
   Author: Anio Joseph
   Project: Hack Apertus 2026
   ========================================================================== */

console.log('[APERTUS] chat.js loading...');

/* --------------------------------------------------------------------------
   1. INTRO ANIMATION
   -------------------------------------------------------------------------- */

(function introAnimation() {
  const intro = document.getElementById('intro');
  const app = document.getElementById('app');
  if (!intro || !app) return;

  setTimeout(() => {
    intro.classList.add('fade-out');
    app.classList.add('visible');
    setTimeout(() => intro.classList.add('hidden'), 900);
  }, 4200);
})();

/* --------------------------------------------------------------------------
   2. THEME TOGGLE
   -------------------------------------------------------------------------- */

(function themeToggle() {
  const toggle = document.getElementById('theme-toggle');
  const icon = toggle ? toggle.querySelector('.theme-icon') : null;
  if (!toggle || !icon) return;

  const THEMES = ['dark', 'light', 'blue-flame'];
  const ICONS = { 'dark': 'ðŸŒ™', 'light': 'â˜€ï¸', 'blue-flame': 'ðŸ’™' };
  const CLASSES = ['light-mode', 'blue-flame'];

  let currentIndex = THEMES.indexOf(localStorage.getItem('apertus-theme') || 'dark');
  if (currentIndex === -1) currentIndex = 0;

  function applyTheme(theme) {
    document.body.classList.remove(...CLASSES);
    if (theme === 'light') document.body.classList.add('light-mode');
    if (theme === 'blue-flame') document.body.classList.add('blue-flame');
    icon.textContent = ICONS[theme];
    localStorage.setItem('apertus-theme', theme);
  }

  applyTheme(THEMES[currentIndex]);

  toggle.addEventListener('click', () => {
    currentIndex = (currentIndex + 1) % THEMES.length;
    applyTheme(THEMES[currentIndex]);
  });
})();

/* --------------------------------------------------------------------------
   3. LATENCY MONITOR (fake, for UI effect)
   -------------------------------------------------------------------------- */

(function latencyMonitor() {
  const el = document.getElementById('latency');
  if (!el) return;
  function update() {
    const ms = Math.floor(200 + Math.random() * 800);
    el.textContent = ms + 'ms';
    el.style.color = ms < 500 ? '#4ade80' : (ms < 800 ? '#ffcc00' : '#ff6b00');
  }
  update();
  setInterval(update, 2500);
})();

/* --------------------------------------------------------------------------
   4. CHAT + UPLOAD + REPORT (main logic)
   -------------------------------------------------------------------------- */

document.addEventListener('DOMContentLoaded', () => {
  console.log('[APERTUS] DOMContentLoaded, initializing chat logic');

  const chat = document.getElementById('chat');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const fileInput = document.getElementById('file-input');
  const filePreview = document.getElementById('file-preview');
  const fileNameEl = document.getElementById('file-name');
  const fileSizeEl = document.getElementById('file-size');
  const removeFileBtn = document.getElementById('remove-file');

  if (!chat || !input || !sendBtn) {
    console.error('[APERTUS] Missing critical elements:', {
      chat: !!chat, input: !!input, sendBtn: !!sendBtn
    });
    return;
  }

  console.log('[APERTUS] All elements found');

  let currentFile = null;

  // --- Helpers ---
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function addMessage(text, role) {
    const msg = document.createElement('div');
    msg.className = 'message ' + role;
    const avatarLabel = role === 'user' ? 'ME' : 'AI';
    const safe = escapeHtml(String(text)).replace(/\n/g, '<br>');
    msg.innerHTML = `
      <div class="avatar">${avatarLabel}</div>
      <div class="bubble">${safe}</div>
    `;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
    return msg;
  }

  function showTyping() {
    const t = document.createElement('div');
    t.className = 'message agent';
    t.id = 'typing';
    t.innerHTML = `
      <div class="avatar">AI</div>
      <div class="bubble"><div class="bubble-title">PROCESSING</div>Analyzing your request... (up to 60 seconds)</div>
    `;
    chat.appendChild(t);
    chat.scrollTop = chat.scrollHeight;
  }

  function hideTyping() {
    const t = document.getElementById('typing');
    if (t) t.remove();
  }

  function showDownloadButton(analysisId) {
    // Remove any existing button
    const existing = document.getElementById('download-report-btn');
    if (existing) existing.remove();

    const wrapper = document.createElement('div');
    wrapper.id = 'download-report-btn';
    wrapper.className = 'message agent';
    wrapper.innerHTML = `
      <div class="avatar">AI</div>
      <div class="bubble">
        <div class="bubble-title">REPORT READY</div>
        <p style="margin:6px 0 12px;">A detailed PDF report has been generated for this analysis.</p>
        <a href="/api/report/${analysisId}.pdf" target="_blank" rel="noopener"
           class="download-report-link"
           style="display:inline-flex;align-items:center;gap:8px;background:#e30613;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600;">
          Download PDF Report
        </a>
      </div>
    `;
    chat.appendChild(wrapper);
    chat.scrollTop = chat.scrollHeight;
    console.log('[APERTUS] Download button shown for:', analysisId);

    // Attach a click handler on the download link -> reset the app
    const link = wrapper.querySelector('.download-report-link');
    if (link) {
      link.addEventListener('click', () => {
        console.log('[APERTUS] Download clicked, scheduling reset...');
        // Wait a short delay to let the download start
        setTimeout(() => resetApp(), 800);
      });
    }
  }

  function resetApp() {
    console.log('[APERTUS] Resetting app for next document');

    // 1. Clear the chat (keep only the initial welcome message if any)
    const messages = chat.querySelectorAll('.message');
    messages.forEach((msg, idx) => {
      // Skip the very first welcome message
      if (idx === 0 && msg.classList.contains('agent') && msg.querySelector('.bubble-title')?.textContent === 'SYSTEM READY') {
        return;
      }
      msg.remove();
    });

    // 2. Remove any lingering typing indicator
    hideTyping();

    // 3. Remove any lingering download button
    const btn = document.getElementById('download-report-btn');
    if (btn) btn.remove();

    // 4. Clear file input / preview
    clearFile();

    // 5. Clear input
    input.value = '';
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();

    // 6. Show a reset confirmation message
    const resetMsg = document.createElement('div');
    resetMsg.className = 'message agent';
    resetMsg.innerHTML = `
      <div class="avatar">AI</div>
      <div class="bubble">
        <div class="bubble-title">READY</div>
        Ready for the next document. You can paste a new invoice, type a message, or upload a file (paperclip).
      </div>
    `;
    chat.appendChild(resetMsg);
    chat.scrollTop = chat.scrollHeight;
  }

  // --- File selection ---
  function selectFile(file) {
    currentFile = file;
    const sizeKb = (file.size / 1024).toFixed(1);
    if (fileNameEl) fileNameEl.textContent = file.name;
    if (fileSizeEl) fileSizeEl.textContent = '(' + sizeKb + ' KB)';
    if (filePreview) filePreview.classList.add('visible');
    console.log('[APERTUS] File selected:', file.name);
  }

  function clearFile() {
    currentFile = null;
    if (fileInput) fileInput.value = '';
    if (filePreview) filePreview.classList.remove('visible');
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) selectFile(file);
    });
  }

  if (removeFileBtn) {
    removeFileBtn.addEventListener('click', clearFile);
  }

  // --- Main send handler ---
  async function handleSend() {
    console.log('[APERTUS] handleSend called');
    const message = input.value.trim();

    // CASE A: File pending -> upload
    if (currentFile) {
      const fileToSend = currentFile;
      clearFile();
      addMessage('Uploading: ' + fileToSend.name, 'user');
      showTyping();

      const formData = new FormData();
      formData.append('file', fileToSend);

      try {
        const res = await fetch('/upload', { method: 'POST', body: formData });
        const data = await res.json();
        hideTyping();

        if (!data.success) {
          addMessage('OCR failed: ' + (data.error || 'unknown'), 'agent');
          return;
        }
        if (!data.text || !data.text.trim()) {
          addMessage('OCR returned no text.', 'agent');
          return;
        }

        const preview = data.text.length > 500 ? data.text.substring(0, 500) + '...' : data.text;
        addMessage('Extracted text from ' + data.filename + ':\n\n' + preview, 'agent');
        await analyzeDocument(data.text);
      } catch (err) {
        hideTyping();
        addMessage('Network error: ' + err.message, 'agent');
      }
      return;
    }

    // CASE B: Regular text message
    if (!message) return;
    addMessage(message, 'user');
    input.value = '';
    await analyzeDocument(message);
  }

  async function analyzeDocument(text) {
    showTyping();
    input.disabled = true;
    sendBtn.disabled = true;

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, save_analysis: true }),
      });
      const data = await res.json();
      hideTyping();

      if (!res.ok) {
        addMessage('Error HTTP ' + res.status + ' : ' + (data.detail || JSON.stringify(data)), 'agent');
        return;
      }
      if (!data.reply || !data.reply.trim()) {
        addMessage('Error: empty reply.', 'agent');
        return;
      }

      addMessage(data.reply, 'agent');
      console.log('[APERTUS] Reply received. analysis_id =', data.analysis_id);

      if (data.analysis_id) {
        showDownloadButton(data.analysis_id);
      } else {
        console.warn('[APERTUS] No analysis_id in reply');
      }
    } catch (err) {
      hideTyping();
      addMessage('Network error: ' + err.message, 'agent');
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  // --- Attach listeners ---
  sendBtn.addEventListener('click', handleSend);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  input.focus();
  console.log('[APERTUS] Chat initialized and listeners attached');
});

/* --------------------------------------------------------------------------
   SOUND ENGINE (Web Audio API - no external files)
   -------------------------------------------------------------------------- */

(function soundEngine() {
  console.log('[SOUND] soundEngine initialized');

  const toggleBtn = document.getElementById('sound-toggle');

  // Sound state (persisted in localStorage)
  let soundEnabled = localStorage.getItem('apertus-sound') !== 'off';

  // Audio context (lazy-initialized on first user gesture)
  let audioCtx = null;

  function getCtx() {
    if (!audioCtx) {
      try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        console.warn('[SOUND] Web Audio API not available:', e);
        return null;
      }
    }
    return audioCtx;
  }

  // Generic tone player
  function playTone({ freq = 440, duration = 0.15, type = 'sine', volume = 0.15, sweep = null }) {
    if (!soundEnabled) return;
    const ctx = getCtx();
    if (!ctx) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    if (sweep) {
      osc.frequency.exponentialRampToValueAtTime(sweep, ctx.currentTime + duration);
    }

    gain.gain.setValueAtTime(volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + duration);
  }

  // --- Sound effects ---
  const SOUNDS = {
    send:    () => playTone({ freq: 660, duration: 0.08, type: 'sine', volume: 0.12, sweep: 880 }),
    receive: () => playTone({ freq: 880, duration: 0.10, type: 'sine', volume: 0.10, sweep: 1046 }),
    success: () => {
      playTone({ freq: 523, duration: 0.10, type: 'sine', volume: 0.12 });
      setTimeout(() => playTone({ freq: 659, duration: 0.10, type: 'sine', volume: 0.12 }), 100);
      setTimeout(() => playTone({ freq: 784, duration: 0.15, type: 'sine', volume: 0.12 }), 200);
    },
    alert:   () => {
      playTone({ freq: 440, duration: 0.15, type: 'square', volume: 0.08 });
      setTimeout(() => playTone({ freq: 330, duration: 0.20, type: 'square', volume: 0.08 }), 160);
    },
    critical: () => {
      for (let i = 0; i < 3; i++) {
        setTimeout(() => playTone({ freq: 880, duration: 0.08, type: 'square', volume: 0.10 }), i * 150);
      }
    },
  };

  // Expose the sound API globally so chat.js can trigger sounds
  window.ApertusSound = SOUNDS;

  // --- Toggle button ---
  function updateToggleUI() {
    if (!toggleBtn) return;
    if (soundEnabled) {
      toggleBtn.textContent = '🔊';
      toggleBtn.classList.remove('muted');
      toggleBtn.title = 'Sound: ON (click to mute)';
    } else {
      toggleBtn.textContent = '🔇';
      toggleBtn.classList.add('muted');
      toggleBtn.title = 'Sound: OFF (click to enable)';
    }
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      soundEnabled = !soundEnabled;
      localStorage.setItem('apertus-sound', soundEnabled ? 'on' : 'off');
      updateToggleUI();
      if (soundEnabled) playTone({ freq: 880, duration: 0.1, type: 'sine', volume: 0.12 });
    });
  }

  updateToggleUI();

  // Resume audio on first user gesture (browsers require this)
  document.addEventListener('click', () => {
    const ctx = getCtx();
    if (ctx && ctx.state === 'suspended') ctx.resume();
  }, { once: true });

  // --- Hook into the chat flow ---
  // 1. Send sound when user submits
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && document.activeElement === document.getElementById('input')) {
      SOUNDS.send();
    }
  });

  const sendBtn = document.getElementById('send');
  if (sendBtn) {
    sendBtn.addEventListener('click', () => SOUNDS.send());
  }

  // 2. Override fetch to detect responses
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const url = typeof args[0] === 'string' ? args[0] : '';
    const response = await originalFetch.apply(this, args);

    // Sound on /chat response
    if (url.endsWith('/chat') && response.ok) {
      const cloned = response.clone();
      cloned.json().then((data) => {
        if (data && data.reply) {
          SOUNDS.receive();
          // Detect fraud level in reply
          const text = data.reply.toLowerCase();
          if (text.includes('critical') || text.includes('escalat')) {
            setTimeout(() => SOUNDS.critical(), 300);
          } else if (text.includes('high') || text.includes('alert')) {
            setTimeout(() => SOUNDS.alert(), 300);
          }
        }
      }).catch(() => {});
    }

    // Sound on PDF download click
    if (url.includes('/api/report/') && response.ok) {
      SOUNDS.success();
    }

    return response;
  };
})();
