// js/audio.js — BGM, Ambient, UI SFX, TTS Playback, SFX Layer
// Extracted from index.html for maintainability

// ── Audio Systems: BGM + Ambient + UI SFX ──────────────────────────
const SCENE_BGM = {
  home: '/audio-assets/bgm/kks_bgm_07.wav',
  sakura: '/audio-assets/bgm/kks_bgm_08.wav',
  fantasy: '/audio-assets/bgm/kks_bgm_16.wav',
  night: '/audio-assets/bgm/kks_bgm_15.wav',
};
const EMOTION_BGM_OVERRIDE = {
  sad: '/audio-assets/bgm/kks_bgm_17.wav',
  happy: '/audio-assets/bgm/kks_bgm_08.wav',
  horny: '/audio-assets/bgm/kks_bgm_02.wav',
};
const SCENE_AMBIENT = {
  home: null,
  sakura: '/audio-assets/se/map/se_ks_action_006.wav',
  fantasy: '/audio-assets/se/map/se_ks_action_001.wav',
  night: '/audio-assets/se/map/se_ks_action_004.wav',
};
const UI_SFX = {
  send: '/audio-assets/se/se_ks_adv_001.wav',
  receive: '/audio-assets/se/se_ks_adv_004.wav',
  select: '/audio-assets/se/se_ks_adv_000.wav',
  transition: '/audio-assets/se/se_ks_adv_005.wav',
};

let bgmAudio = null;
let bgmGain = null;
let ambientAudio = null;
let ambientGain = null;
let audioCtx = null;
let uiSfxBuffers = {};
let bgmEnabled = localStorage.getItem('ai-wife-bgm') !== 'off';
let bgmVolume = parseFloat(localStorage.getItem('ai-wife-bgm-vol') || '0.15');
let ambientVolume = 0.1;
let uiSfxEnabled = localStorage.getItem('ai-wife-uisfx') !== 'off';
let currentBgmUrl = '';
let currentAmbientUrl = '';
let emotionBgmTimeout = null;

function ensureAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();
  return audioCtx;
}

function fadeAudio(audio, gainNode, targetVol, duration, onDone) {
  if (!gainNode) { if (onDone) onDone(); return; }
  const start = gainNode.gain.value;
  const ctx = ensureAudioCtx();
  gainNode.gain.cancelScheduledValues(ctx.currentTime);
  gainNode.gain.setValueAtTime(start, ctx.currentTime);
  gainNode.gain.linearRampToValueAtTime(targetVol, ctx.currentTime + duration);
  if (onDone) setTimeout(onDone, duration * 1000 + 50);
}

function playBgm(url, vol) {
  if (!bgmEnabled || !url) return;
  if (currentBgmUrl === url && bgmAudio && !bgmAudio.paused) return;
  const ctx = ensureAudioCtx();

  // Fade out old
  if (bgmAudio && !bgmAudio.paused) {
    const oldAudio = bgmAudio;
    const oldGain = bgmGain;
    fadeAudio(oldAudio, oldGain, 0, 1.2, () => { oldAudio.pause(); });
  }

  const audio = new Audio(url);
  audio.loop = true;
  audio.crossOrigin = 'anonymous';
  const source = ctx.createMediaElementSource(audio);
  const gain = ctx.createGain();
  gain.gain.value = 0;
  source.connect(gain);
  gain.connect(ctx.destination);
  bgmAudio = audio;
  bgmGain = gain;
  currentBgmUrl = url;
  audio.play().then(() => fadeAudio(audio, gain, vol || bgmVolume, 1.5)).catch(() => {});
}

function playAmbient(url) {
  if (!url) { stopAmbient(); return; }
  if (currentAmbientUrl === url && ambientAudio && !ambientAudio.paused) return;
  stopAmbient();
  const ctx = ensureAudioCtx();
  const audio = new Audio(url);
  audio.loop = true;
  audio.crossOrigin = 'anonymous';
  const source = ctx.createMediaElementSource(audio);
  const gain = ctx.createGain();
  gain.gain.value = 0;
  source.connect(gain);
  gain.connect(ctx.destination);
  ambientAudio = audio;
  ambientGain = gain;
  currentAmbientUrl = url;
  audio.play().then(() => fadeAudio(audio, gain, ambientVolume, 2.0)).catch(() => {});
}

function stopAmbient() {
  if (ambientAudio && !ambientAudio.paused) {
    const old = ambientAudio;
    const oldG = ambientGain;
    fadeAudio(old, oldG, 0, 1.0, () => old.pause());
  }
  ambientAudio = null;
  ambientGain = null;
  currentAmbientUrl = '';
}

function switchSceneAudio(scene) {
  playBgm(SCENE_BGM[scene] || SCENE_BGM.home);
  playAmbient(SCENE_AMBIENT[scene] || null);
}

function triggerEmotionBgm(emotion, currentSceneTheme) {
  const url = EMOTION_BGM_OVERRIDE[emotion];
  if (!url || !bgmEnabled) return;
  // Temporarily switch BGM, revert after 30s
  if (emotionBgmTimeout) clearTimeout(emotionBgmTimeout);
  playBgm(url);
  emotionBgmTimeout = setTimeout(() => {
    playBgm(SCENE_BGM[currentSceneTheme] || SCENE_BGM.home);
    emotionBgmTimeout = null;
  }, 30000);
}

// Preload UI SFX
async function preloadUiSfx() {
  const ctx = ensureAudioCtx();
  for (const [key, url] of Object.entries(UI_SFX)) {
    try {
      const res = await fetch(url);
      const buf = await res.arrayBuffer();
      uiSfxBuffers[key] = await ctx.decodeAudioData(buf);
    } catch (e) { /* skip */ }
  }
}

function playUiSfx(key) {
  if (!uiSfxEnabled || !uiSfxBuffers[key]) return;
  const ctx = ensureAudioCtx();
  const source = ctx.createBufferSource();
  source.buffer = uiSfxBuffers[key];
  const gain = ctx.createGain();
  gain.gain.value = 0.3;
  source.connect(gain);
  gain.connect(ctx.destination);
  source.start();
}

// ── Audio / TTS Playback ─────────────────────────────────────────────
let currentAudio = null;
let isPlaying = false;
let ttsEnabled = localStorage.getItem('ai-wife-tts') !== 'off';

// Streaming TTS state
let streamAbortController = null;
let audioQueue = [];
let playIndex = 0;
let streamDone = false;
let ttsOnFirstAudio = null;  // callback when first audio segment ready
let ttsOnJaText = null;      // callback when ja_text arrives
let ttsOnComplete = null;    // callback when all done

// ── Lip Sync (audio-driven mouth) ────────────────────────────────────
let ttsAnalyser = null;
let ttsAnalyserData = null;

function connectAnalyser(audioEl) {
  try {
    const ctx = ensureAudioCtx();
    const source = ctx.createMediaElementSource(audioEl);
    ttsAnalyser = ctx.createAnalyser();
    ttsAnalyser.fftSize = 256;
    ttsAnalyserData = new Uint8Array(ttsAnalyser.frequencyBinCount);
    source.connect(ttsAnalyser);
    ttsAnalyser.connect(ctx.destination);
  } catch (e) {
    // MediaElementSource can only be created once per element — ignore
    console.warn('[LipSync] analyser connect failed:', e.message);
  }
}

// Returns { aa, ih, ou, ee, oh } mouth shape weights based on frequency analysis.
// Japanese vowels mapped to frequency bands:
//   aa (あ) — open mouth, strong low-mid energy
//   ih (い) — spread lips, higher formant
//   ou (う) — rounded lips, low energy
//   ee (え) — half-open, mid formant
//   oh (お) — rounded open, low-mid
function getLipSyncValues() {
  const zero = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
  if (!ttsAnalyser || !ttsAnalyserData || !isPlaying) return zero;
  ttsAnalyser.getByteFrequencyData(ttsAnalyserData);

  // Split frequency bins into bands (fftSize=256 → 128 bins, ~172Hz per bin at 44.1kHz)
  const len = ttsAnalyserData.length;
  let bandLow = 0, bandMid = 0, bandHigh = 0, total = 0;
  const lowEnd = Math.floor(len * 0.15);   // ~0-750Hz
  const midEnd = Math.floor(len * 0.35);   // ~750-1750Hz
  const highEnd = Math.floor(len * 0.55);  // ~1750-2750Hz

  for (let i = 1; i < highEnd && i < len; i++) {
    const v = ttsAnalyserData[i] / 255;
    total += v;
    if (i < lowEnd) bandLow += v;
    else if (i < midEnd) bandMid += v;
    else bandHigh += v;
  }

  bandLow /= Math.max(1, lowEnd);
  bandMid /= Math.max(1, midEnd - lowEnd);
  bandHigh /= Math.max(1, highEnd - midEnd);
  const energy = total / Math.max(1, highEnd);

  if (energy < 0.04) return zero;  // silence threshold

  // Map bands to mouth shapes (heuristic for Japanese speech)
  const scale = 1.8;
  return {
    aa: Math.min(1, bandLow * scale * 1.2),           // あ — strong low
    oh: Math.min(1, bandLow * scale * 0.6),            // お — moderate low
    ou: Math.min(1, (bandLow * 0.3 + bandMid * 0.2) * scale * 0.5),  // う — quiet rounded
    ee: Math.min(1, bandMid * scale * 0.8),            // え — mid formant
    ih: Math.min(1, (bandMid * 0.4 + bandHigh * 0.6) * scale * 0.9), // い — high spread
  };
}

// Legacy single-value getter (kept for compatibility)
function getLipSyncValue() {
  const v = getLipSyncValues();
  return v.aa;
}

// ── Streaming TTS Player (state machine) ────────────────────────────
// States: idle -> playing -> waiting_for_audio -> playing -> ... -> complete
// Single function `tryPlayNext` handles ALL state transitions.

function tryPlayNext() {
  // Case 1: currently playing — do nothing, onended will call us again
  if (currentAudio && !currentAudio.paused && !currentAudio.ended) return;

  // Case 2: there's audio ready at playIndex — play it
  if (playIndex < audioQueue.length && audioQueue[playIndex]) {
    if (currentAudio) { currentAudio.pause(); }
    const url = audioQueue[playIndex];
    console.log(`[TTS] Playing segment ${playIndex}/${audioQueue.length}: ${url}`);
    currentAudio = new Audio(url);
    currentAudio.crossOrigin = 'anonymous';
    connectAnalyser(currentAudio);
    isPlaying = true;
    currentAudio.onended = () => {
      console.log(`[TTS] Segment ${playIndex} ended`);
      playIndex++;
      tryPlayNext();
    };
    currentAudio.onerror = () => {
      console.warn(`[TTS] Segment ${playIndex} error, skipping`);
      playIndex++;
      tryPlayNext();
    };
    currentAudio.play().catch(e => {
      console.warn('[TTS] play() blocked:', e);
      playIndex++;
      tryPlayNext();
    });
    return;
  }

  // Case 3: no audio ready, stream is done — we're finished
  if (streamDone) {
    console.log(`[TTS] Complete. Played ${playIndex} segments.`);
    isPlaying = false;
    currentAudio = null;
    if (ttsOnComplete) ttsOnComplete();
    return;
  }

  // Case 4: no audio ready, stream still going — wait (underrun)
  console.log(`[TTS] Waiting for segment ${playIndex}...`);
  isPlaying = false;
}

async function playTTSStream(text, emotion = 'neutral') {
  // Stop any previous playback but preserve callbacks
  if (streamAbortController) { streamAbortController.abort(); streamAbortController = null; }
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  audioQueue = [];
  playIndex = 0;
  streamDone = false;
  isPlaying = false;

  const cleanText = text.replace(/\[emotion:\w+\]/g, '').trim();
  if (!cleanText) return;

  const langVal = document.getElementById('lang-selector').value;

  streamAbortController = new AbortController();
  let sseBuffer = '';
  let firstAudioFired = false;

  try {
    const resp = await fetch('/api/tts/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: cleanText, language: langVal, emotion }),
      signal: streamAbortController.signal,
    });
    if (!resp.ok) return;

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const parts = sseBuffer.split('\n\n');
      sseBuffer = parts.pop();

      for (const block of parts) {
        const dataLine = block.split('\n').find(l => l.startsWith('data: '));
        if (!dataLine) continue;
        let event;
        try { event = JSON.parse(dataLine.slice(6)); } catch { continue; }

        if (event.type === 'ja_text') {
          if (ttsOnJaText) ttsOnJaText(event.data);

        } else if (event.type === 'audio') {
          audioQueue[event.index] = event.url;
          console.log(`[TTS] Received audio ${event.index}/${event.total}`);
          if (!firstAudioFired) {
            firstAudioFired = true;
            if (ttsOnFirstAudio) ttsOnFirstAudio();
          }
          // Always try to advance playback
          tryPlayNext();

        } else if (event.type === 'done' || event.type === 'cancelled') {
          streamDone = true;
          console.log(`[TTS] Stream done. Queue: ${audioQueue.length}, playIndex: ${playIndex}`);
          tryPlayNext();

        } else if (event.type === 'error') {
          console.error('[TTS] Server error:', event.message);
          streamDone = true;
          tryPlayNext();
        }
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') console.error('[TTS] Stream error:', err);
    streamDone = true;
    tryPlayNext();
  }
}

// Legacy non-streaming playTTS for pregenWelcomeTTS
async function playTTS(text, emotion = 'neutral') {
  try {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
    const cleanText = text.replace(/\[emotion:\w+\]/g, '').trim();
    if (!cleanText) return null;
    const langVal = document.getElementById('lang-selector').value;
    const resp = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: cleanText, language: langVal, emotion }),
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const audioResp = await fetch(data.audio_url);
    const blob = await audioResp.blob();
    const url = URL.createObjectURL(blob);
    currentAudio = new Audio(url);
    currentAudio.play();
    isPlaying = true;
    currentAudio.onended = () => { isPlaying = false; currentAudio = null; URL.revokeObjectURL(url); };
    return data.ja_text || null;
  } catch (e) {
    console.warn('TTS playback failed:', e);
    return null;
  }
}

// ── SFX Audio Layer ──────────────────────────────────────────────────
const sfxPool = [new Audio(), new Audio(), new Audio()];
let sfxPoolIdx = 0;

function playSfx(urls, loop = false, volume = 0.3) {
  stopSfx();
  urls.forEach(url => {
    const audio = sfxPool[sfxPoolIdx % sfxPool.length];
    sfxPoolIdx++;
    audio.pause();
    audio.src = url;
    audio.loop = loop;
    audio.volume = Math.min(1, Math.max(0, volume));
    audio.play().catch(e => console.warn('SFX play blocked:', e));
  });
}

function stopSfx() {
  sfxPool.forEach(a => { a.pause(); a.currentTime = 0; a.src = ''; });
}

function handleSfxResult(result) {
  if (!result || !result.sfx) return;
  const sfx = result.sfx;
  if (sfx.stop) { stopSfx(); }
  else if (sfx.urls) { playSfx(sfx.urls, sfx.loop, sfx.volume || 0.3); }
}

function stopTTS() {
  if (streamAbortController) {
    streamAbortController.abort();
    streamAbortController = null;
  }
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  audioQueue = [];
  playIndex = 0;
  streamDone = false;
  isPlaying = false;
  ttsOnFirstAudio = null;
  ttsOnJaText = null;
  ttsOnComplete = null;
}

// ── State getters/setters ────────────────────────────────────────────

function isTtsEnabled() { return ttsEnabled; }
function setTtsEnabled(val) {
  ttsEnabled = !!val;
  localStorage.setItem('ai-wife-tts', ttsEnabled ? 'on' : 'off');
}

function isBgmEnabled() { return bgmEnabled; }
function setBgmEnabled(val) {
  bgmEnabled = !!val;
  localStorage.setItem('ai-wife-bgm', bgmEnabled ? 'on' : 'off');
}

function getBgmVolume() { return bgmVolume; }
function setBgmVolume(val) {
  bgmVolume = val;
  localStorage.setItem('ai-wife-bgm-vol', String(bgmVolume));
}

function getAmbientVolume() { return ambientVolume; }
function setAmbientVolume(val) { ambientVolume = val; }

function isUiSfxEnabled() { return uiSfxEnabled; }
function setUiSfxEnabled(val) {
  uiSfxEnabled = !!val;
  localStorage.setItem('ai-wife-uisfx', uiSfxEnabled ? 'on' : 'off');
}

function getIsPlaying() { return isPlaying; }

function getCurrentAudio() { return currentAudio; }
function setCurrentAudio(audio) { currentAudio = audio; }
function setIsPlaying(val) { isPlaying = !!val; }

function getBgmGain() { return bgmGain; }
function getBgmAudio() { return bgmAudio; }
function getCurrentBgmUrl() { return currentBgmUrl; }
function setCurrentBgmUrl(val) { currentBgmUrl = val; }
function getAmbientGain() { return ambientGain; }

// TTS callback setters
function setTtsOnFirstAudio(fn) { ttsOnFirstAudio = fn; }
function setTtsOnJaText(fn) { ttsOnJaText = fn; }
function setTtsOnComplete(fn) { ttsOnComplete = fn; }

// Audio queue access (for replay-from-cache)
function getAudioQueue() { return audioQueue; }
function setAudioQueue(arr) { audioQueue = arr; }
function getPlayIndex() { return playIndex; }
function setPlayIndex(val) { playIndex = val; }
function setStreamDone(val) { streamDone = !!val; }

function hasAudioCtx() { return !!audioCtx; }

// ── Exports ──────────────────────────────────────────────────────────
export {
  // Constants
  SCENE_BGM,
  EMOTION_BGM_OVERRIDE,
  SCENE_AMBIENT,
  UI_SFX,

  // BGM / Ambient / UI SFX functions
  ensureAudioCtx,
  fadeAudio,
  playBgm,
  playAmbient,
  stopAmbient,
  switchSceneAudio,
  triggerEmotionBgm,
  preloadUiSfx,
  playUiSfx,

  // TTS playback functions
  tryPlayNext,
  playTTSStream,
  playTTS,
  stopTTS,

  // SFX layer functions
  playSfx,
  stopSfx,
  handleSfxResult,

  // State getters/setters
  isTtsEnabled,
  setTtsEnabled,
  isBgmEnabled,
  setBgmEnabled,
  getBgmVolume,
  setBgmVolume,
  getAmbientVolume,
  setAmbientVolume,
  isUiSfxEnabled,
  setUiSfxEnabled,
  getIsPlaying,
  setIsPlaying,
  getCurrentAudio,
  setCurrentAudio,
  getBgmGain,
  getBgmAudio,
  getCurrentBgmUrl,
  setCurrentBgmUrl,
  getAmbientGain,
  hasAudioCtx,

  // TTS callback setters
  setTtsOnFirstAudio,
  setTtsOnJaText,
  setTtsOnComplete,

  // Audio queue access
  getAudioQueue,
  setAudioQueue,
  getPlayIndex,
  setPlayIndex,
  setStreamDone,

  // Lip sync
  getLipSyncValue,
  getLipSyncValues,
};
