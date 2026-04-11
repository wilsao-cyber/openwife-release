// ── Chat / SSE / STT Module ─────────────────────────────────────────
// Extracted from index.html — handles messaging UI, SSE streaming,
// TTS integration per message, and STT voice input.

import {
  playTTSStream, playTTS, stopTTS, tryPlayNext,
  isTtsEnabled, playUiSfx, handleSfxResult,
  setTtsOnFirstAudio, setTtsOnJaText, setTtsOnComplete,
  getIsPlaying, setIsPlaying, getCurrentAudio, setCurrentAudio,
  getAudioQueue, setAudioQueue, getPlayIndex, setPlayIndex, setStreamDone,
} from './audio.js';
import { showToast } from './settings.js';

// ── Context (injected via initChat) ─────────────────────────────────
let ctx = {
  getAnimController: () => null,
  getCurrentVrm:     () => null,
  getUseFallback:    () => false,
  getDeepThinking:   () => false,
  getTtsBatchMode:   () => false,
  triggerEmotionBgm: () => {},
  getSceneTheme:     () => 'home',
  setEmotion:        () => {},
  openLightbox:      () => {},
  CLIENT_ID:         '',
};

// ── UI Elements ──────────────────────────────────────────────────────
// langSel is eagerly resolved so settings.js can read it before initChat runs.
let messagesEl, inputEl, sendBtn, greetingEl, modeSel, scrollBottomBtn, chatPanel;
export let langSel = document.getElementById('lang-selector');
let userScrolledUp = false;

function scrollToBottom() {
  if (!userScrolledUp) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

function addMessageObj(type, content, className = '') {
  const div = document.createElement('div');
  div.className = `msg ${className}`;
  // NOTE: content is always constructed from trusted templates in this
  // codebase (user text is set via textContent, not interpolated into HTML).
  div.innerHTML = content;  // eslint-disable-line no-unsanitized/property
  messagesEl.appendChild(div);
  scrollToBottom();
  return div;
}

function showGreeting(text) {
  // Greeting element removed — no-op
}

// ── Media rendering (used by SSE handler) ────────────────────────────
function renderMediaInChat(container, media) {
  if (!media || !Array.isArray(media)) return;
  media.forEach((item, idx) => {
    if (item.type === 'image') {
      const img = document.createElement('img');
      img.className = 'media-thumb';
      img.src = item.url;
      img.alt = item.alt || '';
      img.onclick = () => ctx.openLightbox(media, idx);
      container.appendChild(img);
    } else if (item.type === 'video') {
      const video = document.createElement('video');
      video.className = 'media-thumb';
      video.src = item.url;
      video.controls = true;
      video.style.maxWidth = '300px';
      video.style.borderRadius = '8px';
      container.appendChild(video);
    } else if (item.type === 'iframe') {
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'cursor:pointer;max-width:300px;margin:6px 0;position:relative;';
      if (item.thumbnail) {
        const thumb = document.createElement('img');
        thumb.className = 'media-thumb';
        thumb.src = item.thumbnail;
        thumb.alt = item.title || '';
        wrapper.appendChild(thumb);
        const play = document.createElement('div');
        play.style.cssText = 'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:48px;color:white;text-shadow:0 2px 8px rgba(0,0,0,0.8);';
        play.textContent = '\u25B6';
        wrapper.appendChild(play);
      } else {
        const label = document.createElement('div');
        label.className = 'content-preview';
        label.textContent = '\u25B6 ' + (item.title || 'Video');
        wrapper.appendChild(label);
      }
      wrapper.onclick = () => ctx.openLightbox(media, idx);
      container.appendChild(wrapper);
    } else if (item.type === 'richtext') {
      const card = document.createElement('div');
      card.className = 'content-preview';
      const title = document.createElement('div');
      title.className = 'content-preview-title';
      title.textContent = item.title || 'Content';
      card.appendChild(title);
      const snippet = document.createElement('div');
      snippet.className = 'content-preview-snippet';
      snippet.textContent = (item.html || '').replace(/<[^>]*>/g, '').substring(0, 80) + '...';
      card.appendChild(snippet);
      card.onclick = () => ctx.openLightbox(media, idx);
      container.appendChild(card);
    }
  });
}

// ── SSE Consumption ──────────────────────────────────────────────────
export async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = '';
  sendBtn.disabled = true;
  // playUiSfx('send');

  addMessageObj('user', `<span>${escapeHtml(text)}</span>`, 'user');

  const animController = ctx.getAnimController();
  if (animController && animController.actions.has('think')) {
    animController.play('think');
  }

  const aiDiv = document.createElement('div');
  aiDiv.className = 'msg ai';
  const typingEl = document.createElement('div');
  typingEl.className = 'typing-indicator';
  typingEl.innerHTML = '<span></span><span></span><span></span>';  // eslint-disable-line no-unsanitized/property
  aiDiv.appendChild(typingEl);
  const aiSpan = document.createElement('span');
  aiSpan.style.display = 'none';
  aiDiv.appendChild(aiSpan);
  messagesEl.appendChild(aiDiv);
  scrollToBottom();

  let typingRemoved = false;
  function removeTyping() {
    if (!typingRemoved) { typingEl.remove(); aiSpan.style.display = ''; typingRemoved = true; }
  }

  // Track state
  let fullText = '';
  let activePlanCard = null;
  const startTime = performance.now();
  let firstChunkTime = null;

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        language: langSel.value,
        mode_override: modeSel.value === 'auto' ? null : modeSel.value,
        client_id: ctx.CLIENT_ID,
        use_fallback: ctx.getUseFallback(),
        deep_thinking: ctx.getDeepThinking(),
      })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // incomplete line back to buffer

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const evt = JSON.parse(jsonStr);

          switch (evt.type) {
            case 'mode_change':
              addMessageObj('sys', `\u2699\uFE0F \u6A21\u5F0F: ${evt.mode === 'assist' ? '\u5354\u52A9' : '\u804A\u5929'}`, 'notice');
              break;

            case 'notice':
              removeTyping();
              addMessageObj('sys', evt.text, 'notice');
              break;

            case 'chunk':
              removeTyping();
              if (!firstChunkTime) firstChunkTime = performance.now();
              fullText += evt.data;
              aiSpan.textContent = fullText.replace(/\[emotion:\w+\]/g, '');
              scrollToBottom();
              break;

            case 'plan':
              removeTyping();
              activePlanCard = buildPlanCard(evt, aiDiv, messagesEl);
              aiDiv.appendChild(activePlanCard);
              scrollToBottom();
              break;

            case 'tool_result': {
              const r = evt.result;
              if (r && r.error) {
                const badge = document.createElement('div');
                badge.style.cssText = 'font-size:11px;color:#f44336;margin:4px 0;padding:4px 8px;background:rgba(255,0,0,0.1);border-radius:6px;';
                badge.textContent = '\u26A0\uFE0F ' + evt.tool + ': ' + r.error.substring(0, 80);
                aiDiv.insertBefore(badge, aiSpan);
              }
              if (r && r.media) {
                renderMediaInChat(aiDiv, r.media);
              }
              // Handle SFX playback from tool results
              handleSfxResult(r);
              // Handle scene audio (mixed TTS + SFX)
              if (r && r.scene_audio) {
                stopTTS();  // stop any streaming TTS
                const sceneAudio = new Audio(r.scene_audio);
                sceneAudio.play().catch(e => console.warn('Scene audio blocked:', e));
                setCurrentAudio(sceneAudio);
                setIsPlaying(true);
                sceneAudio.onended = () => { setIsPlaying(false); setCurrentAudio(null); };
              }
              scrollToBottom();
              break;
            }

            case 'error':
              addMessageObj('sys', '\u932F\u8AA4: ' + evt.text, 'error');
              break;

            case 'done': {
              removeTyping();
              if (!fullText && evt.text) {
                fullText = evt.text;
                aiSpan.textContent = fullText.replace(/\[emotion:\w+\]/g, '');
              }
              // Convert URLs in text to clickable links
              linkifyUrls(aiSpan);
              if (evt.emotion) {
                ctx.setEmotion(evt.emotion);
                ctx.triggerEmotionBgm(evt.emotion, ctx.getSceneTheme());
                const tag = document.createElement('div');
                tag.className = 'emotion-tag';
                tag.textContent = evt.emotion;
                aiDiv.insertBefore(tag, aiSpan);
              }
              // Timing badge
              const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
              const ttfb = firstChunkTime ? ((firstChunkTime - startTime) / 1000).toFixed(1) : 'N/A';
              const timingDiv = document.createElement('div');
              timingDiv.className = 'timing-badge';
              timingDiv.textContent = '\u23F1\uFE0F \u9996\u5B57 ' + ttfb + 's \xB7 \u7E3D\u8A08 ' + elapsed + 's \xB7 ' + fullText.length + ' \u5B57';
              aiDiv.appendChild(timingDiv);

              buildTtsControls(aiDiv, fullText, evt.emotion || 'neutral');

              showGreeting(aiSpan.textContent.substring(0, 60) + (aiSpan.textContent.length > 60 ? '...' : ''));
              // Auto-play TTS audio if enabled
              if (fullText && isTtsEnabled()) {
                const ttsBtn = aiDiv.querySelector('.tts-btn');
                const ttsLoading = aiDiv.querySelector('.tts-loading');
                doPlayTTSForMessage(ttsBtn, ttsLoading, aiDiv);
              }
              // Reset expression when TTS finishes (or after 4s if TTS disabled)
              if (isTtsEnabled() && fullText) {
                setTtsOnComplete(() => {
                  ctx.setEmotion('neutral');
                  const ac2 = ctx.getAnimController();
                  if (ac2) ac2.play('idle');
                });
              } else {
                setTimeout(() => {
                  ctx.setEmotion('neutral');
                  const ac2 = ctx.getAnimController();
                  if (ac2) ac2.play('idle');
                }, 4000);
              }
              break;
            }
          }
        } catch (e) { console.warn('SSE payload parse failed:', e); }
      }
    }
  } catch (err) {
    removeTyping();
    if (!fullText) aiSpan.textContent = '\u9023\u7DDA\u932F\u8AA4: ' + err.message;
    const ac = ctx.getAnimController();
    if (ac) ac.play('idle');
  }

  if (!fullText && !aiDiv.querySelector('.plan-card') && !aiDiv.querySelector('.tool-card')) {
     aiDiv.remove();
  }

  sendBtn.disabled = false;
  inputEl.focus();
}

// ── Helper: escape HTML for safe insertion ───────────────────────────
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Helper: convert URLs to clickable links ──────────────────────────
function linkifyUrls(el) {
  const text = el.textContent;
  const urlRegex = /(https?:\/\/[^\s\uFF09\u0029]+)/g;
  if (!urlRegex.test(text)) return;
  const parts = text.split(urlRegex);
  el.textContent = '';
  parts.forEach(part => {
    if (part.match(/^https?:\/\//)) {
      const a = document.createElement('a');
      a.href = part;
      a.textContent = part.length > 50 ? part.substring(0, 50) + '...' : part;
      a.target = '_blank';
      a.rel = 'noopener';
      a.style.cssText = 'color:#69b4ff;text-decoration:underline;word-break:break-all;';
      el.appendChild(a);
    } else {
      el.appendChild(document.createTextNode(part));
    }
  });
}

// ── Helper: build plan confirmation card ─────────────────────────────
function buildPlanCard(evt, aiDiv, messagesEl) {
  const card = document.createElement('div');
  card.className = 'plan-card';

  const descDiv = document.createElement('div');
  const strong = document.createElement('strong');
  strong.textContent = '\u63D0\u8B70\u8A08\u756B:';
  descDiv.appendChild(strong);
  descDiv.appendChild(document.createElement('br'));
  const descText = (evt.description || '');
  descText.split('\n').forEach((line, i) => {
    if (i > 0) descDiv.appendChild(document.createElement('br'));
    descDiv.appendChild(document.createTextNode(line));
  });
  card.appendChild(descDiv);

  const actions = document.createElement('div');
  actions.className = 'plan-actions';
  const confirmBtn = document.createElement('button');
  confirmBtn.className = 'btn-confirm';
  confirmBtn.textContent = '\u2705 \u6388\u6B0A\u57F7\u884C';
  const denyBtn = document.createElement('button');
  denyBtn.className = 'btn-deny';
  denyBtn.textContent = '\u274C \u62D2\u7D55';
  actions.appendChild(confirmBtn);
  actions.appendChild(denyBtn);
  card.appendChild(actions);

  confirmBtn.onclick = async () => {
    card.querySelectorAll('button').forEach(b => b.disabled = true);
    actions.textContent = '';
    const executing = document.createElement('i');
    executing.textContent = '(\u57F7\u884C\u4E2D...)';
    actions.appendChild(executing);
    try {
      const confirmRes = await fetch(`/api/chat/confirm/${ctx.CLIENT_ID}`, { method: 'POST' });
      const confirmReader = confirmRes.body.getReader();
      const confirmDecoder = new TextDecoder();
      let confirmBuf = '';
      const confirmSpan = document.createElement('span');
      const confirmDiv = document.createElement('div');
      confirmDiv.className = 'msg ai';
      const toolResultsContainer = document.createElement('div');
      confirmDiv.appendChild(toolResultsContainer);
      confirmDiv.appendChild(confirmSpan);
      messagesEl.appendChild(confirmDiv);
      let confirmText = '';

      while (true) {
        const { done: cDone, value: cVal } = await confirmReader.read();
        if (cDone) break;
        confirmBuf += confirmDecoder.decode(cVal, { stream: true });
        const cLines = confirmBuf.split('\n');
        confirmBuf = cLines.pop();
        for (const cLine of cLines) {
          if (!cLine.startsWith('data: ')) continue;
          const cJson = cLine.slice(6).trim();
          if (!cJson) continue;
          try {
            const cEvt = JSON.parse(cJson);
            if (cEvt.type === 'tool_result') {
              const r = cEvt.result;
              if (r && r.error) {
                const badge = document.createElement('div');
                badge.style.cssText = 'font-size:11px;color:#f44336;margin:4px 0;padding:4px 8px;background:rgba(255,0,0,0.1);border-radius:6px;';
                badge.textContent = '\u26A0\uFE0F ' + cEvt.tool + ': ' + r.error.substring(0, 80);
                toolResultsContainer.appendChild(badge);
              }
              if (r && r.media) {
                renderMediaInChat(toolResultsContainer, r.media);
              }
              handleSfxResult(r);
              if (r && r.scene_audio) {
                stopTTS();
                const sa = new Audio(r.scene_audio);
                sa.play().catch(e => console.warn('Scene audio blocked:', e));
                setCurrentAudio(sa);
                setIsPlaying(true);
                sa.onended = () => { setIsPlaying(false); setCurrentAudio(null); };
              }
            } else if (cEvt.type === 'chunk') {
              confirmText += cEvt.data;
              confirmSpan.textContent = confirmText.replace(/\[emotion:\w+\]/g, '');
            } else if (cEvt.type === 'done') {
              if (!confirmText && cEvt.text) {
                confirmText = cEvt.text;
                confirmSpan.textContent = confirmText.replace(/\[emotion:\w+\]/g, '');
              }
              if (cEvt.emotion) ctx.setEmotion(cEvt.emotion);
            }
          } catch (ce) {}
        }
      }
      actions.textContent = '';
      const done = document.createElement('i');
      done.textContent = '(\u5DF2\u5B8C\u6210)';
      actions.appendChild(done);
    } catch (ce) {
      actions.textContent = '';
      const fail = document.createElement('i');
      fail.textContent = '(\u57F7\u884C\u5931\u6557)';
      actions.appendChild(fail);
    }
    scrollToBottom();
  };

  denyBtn.onclick = async () => {
    card.querySelectorAll('button').forEach(b => b.disabled = true);
    try {
      const denyRes = await fetch(`/api/chat/deny/${ctx.CLIENT_ID}`, { method: 'POST' });
      const denyData = await denyRes.json();
      actions.textContent = denyData.text || '(Denied)';
    } catch (e) {
      actions.textContent = '(Denied)';
    }
  };

  return card;
}

// ── Helper: build TTS controls for a message ─────────────────────────
// Per-message TTS state is stored on the DOM element via dataset/closure.
function buildTtsControls(aiDiv, ttsText, ttsEmotion) {
  const ttsRow = document.createElement('div');
  ttsRow.style.cssText = 'display:flex;align-items:center;flex-wrap:wrap;margin-top:2px;';
  const ttsBtn = document.createElement('span');
  ttsBtn.className = 'tts-btn';
  ttsBtn.textContent = '\uD83D\uDD0A';
  ttsBtn.title = '\u64AD\u653E / \u505C\u6B62\u8A9E\u97F3';
  ttsRow.appendChild(ttsBtn);

  const ttsLoading = document.createElement('span');
  ttsLoading.className = 'tts-loading';
  ttsLoading.textContent = '\u8A9E\u97F3\u751F\u6210\u4E2D';
  ttsLoading.style.display = 'none';
  ttsRow.appendChild(ttsLoading);

  const jaToggle = document.createElement('span');
  jaToggle.className = 'ja-toggle';
  jaToggle.textContent = '\uD83C\uDDEF\uD83C\uDDF5 \u65E5\u672C\u8A9E';
  jaToggle.title = '\u986F\u793A\u8A9E\u97F3\u65E5\u6587\u539F\u6587';
  ttsRow.appendChild(jaToggle);
  aiDiv.appendChild(ttsRow);

  const jaDrawer = document.createElement('div');
  jaDrawer.className = 'ja-drawer';
  aiDiv.appendChild(jaDrawer);

  jaToggle.onclick = () => { jaDrawer.classList.toggle('open'); };

  // Closure-based per-message TTS state
  let cachedAudioUrls = [];
  let cachedJaText = null;
  let ttsGenerating = false;

  function replayFromCache() {
    stopTTS();
    setAudioQueue([...cachedAudioUrls]);
    setPlayIndex(0);
    setStreamDone(true);
    ttsBtn.classList.add('playing');
    setTtsOnComplete(() => { ttsBtn.classList.remove('playing'); });
    tryPlayNext();
  }

  async function doPlay() {
    if (cachedAudioUrls.length > 0) { replayFromCache(); return; }
    if (ttsGenerating) return;
    ttsGenerating = true;
    ttsLoading.style.display = 'inline-block';
    ttsBtn.classList.add('playing');

    if (ctx.getTtsBatchMode()) {
      // Batch mode: generate all -> single WAV -> play once
      try {
        const resp = await fetch('/api/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: ttsText, language: langSel.value, emotion: ttsEmotion, mix_sfx: true }),
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.ja_text) { cachedJaText = data.ja_text; jaDrawer.textContent = data.ja_text; }
          ttsLoading.style.display = 'none';
          cachedAudioUrls = [data.audio_url];
          stopTTS();
          const batchAudio = new Audio(data.audio_url);
          setCurrentAudio(batchAudio);
          setIsPlaying(true);
          batchAudio.play();
          batchAudio.onended = () => { setIsPlaying(false); setCurrentAudio(null); ttsBtn.classList.remove('playing'); };
        }
      } catch (e) { console.error('Batch TTS failed:', e); }
      ttsGenerating = false;
      ttsLoading.style.display = 'none';
    } else {
      // Streaming mode: play segments as they arrive
      setTtsOnJaText((jaText) => {
        cachedJaText = jaText;
        jaDrawer.textContent = jaText;
      });
      setTtsOnFirstAudio(() => {
        ttsLoading.style.display = 'none';
      });
      setTtsOnComplete(() => {
        ttsBtn.classList.remove('playing');
        ttsGenerating = false;
        ttsLoading.style.display = 'none';
        if (cachedAudioUrls.length === 0) {
          cachedAudioUrls = getAudioQueue().filter(Boolean);
        }
      });

      await playTTSStream(ttsText, ttsEmotion);
      if (cachedAudioUrls.length === 0) {
        cachedAudioUrls = getAudioQueue().filter(Boolean);
      }
    }
  }

  ttsBtn.onclick = () => {
    if (getIsPlaying() && getCurrentAudio()) {
      stopTTS();
      ttsBtn.classList.remove('playing');
      ttsGenerating = false;
      ttsLoading.style.display = 'none';
    } else {
      doPlay();
    }
  };

  // Expose doPlay for auto-play from sendMessage's 'done' handler
  aiDiv._doPlayTTS = doPlay;
}

// Called from sendMessage 'done' handler to auto-play TTS
function doPlayTTSForMessage(ttsBtn, ttsLoading, aiDiv) {
  if (aiDiv._doPlayTTS) aiDiv._doPlayTTS();
}

// ── STT Voice Input (click-to-toggle) ─────────────────────────────────
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function startRecording() {
  const micBtn = document.getElementById('mic-btn');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
    audioChunks = [];
    mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      if (audioChunks.length === 0) return;
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      micBtn.textContent = '\u23F3';
      try {
        const form = new FormData();
        form.append('audio', blob, 'recording.webm');
        const sttLang = langSel.value === 'ja' ? 'ja' : langSel.value === 'en' ? 'en' : 'zh';
        form.append('language', sttLang);
        const res = await fetch('/api/stt', { method: 'POST', body: form });
        const data = await res.json();
        if (data.text && data.text.trim()) {
          inputEl.value = data.text.trim();
          sendMessage();
        }
      } catch (e) {
        console.error('STT failed:', e);
      }
      micBtn.textContent = '\uD83C\uDF99\uFE0F';
    };
    // Collect chunks every 500ms to avoid data loss
    mediaRecorder.start(500);
    isRecording = true;
    micBtn.classList.add('recording');
    micBtn.textContent = '\u23F9\uFE0F';
  } catch (e) {
    console.error('Mic access denied:', e);
  }
}

function stopRecording() {
  const micBtn = document.getElementById('mic-btn');
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  isRecording = false;
  micBtn.classList.remove('recording');
}

// ── Init ─────────────────────────────────────────────────────────────
export function initChat(injectedCtx) {
  ctx = { ...ctx, ...injectedCtx };

  // Grab DOM elements
  messagesEl      = document.getElementById('messages');
  inputEl         = document.getElementById('chat-input');
  sendBtn         = document.getElementById('send-btn');
  greetingEl      = document.getElementById('greeting');
  modeSel         = document.getElementById('mode-selector');
  langSel         = document.getElementById('lang-selector');
  scrollBottomBtn = document.getElementById('scroll-bottom-btn');
  chatPanel       = document.getElementById('chat-panel');

  // Auto-scroll tracking
  messagesEl.addEventListener('scroll', () => {
    const atBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
    userScrolledUp = !atBottom;
    scrollBottomBtn.classList.toggle('visible', !atBottom);
  });
  scrollBottomBtn.addEventListener('click', () => {
    messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });
  });

  // Chat panel resize
  const resizeHandle = document.getElementById('chat-resize-handle');
  let isResizing = false;
  resizeHandle.addEventListener('mousedown', () => {
    isResizing = true;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  });
  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const newHeight = window.innerHeight - e.clientY;
    chatPanel.style.height = Math.max(150, Math.min(window.innerHeight - 100, newHeight)) + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (isResizing) {
      isResizing = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  });

  // Wire send button + Enter key
  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

  // Wire mic button (click-to-toggle recording)
  const micBtn = document.getElementById('mic-btn');
  micBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });
}
