/**
 * settings.js — Settings panel, provider config, startup screen,
 * render settings, VRM character tab, animation management,
 * music controls, custom BGM upload.
 *
 * Extracted from index.html to keep the main module manageable.
 * NOTE: innerHTML usage below is from the original codebase and uses
 * server-owned data only (memory content, cron jobs, etc.), not
 * arbitrary user input.
 */

import * as THREE from 'three';
import {
  SCENE_BGM, SCENE_AMBIENT, switchSceneAudio,
  playBgm, playAmbient, stopAmbient, preloadUiSfx,
  isTtsEnabled, isBgmEnabled, setBgmEnabled,
  getBgmVolume, setBgmVolume, getAmbientVolume, setAmbientVolume,
  getBgmGain, getBgmAudio, getCurrentBgmUrl, setCurrentBgmUrl,
  getAmbientGain, hasAudioCtx,
  getIsPlaying, setIsPlaying, getCurrentAudio, setCurrentAudio,
} from './audio.js';

// ── Module-level references filled by initSettings(ctx) ────────────
let animController = null;
let currentVrm = null;
let scene = null;
let camera = null;
let controls = null;
let renderer = null;
let ambientLight = null;
let dirLight = null;
let loadModel = null;       // async fn
let applySceneTheme = null; // fn
let currentSceneTheme = 'home';
let sceneAudioSwitcher = switchSceneAudio;
let langSel = null;         // <select> element
let savedVrmPath = '';
let isInIdleState = true;
let setEmotion = null;      // fn from main module
let setMouthShape = null;   // fn from main module

// Setter exposed so the main module can push updates into us.
export function updateCtx(patch) {
  if (patch.animController !== undefined) animController = patch.animController;
  if (patch.currentVrm !== undefined)     currentVrm = patch.currentVrm;
  if (patch.scene !== undefined)          scene = patch.scene;
  if (patch.camera !== undefined)         camera = patch.camera;
  if (patch.controls !== undefined)       controls = patch.controls;
  if (patch.renderer !== undefined)       renderer = patch.renderer;
  if (patch.ambientLight !== undefined)   ambientLight = patch.ambientLight;
  if (patch.dirLight !== undefined)       dirLight = patch.dirLight;
  if (patch.loadModel !== undefined)      loadModel = patch.loadModel;
  if (patch.applySceneTheme !== undefined) applySceneTheme = patch.applySceneTheme;
  if (patch.currentSceneTheme !== undefined) currentSceneTheme = patch.currentSceneTheme;
  if (patch.sceneAudioSwitcher !== undefined) sceneAudioSwitcher = patch.sceneAudioSwitcher;
  if (patch.langSel !== undefined)        langSel = patch.langSel;
  if (patch.savedVrmPath !== undefined)   savedVrmPath = patch.savedVrmPath;
  if (patch.isInIdleState !== undefined)  isInIdleState = patch.isInIdleState;
}

// ── Toast (shared utility) ──────────────────────────────────────────
const toast = document.getElementById('toast');
export function showToast(msg, duration = 3000) {
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// ── Getter for the overridden sceneAudioSwitcher ────────────────────
export function getSceneAudioSwitcher() {
  return sceneAudioSwitcher;
}

// =====================================================================
// initSettings — call once after the 3D scene is ready
// =====================================================================
export function initSettings(ctx) {
  // Populate module-level refs from the context object
  animController   = ctx.animController;
  currentVrm       = ctx.currentVrm;
  scene            = ctx.scene;
  camera           = ctx.camera;
  controls         = ctx.controls;
  renderer         = ctx.renderer;
  ambientLight     = ctx.ambientLight;
  dirLight         = ctx.dirLight;
  loadModel        = ctx.loadModel;
  applySceneTheme  = ctx.applySceneTheme;
  currentSceneTheme = ctx.currentSceneTheme;
  sceneAudioSwitcher = ctx.sceneAudioSwitcher;
  langSel          = ctx.langSel;
  savedVrmPath     = ctx.savedVrmPath;
  isInIdleState    = ctx.isInIdleState;
  setEmotion       = ctx.setEmotion || null;
  setMouthShape    = ctx.setMouthShape || null;

  // ── Settings Panel ──────────────────────────────────────────────────
  const settingsModal = document.getElementById('settings-modal');
  document.getElementById('settings-btn').onclick = () => {
    settingsModal.classList.remove('hidden'); settingsModal.classList.add('visible');
    loadSettingsData();
  };
  document.getElementById('close-settings').onclick = () => { settingsModal.classList.remove('visible'); settingsModal.classList.add('hidden'); };

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-body').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      document.getElementById(e.target.dataset.tab).classList.add('active');
    };
  });

  async function loadSettingsData() {
    // Memories
    try {
      const memRes = await fetch('/api/memory/list');
      if (memRes.ok) {
        const mems = (await memRes.json()).memories || await memRes.json();
        const l = document.getElementById('memory-list');
        l.textContent = '';
        if (!mems || mems.length === 0) {
          const span = document.createElement('span');
          span.style.color = '#aaa';
          span.textContent = '目前沒有記憶。';
          l.appendChild(span);
        }
        (Array.isArray(mems) ? mems : []).forEach(m => {
          const d = document.createElement('div'); d.className = 'memory-item';
          const contentDiv = document.createElement('div');
          contentDiv.textContent = m.content;
          const small = document.createElement('small');
          small.style.color = '#FFB6C1';
          small.textContent = m.category;
          contentDiv.appendChild(document.createElement('br'));
          contentDiv.appendChild(small);
          d.appendChild(contentDiv);
          const delBtn = document.createElement('button');
          delBtn.textContent = '刪除';
          delBtn.onclick = async () => {
            await fetch(`/api/memory/${m.id}`, { method: 'DELETE' });
            d.remove();
          };
          d.appendChild(delBtn);
          l.appendChild(d);
        });
      }
    } catch (e) { console.error('Load memories failed', e); }

    // Soul
    try {
      const soulRes = await fetch('/api/soul');
      if (soulRes.ok) {
        const json = await soulRes.json();
        document.getElementById('soul-editor').value = json.soul || '';
        document.getElementById('profile-editor').value = json.profile || '';
      }
    } catch (e) { console.error('Load soul failed', e); }

    // Heartbeat
    try {
      const hbRes = await fetch('/api/heartbeat/jobs');
      if (hbRes.ok) {
        const jobs = await hbRes.json();
        const hl = document.getElementById('heartbeat-list');
        hl.textContent = '';
        if (!jobs || jobs.length === 0) {
          const span = document.createElement('span');
          span.style.color = '#aaa';
          span.textContent = '目前沒有定時任務。';
          hl.appendChild(span);
        }
        jobs.forEach(j => {
          const d = document.createElement('div'); d.className = 'hb-item';
          const infoDiv = document.createElement('div');
          infoDiv.className = 'info';
          const cronDiv = document.createElement('div');
          cronDiv.className = 'cron';
          cronDiv.textContent = `ID: ${j.id} | ${j.cron}`;
          infoDiv.appendChild(cronDiv);
          const actionDiv = document.createElement('div');
          actionDiv.className = 'action';
          actionDiv.textContent = j.action;
          infoDiv.appendChild(actionDiv);
          d.appendChild(infoDiv);
          const btn = document.createElement('button');
          btn.className = `btn-toggle ${j.enabled ? 'enabled' : ''}`;
          btn.textContent = j.enabled ? '啟用中' : '已停用';
          btn.onclick = async () => {
            j.enabled = !j.enabled;
            btn.className = `btn-toggle ${j.enabled ? 'enabled' : ''}`;
            btn.textContent = j.enabled ? '啟用中' : '已停用';
            try {
              await fetch('/api/heartbeat/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(j)
              });
            } catch (e) {}
          };
          d.appendChild(btn);
          hl.appendChild(d);
        });
      }
    } catch (e) { console.error('Load heartbeat failed', e); }

    // Provider
    loadProviderSettings();

    // Voice profiles
    try {
      const vRes = await fetch('/api/voice/profiles');
      if (vRes.ok) {
        const vData = await vRes.json();
        const profiles = vData.profiles || [];
        const activeNormal = vData.active_normal || '';
        const activeHorny = vData.active_horny || '';

        const normalSel = document.getElementById('voice-normal-select');
        const hornySel = document.getElementById('voice-horny-select');
        const testSel = document.getElementById('voice-test-profile');
        const trainSel = document.getElementById('train-profile-select');

        [normalSel, hornySel, testSel, trainSel].forEach(sel => { sel.textContent = ''; });

        profiles.forEach(p => {
          const makeOpt = (sel, selected) => {
            const o = document.createElement('option');
            o.value = p.id;
            o.textContent = `${p.name} (${p.language || 'ja'})`;
            if (selected) o.selected = true;
            sel.appendChild(o);
          };
          makeOpt(normalSel, p.id === activeNormal);
          makeOpt(hornySel, p.id === activeHorny);
          makeOpt(testSel, false);
          makeOpt(trainSel, false);
        });
      }
    } catch (e) { console.error('Load voice profiles failed', e); }
  }

  // Voice profile handlers
  document.getElementById('voice-save-btn').onclick = async () => {
    const normalId = document.getElementById('voice-normal-select').value;
    const hornyId = document.getElementById('voice-horny-select').value;
    const btn = document.getElementById('voice-save-btn');
    btn.textContent = '切換中...';
    try {
      await fetch('/api/voice/switch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: normalId, mode: 'normal' }) });
      await fetch('/api/voice/switch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: hornyId, mode: 'horny' }) });
      btn.textContent = '✓ 已套用';
      setTimeout(() => { btn.textContent = '套用語音設定'; }, 2000);
    } catch (e) { btn.textContent = '失敗'; }
  };

  // Voice training handlers
  document.getElementById('train-create-btn').onclick = async () => {
    const name = document.getElementById('train-name').value.trim();
    const lang = document.getElementById('train-lang').value;
    const status = document.getElementById('train-create-status');
    if (!name) { status.textContent = '請輸入角色名稱'; return; }
    status.textContent = '建立中...';
    try {
      const resp = await fetch('/api/voice/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, language: lang, description: `${name} voice profile` }),
      });
      const data = await resp.json();
      if (data.error) { status.textContent = '❌ ' + data.error; return; }
      status.textContent = `✓ 已建立: ${data.name} (${data.id.substring(0, 8)}...)`;
      document.getElementById('train-name').value = '';
      loadSettingsData();
    } catch (e) { status.textContent = '❌ ' + e.message; }
  };

  document.getElementById('train-upload-btn').onclick = async () => {
    const profileId = document.getElementById('train-profile-select').value;
    const file = document.getElementById('train-file').files[0];
    const refText = document.getElementById('train-ref-text').value.trim();
    const status = document.getElementById('train-upload-status');
    if (!profileId) { status.textContent = '請選擇角色'; return; }
    if (!file) { status.textContent = '請選擇音頻檔案'; return; }
    if (!refText) { status.textContent = '請輸入文字稿'; return; }
    status.textContent = '上傳中...（首次可能需要 30-60 秒建立 voice prompt）';
    const formData = new FormData();
    formData.append('file', file);
    formData.append('profile_id', profileId);
    formData.append('reference_text', refText);
    try {
      const resp = await fetch('/api/voice/upload-sample', { method: 'POST', body: formData });
      const data = await resp.json();
      if (data.error) { status.textContent = '❌ ' + data.error; return; }
      status.textContent = `✓ 樣本已上傳 (${data.id?.substring(0, 8)}...)`;
      document.getElementById('train-file').value = '';
      document.getElementById('train-ref-text').value = '';
      loadTrainSamples(profileId);
    } catch (e) { status.textContent = '❌ ' + e.message; }
  };

  document.getElementById('train-profile-select').onchange = () => {
    const pid = document.getElementById('train-profile-select').value;
    if (pid) loadTrainSamples(pid);
  };

  async function loadTrainSamples(profileId) {
    const el = document.getElementById('train-samples-list');
    try {
      const resp = await fetch(`/api/voice/samples/${profileId}`);
      const data = await resp.json();
      const samples = data.samples || [];
      if (!samples.length) {
        el.textContent = '';
        const div = document.createElement('div');
        div.style.padding = '4px';
        div.textContent = '尚無樣本';
        el.appendChild(div);
        return;
      }
      el.textContent = '';
      samples.forEach(s => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:4px;padding:3px 0;border-bottom:1px solid var(--glass-border);';
        const span1 = document.createElement('span');
        span1.style.cssText = 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
        span1.textContent = (s.reference_text?.substring(0, 30) || 'sample') + '...';
        row.appendChild(span1);
        const span2 = document.createElement('span');
        span2.style.cssText = 'color:var(--text-muted);font-size:9px;';
        span2.textContent = s.id?.substring(0, 6) || '';
        row.appendChild(span2);
        el.appendChild(row);
      });
    } catch { el.textContent = '載入失敗'; }
  }

  document.getElementById('voice-test-btn').onclick = async () => {
    const profileId = document.getElementById('voice-test-profile').value;
    const text = document.getElementById('voice-test-text').value || 'こんにちは';
    const status = document.getElementById('voice-test-status');
    const btn = document.getElementById('voice-test-btn');
    btn.disabled = true;
    status.textContent = '生成中...';
    try {
      const resp = await fetch('/api/voice/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile_id: profileId, text }) });
      const data = await resp.json();
      if (data.error) { status.textContent = '❌ ' + data.error; return; }
      status.textContent = `✓ ${data.duration?.toFixed(1)}s`;
      const audio = new Audio(data.audio_url);
      audio.play();
    } catch (e) { status.textContent = '❌ ' + e.message; }
    finally { btn.disabled = false; }
  };

  // TTS service management
  async function checkTTSStatus() {
    const el = document.getElementById('tts-service-status');
    try {
      const resp = await fetch('/api/tts/status');
      const data = await resp.json();
      if (data.status === 'running') {
        el.textContent = `狀態: ✅ 運行中 (${data.profiles} 個語音角色)`;
        el.style.color = '#4caf50';
      } else {
        el.textContent = '狀態: ❌ 已停止';
        el.style.color = '#ff6b6b';
      }
    } catch { el.textContent = '狀態: ⚠️ 無法連線'; el.style.color = '#ff9800'; }
  }

  document.getElementById('tts-kill-btn').onclick = async () => {
    const btn = document.getElementById('tts-kill-btn');
    btn.disabled = true; btn.textContent = '停止中...';
    try {
      await fetch('/api/tts/kill', { method: 'POST' });
      btn.textContent = '✓ 已停止';
      await checkTTSStatus();
    } catch { btn.textContent = '失敗'; }
    finally { setTimeout(() => { btn.disabled = false; btn.textContent = '強制停止'; }, 2000); }
  };

  document.getElementById('tts-restart-btn').onclick = async () => {
    const btn = document.getElementById('tts-restart-btn');
    btn.disabled = true; btn.textContent = '重啟中...（約30秒）';
    document.getElementById('tts-service-status').textContent = '狀態: 🔄 重啟中...';
    try {
      const resp = await fetch('/api/tts/restart', { method: 'POST' });
      const data = await resp.json();
      if (data.ok) { btn.textContent = '✓ 已重啟'; }
      else { btn.textContent = '⚠️ ' + (data.message || data.error); }
      await checkTTSStatus();
    } catch { btn.textContent = '失敗'; }
    finally { setTimeout(() => { btn.disabled = false; btn.textContent = '重新啟動'; }, 3000); }
  };

  // Check TTS status when voice tab is opened
  const origTabClick = document.querySelectorAll('.tab-btn');
  origTabClick.forEach(btn => {
    const origHandler = btn.onclick;
    btn.onclick = (e) => {
      if (origHandler) origHandler(e);
      if (e.target.dataset.tab === 'tab-voice') checkTTSStatus();
    };
  });

  document.getElementById('save-soul-btn').onclick = async () => {
    const val = document.getElementById('soul-editor').value;
    const profileVal = document.getElementById('profile-editor').value;
    try {
      await fetch('/api/soul', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ soul: val, profile: profileVal })
      });
      const btn = document.getElementById('save-soul-btn');
      btn.textContent = '已儲存 ✓'; setTimeout(() => btn.textContent = '儲存修改', 2000);
    } catch (e) { alert('儲存失敗'); }
  };

  // ── Provider Settings ────────────────────────────────────────────────
  const providerPresets = {
    ollama:            { base_url: 'http://localhost:9090', model: 'qwen3.5:9b' },
    dashscope:         { base_url: 'https://dashscope-intl.aliyuncs.com/compatible-mode', model: 'qwen3-235b-a22b' },
    openrouter:        { base_url: 'https://openrouter.ai/api', model: 'qwen/qwen3.6-plus:free' },
    openai:            { base_url: 'https://api.openai.com', model: 'gpt-4o-mini' },
    openai_compatible: { base_url: '', model: '' },
  };

  const providerSelect = document.getElementById('provider-select');
  const providerBaseUrl = document.getElementById('provider-base-url');
  const providerModel = document.getElementById('provider-model');
  const providerApiKey = document.getElementById('provider-api-key');
  const providerStatus = document.getElementById('provider-status');

  providerSelect.onchange = () => {
    const pv = providerSelect.value;
    const preset = providerPresets[pv];
    if (preset) {
      providerBaseUrl.value = preset.base_url;
    }
    const saved = loadProviderKeys(pv);
    providerModel.value = saved.model || (preset ? preset.model : '');
    providerApiKey.value = saved.key;
    providerApiKey.placeholder = pv === 'ollama' ? '（本機不需要）' : (saved.key ? '已儲存 ✓' : 'sk-...');
  };

  async function loadProviderSettings() {
    try {
      const res = await fetch('/api/config/provider');
      if (res.ok) {
        const data = await res.json();
        providerSelect.value = data.provider || 'ollama';
        providerBaseUrl.value = data.base_url || '';
        providerModel.value = data.model || '';
        providerApiKey.value = '';
        providerStatus.textContent = data.has_api_key ? '🔑 API Key 已設定' : '';
      }
    } catch (e) { console.error('Load provider failed', e); }

    try {
      const kr = await fetch('/api/config/keys');
      if (kr.ok) {
        const kd = await kr.json();
        if (kd.brave_api_key) document.getElementById('keys-brave').placeholder = kd.brave_api_key + ' (已設定)';
        const gStatusEl = document.getElementById('keys-google-status');
        gStatusEl.textContent = '';
        const lines = [];
        if (kd.google_credentials) lines.push('✅ Google OAuth 憑證');
        else lines.push('❌ Google OAuth 憑證 (需要 config/credentials.json)');
        if (kd.gmail_token) lines.push('✅ Gmail Token');
        if (kd.calendar_token) lines.push('✅ Calendar Token');
        lines.forEach((line, i) => {
          if (i > 0) gStatusEl.appendChild(document.createElement('br'));
          gStatusEl.appendChild(document.createTextNode(line));
        });
      }
    } catch (e) { console.error('Load keys failed', e); }
  }

  // SFX management
  async function loadSfxInfo() {
    try {
      const resp = await fetch('/api/sfx');
      if (resp.ok) {
        const data = await resp.json();
        const cats = data.categories || {};
        const total = Object.values(cats).reduce((a, b) => a + b, 0);
        document.getElementById('sfx-stats').textContent = `已索引 ${total} 個音效，${Object.keys(cats).length} 個分類`;
        const catEl = document.getElementById('sfx-categories');
        catEl.textContent = '';
        Object.entries(cats).forEach(([k, v]) => {
          const span = document.createElement('span');
          span.style.cssText = 'display:inline-block;padding:2px 8px;margin:2px;background:var(--accent-muted);border-radius:8px;';
          span.textContent = `${k} (${v})`;
          catEl.appendChild(span);
        });
      }
    } catch (e) { document.getElementById('sfx-stats').textContent = '無法載入音效目錄'; }
  }

  document.getElementById('sfx-upload-btn').onclick = async () => {
    const btn = document.getElementById('sfx-upload-btn');
    const files = document.getElementById('sfx-upload-file').files;
    const category = document.getElementById('sfx-upload-category').value.trim() || 'custom';
    const status = document.getElementById('sfx-upload-status');
    if (!files.length) { status.textContent = '請選擇檔案'; return; }
    btn.disabled = true; btn.textContent = '上傳中...';
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    formData.append('category', category);
    try {
      const resp = await fetch('/api/sfx/upload', { method: 'POST', body: formData });
      const data = await resp.json();
      status.textContent = `✓ 已上傳 ${data.uploaded?.length || 0} 個檔案，目錄共 ${data.total} 個音效`;
      document.getElementById('sfx-upload-file').value = '';
      loadSfxInfo();
    } catch (e) { status.textContent = '❌ 上傳失敗: ' + e.message; }
    finally { btn.disabled = false; btn.textContent = '上傳'; }
  };

  document.getElementById('sfx-search-btn').onclick = async () => {
    const query = document.getElementById('sfx-search-input').value.trim();
    const resultsEl = document.getElementById('sfx-results');
    if (!query) { resultsEl.textContent = ''; return; }
    try {
      const resp = await fetch(`/api/sfx?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      const results = data.results || [];
      if (!results.length) {
        resultsEl.textContent = '';
        const div = document.createElement('div');
        div.style.cssText = 'padding:6px;color:var(--text-muted);';
        div.textContent = '找不到相關音效';
        resultsEl.appendChild(div);
        return;
      }
      resultsEl.textContent = '';
      results.forEach(r => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid var(--glass-border);';
        const playBtn = document.createElement('button');
        playBtn.style.cssText = 'background:none;border:none;cursor:pointer;font-size:14px;';
        playBtn.textContent = '▶';
        playBtn.onclick = () => new Audio('/api/sfx/' + r.id).play();
        row.appendChild(playBtn);
        const descSpan = document.createElement('span');
        descSpan.style.cssText = 'flex:1;font-size:11px;color:var(--text-primary);';
        descSpan.textContent = r.description;
        row.appendChild(descSpan);
        const catSpan = document.createElement('span');
        catSpan.style.cssText = 'font-size:10px;color:var(--text-muted);';
        catSpan.textContent = r.category;
        row.appendChild(catSpan);
        resultsEl.appendChild(row);
      });
    } catch (e) { resultsEl.textContent = '❌ 搜尋失敗'; }
  };

  // Load SFX info when tab is opened
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const orig = btn.onclick;
    btn.addEventListener('click', (e) => {
      if (e.target.dataset.tab === 'tab-sfx') loadSfxInfo();
    });
  });

  document.getElementById('save-keys-btn').onclick = async () => {
    const btn = document.getElementById('save-keys-btn');
    const braveKey = document.getElementById('keys-brave').value.trim();
    if (!braveKey) { btn.textContent = '請輸入至少一個 Key'; setTimeout(() => { btn.textContent = '儲存 API Keys'; }, 2000); return; }
    btn.disabled = true; btn.textContent = '儲存中...';
    try {
      const body = {};
      if (braveKey) body.brave_api_key = braveKey;
      await fetch('/api/config/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      btn.textContent = '✓ 已儲存';
      if (braveKey) localStorage.setItem('ai-wife-brave-key', braveKey);
    } catch { btn.textContent = '失敗'; }
    finally { setTimeout(() => { btn.disabled = false; btn.textContent = '儲存 API Keys'; }, 2000); }
  };

  // Auto-restore Brave key from localStorage on startup
  (async () => {
    const savedBrave = localStorage.getItem('ai-wife-brave-key');
    if (savedBrave) {
      try { await fetch('/api/config/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ brave_api_key: savedBrave }) }); } catch {}
    }
  })();

  document.getElementById('save-provider-btn').onclick = async () => {
    const btn = document.getElementById('save-provider-btn');
    btn.disabled = true;
    btn.textContent = '套用中...';
    try {
      const res = await fetch('/api/config/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: providerSelect.value,
          base_url: providerBaseUrl.value,
          api_key: providerApiKey.value,
          model: providerModel.value,
        })
      });
      const data = await res.json();
      if (data.success) {
        btn.textContent = '已套用 ✓';
        providerStatus.textContent = '🔑 API Key 已設定';
        saveProviderKeys(providerSelect.value, providerApiKey.value, providerModel.value);
        showToast(`已切換到 ${data.provider} / ${data.model}`);
      } else {
        btn.textContent = '失敗 ✗';
        providerStatus.textContent = '❌ ' + (data.error || 'Unknown error');
      }
    } catch (e) {
      btn.textContent = '失敗 ✗';
      providerStatus.textContent = '❌ 連線失敗';
    }
    setTimeout(() => { btn.disabled = false; btn.textContent = '套用設定'; }, 2000);
  };

  // ── Startup Screen ──────────────────────────────────────────────────
  const setupScreen = document.getElementById('setup-screen');
  const setupModel = document.getElementById('setup-model');
  const setupLang = document.getElementById('setup-lang');
  const setupProvider = document.getElementById('setup-provider');
  const setupCloudFields = document.getElementById('setup-cloud-fields');
  const setupLocalModelField = document.getElementById('setup-local-model-field');
  const setupCloudModel = document.getElementById('setup-cloud-model');
  const setupApiKey = document.getElementById('setup-api-key');
  const testBtn = document.getElementById('test-connection-btn');
  const enterBtn = document.getElementById('enter-btn');
  const modelOverlay = document.getElementById('model-switch-overlay');

  const CLOUD_BASE_URLS = {
    dashscope: 'https://dashscope-intl.aliyuncs.com/compatible-mode',
    openrouter: 'https://openrouter.ai/api',
    openai: 'https://api.openai.com',
  };
  const CLOUD_DEFAULT_MODELS = {
    dashscope: 'qwen3-235b-a22b',
    openrouter: 'qwen/qwen3.6-plus:free',
    openai: 'gpt-4o-mini',
  };

  // Per-provider key storage helpers
  function saveProviderKeys(provider, key, model) {
    if (provider && key) localStorage.setItem('ai-wife-key-' + provider, key);
    if (provider && model) localStorage.setItem('ai-wife-model-' + provider, model);
  }
  function loadProviderKeys(provider) {
    return {
      key: localStorage.getItem('ai-wife-key-' + provider) || '',
      model: localStorage.getItem('ai-wife-model-' + provider) || CLOUD_DEFAULT_MODELS[provider] || '',
    };
  }

  // Fetch and populate model list for a provider
  var _allModels = {};
  async function loadModelList(provider, selectEl, searchEl) {
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    const loadingOpt = document.createElement('option');
    loadingOpt.value = '';
    loadingOpt.textContent = '載入中...';
    selectEl.appendChild(loadingOpt);
    try {
      const r = await fetch('/api/config/provider-models?provider=' + encodeURIComponent(provider));
      const data = await r.json();
      const models = data.models || [];
      _allModels[provider] = models;
      populateModelSelect(models, selectEl, '');
      const saved = loadProviderKeys(provider);
      if (saved.model) selectEl.value = saved.model;
    } catch (e) {
      while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
      const errOpt = document.createElement('option');
      errOpt.value = '';
      errOpt.textContent = '載入失敗';
      selectEl.appendChild(errOpt);
    }
  }

  function populateModelSelect(models, selectEl, filter) {
    const q = filter.toLowerCase();
    const filtered = q ? models.filter(m => m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)) : models;
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    if (filtered.length === 0) {
      const noneOpt = document.createElement('option');
      noneOpt.value = '';
      noneOpt.textContent = '無匹配結果';
      selectEl.appendChild(noneOpt);
      return;
    }
    filtered.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      const badge = m.free ? '🆓 ' : '';
      const ctxLabel = m.context ? ' (' + Math.round(m.context/1024) + 'K)' : '';
      opt.textContent = badge + m.name + ctxLabel;
      selectEl.appendChild(opt);
    });
  }

  // Search filters
  document.getElementById('setup-cloud-model-search').addEventListener('input', (e) => {
    const models = _allModels[setupProvider.value] || [];
    populateModelSelect(models, document.getElementById('setup-cloud-model'), e.target.value);
  });
  document.getElementById('setup-fallback-model-search').addEventListener('input', (e) => {
    const fbProv = document.getElementById('setup-fallback-provider').value;
    const models = _allModels[fbProv] || [];
    populateModelSelect(models, document.getElementById('setup-fallback-model'), e.target.value);
  });

  setupProvider.addEventListener('change', () => {
    const isCloud = setupProvider.value !== 'ollama';
    setupCloudFields.style.display = isCloud ? 'block' : 'none';
    setupLocalModelField.style.display = isCloud ? 'none' : 'block';
    document.getElementById('setup-fallback-fields').style.display = isCloud ? 'block' : 'none';
    if (isCloud) {
      const saved = loadProviderKeys(setupProvider.value);
      setupApiKey.value = saved.key;
      setupApiKey.placeholder = saved.key ? '已儲存 ✓' : 'sk-...';
      loadModelList(setupProvider.value, document.getElementById('setup-cloud-model'), document.getElementById('setup-cloud-model-search'));
    }
  });

  document.getElementById('setup-fallback-provider').addEventListener('change', () => {
    const fbProv = document.getElementById('setup-fallback-provider').value;
    if (fbProv) {
      const saved = loadProviderKeys(fbProv);
      document.getElementById('setup-fallback-key').value = saved.key;
      loadModelList(fbProv, document.getElementById('setup-fallback-model'), document.getElementById('setup-fallback-model-search'));
    }
  });

  // Restore saved provider (default to dashscope if no saved preference)
  const savedProviderVal = localStorage.getItem('ai-wife-provider') || 'dashscope';
  const savedApiKeyVal = localStorage.getItem('ai-wife-api-key');
  const savedCloudModelVal = localStorage.getItem('ai-wife-cloud-model');
  setupProvider.value = savedProviderVal;
  setupProvider.dispatchEvent(new Event('change'));
  if (savedApiKeyVal) setupApiKey.value = savedApiKeyVal;

  function setStatus(id, status, detail = '') {
    const el = document.getElementById(id);
    el.className = `status ${status}`;
    el.textContent = { ok: '✓', fail: '✗', pending: '?', testing: '…' }[status] || '?';
    const detailEl = document.getElementById(id + '-detail');
    if (detailEl && detail) detailEl.textContent = detail;
  }

  let welcomeAudioUrl = null;
  let welcomeJaText = null;

  async function pregenWelcomeTTS() {
    try {
      const resp = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: '老公～歡迎回來！今天想跟小愛聊什麼呢？',
          language: langSel.value || 'zh-TW',
          emotion: 'happy',
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const audioResp = await fetch(data.audio_url);
        const blob = await audioResp.blob();
        welcomeAudioUrl = URL.createObjectURL(blob);
        welcomeJaText = data.ja_text || '';
        console.log('Welcome TTS pre-generated');
      }
    } catch (e) {
      console.warn('Welcome TTS pregen failed:', e);
    }
  }

  async function runTests() {
    testBtn.disabled = true;
    testBtn.textContent = '測試中...';

    const tests = ['llm', 'tts', 'stt', 'skills'];
    tests.forEach(t => setStatus('test-' + t, 'testing'));

    const prov = setupProvider.value;
    if (prov !== 'ollama') {
      const ak = setupApiKey.value.trim();
      const cm = setupCloudModel.value || document.getElementById('setup-cloud-model-search').value.trim();
      if (!ak) { showToast('請先輸入 API Key'); testBtn.disabled = false; testBtn.textContent = '測試連線'; return; }
      if (!cm) { showToast('請先輸入模型名稱'); testBtn.disabled = false; testBtn.textContent = '測試連線'; return; }
      try {
        const pr = await fetch('/api/config/provider', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: prov, base_url: CLOUD_BASE_URLS[prov], api_key: ak, model: cm,
            fallback_provider: document.getElementById('setup-fallback-provider').value,
            fallback_base_url: CLOUD_BASE_URLS[document.getElementById('setup-fallback-provider').value] || '',
            fallback_api_key: document.getElementById('setup-fallback-key').value.trim(),
            fallback_model: document.getElementById('setup-fallback-model').value || document.getElementById('setup-fallback-model-search').value.trim(),
          }),
        });
        const pd = await pr.json();
        if (!pd.success) { showToast('Provider 設定失敗: ' + pd.error); testBtn.disabled = false; testBtn.textContent = '測試連線'; return; }
      } catch (e) { showToast('連線失敗'); testBtn.disabled = false; testBtn.textContent = '測試連線'; return; }
    } else {
      try {
        await fetch('/api/config/provider', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: 'ollama', base_url: 'http://localhost:9090', api_key: '', model: setupModel.value }),
        });
      } catch (e) {}
    }

    try {
      const res = await fetch('/api/health/test');
      const data = await res.json();

      if (data.llm?.ok) {
        const pLabel = data.llm.provider === 'ollama' ? '🖥️' : '☁️';
        setStatus('test-llm', 'ok', `${pLabel} ${data.llm.model} (${data.llm.latency_ms}ms)`);
      } else {
        setStatus('test-llm', 'fail', data.llm?.error?.substring(0, 80) || 'Unknown');
      }

      if (data.tts?.ok) {
        setStatus('test-tts', 'ok', data.tts.provider);
      } else {
        setStatus('test-tts', 'fail', data.tts?.error || 'Unknown');
      }

      if (data.stt?.ok) {
        setStatus('test-stt', 'ok', data.stt.provider);
      } else {
        setStatus('test-stt', 'fail', data.stt?.error || 'Unknown');
      }

      if (data.skills?.ok) {
        setStatus('test-skills', 'ok', `${data.skills.tool_count} tools`);
      } else {
        setStatus('test-skills', 'fail', data.skills?.error || 'Unknown');
      }

      const llmOk = data.llm?.ok;
      if (llmOk) {
        if (isTtsEnabled()) {
          enterBtn.textContent = '語音準備中...';
          enterBtn.disabled = true;
          await pregenWelcomeTTS();
          enterBtn.textContent = '進入 💕';
          enterBtn.disabled = false;
        }
        enterBtn.classList.add('ready');
      }
    } catch (e) {
      tests.forEach(t => setStatus('test-' + t, 'fail', '連線失敗'));
    }

    testBtn.disabled = false;
    testBtn.textContent = '重新測試';
  }

  testBtn.addEventListener('click', runTests);

  enterBtn.addEventListener('click', async () => {
    const provider = setupProvider.value;
    const isCloud = provider !== 'ollama';

    localStorage.setItem('ai-wife-provider', provider);
    localStorage.setItem('ai-wife-lang', setupLang.value);
    langSel.value = setupLang.value;

    if (isCloud) {
      const cloudModel = setupCloudModel.value || document.getElementById('setup-cloud-model-search').value.trim();
      const apiKey = setupApiKey.value.trim();
      if (!apiKey) { showToast('請輸入 API Key'); return; }
      if (!cloudModel) { showToast('請選擇模型'); return; }

      localStorage.setItem('ai-wife-api-key', apiKey);
      localStorage.setItem('ai-wife-cloud-model', cloudModel);
      saveProviderKeys(provider, apiKey, cloudModel);
      const _fbp = document.getElementById('setup-fallback-provider').value;
      const _fbk = document.getElementById('setup-fallback-key').value.trim();
      const _fbm = document.getElementById('setup-fallback-model').value || document.getElementById('setup-fallback-model-search').value.trim();
      if (_fbp) {
        localStorage.setItem('ai-wife-fb-provider', _fbp);
        localStorage.setItem('ai-wife-fb-key', _fbk);
        localStorage.setItem('ai-wife-fb-model', _fbm);
        saveProviderKeys(_fbp, _fbk, _fbm);
      }

      enterBtn.textContent = '連線中...';
      enterBtn.disabled = true;
      try {
        const res = await fetch('/api/config/provider', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: provider,
            base_url: CLOUD_BASE_URLS[provider],
            api_key: apiKey,
            model: cloudModel,
            fallback_provider: document.getElementById('setup-fallback-provider').value,
            fallback_base_url: CLOUD_BASE_URLS[document.getElementById('setup-fallback-provider').value] || '',
            fallback_api_key: document.getElementById('setup-fallback-key').value.trim(),
            fallback_model: document.getElementById('setup-fallback-model').value || document.getElementById('setup-fallback-model-search').value.trim(),
          }),
        });
        const data = await res.json();
        if (!data.success) {
          showToast('設定失敗: ' + (data.error || ''));
          enterBtn.textContent = '進入 💕';
          enterBtn.disabled = false;
          return;
        }
      } catch (e) {
        showToast('連線失敗');
        enterBtn.textContent = '進入 💕';
        enterBtn.disabled = false;
        return;
      }
    } else {
      localStorage.setItem('ai-wife-model', setupModel.value);
    }

    setupScreen.classList.add('hidden');
    enterBtn.textContent = '進入 💕';
    enterBtn.disabled = false;
    updateModelDisplay();

    preloadUiSfx();
    sceneAudioSwitcher(localStorage.getItem('ai-wife-scene') || 'home');

    if (welcomeAudioUrl && isTtsEnabled()) {
      setTimeout(() => {
        if (getCurrentAudio()) { getCurrentAudio().pause(); setCurrentAudio(null); }
        const welcomeAudio = new Audio(welcomeAudioUrl);
        setCurrentAudio(welcomeAudio);
        welcomeAudio.play().catch(() => {});
        setIsPlaying(true);
        welcomeAudio.onended = () => { setIsPlaying(false); setCurrentAudio(null); URL.revokeObjectURL(welcomeAudioUrl); welcomeAudioUrl = null; };
      }, 500);
    }
  });

  // Load saved preferences
  const savedModel = localStorage.getItem('ai-wife-model');
  const savedLang = localStorage.getItem('ai-wife-lang');
  if (savedModel) setupModel.value = savedModel;
  if (savedLang) {
    setupLang.value = savedLang;
    langSel.value = savedLang;
  }

  // ── Model Display (top bar) ──────────────────────────────────────────
  const modelDisplay = document.getElementById('model-display');
  function updateModelDisplay() {
    const prov = localStorage.getItem('ai-wife-provider') || 'ollama';
    const model = localStorage.getItem('ai-wife-cloud-model') || localStorage.getItem('ai-wife-model') || '';
    const short = model.length > 20 ? model.substring(model.lastIndexOf('/') + 1).substring(0, 18) : model;
    if (modelDisplay) modelDisplay.textContent = '📡 ' + (short || 'N/A');
  }
  updateModelDisplay();

  // Restore fallback
  const _sfbp = localStorage.getItem('ai-wife-fb-provider');
  if (_sfbp) {
    const fbSelect = document.getElementById('setup-fallback-provider');
    fbSelect.value = _sfbp;
    const _sfbk = localStorage.getItem('ai-wife-fb-key');
    if (_sfbk) document.getElementById('setup-fallback-key').value = _sfbk;
    fbSelect.dispatchEvent(new Event('change'));
    const _sfbm = localStorage.getItem('ai-wife-fb-model');
    if (_sfbm) {
      setTimeout(() => { document.getElementById('setup-fallback-model').value = _sfbm; }, 2000);
    }
  }

  // ── Render Settings Panel ────────────────────────────────────────────
  const RENDER_PRESETS = {
    '預設': {
      exposure: 1.2, brightness: 0.95, contrast: 1.1, saturation: 1.2, sepia: 0.05,
      ambientR: 1.0, ambientG: 0.85, ambientB: 0.75, ambientInt: 0.8,
      spotInt: 2.0, rimInt: 0.5,
      customLightOn: 0, customLightInt: 2.0,
      customLightR: 1.0, customLightG: 0.9, customLightB: 0.8,
      customLightX: 0, customLightY: 2.0, customLightZ: 2.0,
      shadeWarm: 0.3, shadingToony: 0.8, rimFresnelPower: 3.0, rimLift: 0.3,
    },
    '模式 1 — 暖色動漫': {
      exposure: 0.85, brightness: 1.3, contrast: 0.85, saturation: 1.7, sepia: 0.26,
      ambientR: 1, ambientG: 0, ambientB: 0, ambientInt: 0.7,
      spotInt: 0, rimInt: 1.6,
      customLightOn: 1, customLightInt: 3,
      customLightR: 1, customLightG: 1, customLightB: 1,
      customLightX: 5, customLightY: 6, customLightZ: 5,
      shadeWarm: 0.3, shadingToony: 0.75, rimFresnelPower: 6, rimLift: 0.1,
    },
  };
  const RENDER_DEFAULTS = RENDER_PRESETS['預設'];
  var customLight = null;
  var renderSettings = JSON.parse(localStorage.getItem('ai-wife-render') || 'null') || {...RENDER_DEFAULTS};

  const RENDER_SLIDERS = [
    {section: '📷 後處理'},
    {key: 'exposure', label: '曝光', min: 0.1, max: 5.0, step: 0.05},
    {key: 'brightness', label: '亮度', min: 0.2, max: 3.0, step: 0.05},
    {key: 'contrast', label: '對比度', min: 0.5, max: 3.0, step: 0.05},
    {key: 'saturation', label: '飽和度', min: 0, max: 4.0, step: 0.05},
    {key: 'sepia', label: '暖色調', min: 0, max: 1.0, step: 0.01},
    {section: '💡 主燈光'},
    {key: 'ambientInt', label: '環境光強度', min: 0, max: 5.0, step: 0.1},
    {key: 'ambientR', label: '環境光 R', min: 0, max: 1.0, step: 0.02},
    {key: 'ambientG', label: '環境光 G', min: 0, max: 1.0, step: 0.02},
    {key: 'ambientB', label: '環境光 B', min: 0, max: 1.0, step: 0.02},
    {key: 'spotInt', label: '聚光燈強度', min: 0, max: 10.0, step: 0.1},
    {key: 'rimInt', label: '邊緣光強度', min: 0, max: 5.0, step: 0.1},
    {section: '✨ 自訂光源'},
    {key: 'customLightOn', label: '啟用', min: 0, max: 1, step: 1},
    {key: 'customLightInt', label: '強度', min: 0, max: 10.0, step: 0.1},
    {key: 'customLightR', label: '顏色 R', min: 0, max: 1.0, step: 0.02},
    {key: 'customLightG', label: '顏色 G', min: 0, max: 1.0, step: 0.02},
    {key: 'customLightB', label: '顏色 B', min: 0, max: 1.0, step: 0.02},
    {key: 'customLightX', label: '位置 X', min: -5, max: 5, step: 0.1},
    {key: 'customLightY', label: '位置 Y', min: -2, max: 6, step: 0.1},
    {key: 'customLightZ', label: '位置 Z', min: -5, max: 5, step: 0.1},
    {section: '🎨 材質 (MToon)'},
    {key: 'shadeWarm', label: '陰影暖色', min: 0, max: 1.0, step: 0.05},
    {key: 'shadingToony', label: 'Cel-shade 銳度', min: 0, max: 1.0, step: 0.05},
    {key: 'rimFresnelPower', label: 'Rim Fresnel', min: 0.5, max: 15, step: 0.5},
    {key: 'rimLift', label: 'Rim Lift', min: 0, max: 1.0, step: 0.05},
  ];

  function buildRenderUI() {
    const renderContainer = document.getElementById('render-sliders');
    while (renderContainer.firstChild) renderContainer.removeChild(renderContainer.firstChild);
    RENDER_SLIDERS.forEach(s => {
      if (s.section) {
        const sec = document.createElement('div');
        sec.className = 'render-section';
        sec.textContent = s.section;
        renderContainer.appendChild(sec);
        return;
      }
      const row = document.createElement('div');
      row.className = 'render-slider-row';
      const lbl = document.createElement('label');
      lbl.textContent = s.label;
      row.appendChild(lbl);
      const input = document.createElement('input');
      input.type = 'range';
      input.min = s.min; input.max = s.max; input.step = s.step;
      input.value = renderSettings[s.key];
      const val = document.createElement('span');
      val.className = 'slider-val';
      val.textContent = Number(renderSettings[s.key]).toFixed(2);
      input.addEventListener('input', () => {
        renderSettings[s.key] = parseFloat(input.value);
        val.textContent = Number(input.value).toFixed(2);
        applyRenderSettings();
        localStorage.setItem('ai-wife-render', JSON.stringify(renderSettings));
      });
      row.appendChild(input);
      row.appendChild(val);
      renderContainer.appendChild(row);
    });
  }

  function applyRenderSettings() {
    const s = renderSettings;
    const canvas = document.querySelector('#vrm-container canvas');
    if (canvas) {
      canvas.style.filter = `contrast(${s.contrast}) saturate(${s.saturation}) brightness(${s.brightness}) sepia(${s.sepia})`;
    }
    if (renderer) renderer.toneMappingExposure = s.exposure;
    if (ambientLight) {
      ambientLight.color.setRGB(s.ambientR, s.ambientG, s.ambientB);
      ambientLight.intensity = s.ambientInt;
    }
    if (scene) {
      scene.traverse(obj => {
        if (obj.isSpotLight) obj.intensity = s.spotInt;
        if (obj.isDirectionalLight && obj !== dirLight && obj !== ambientLight) {
          obj.intensity = s.rimInt;
        }
      });
    }
    if (s.customLightOn > 0.5) {
      if (!customLight && scene) {
        customLight = new THREE.PointLight(0xffffff, 2.0, 15, 1);
        scene.add(customLight);
      }
      if (customLight) {
        customLight.color.setRGB(s.customLightR, s.customLightG, s.customLightB);
        customLight.intensity = s.customLightInt;
        customLight.position.set(s.customLightX, s.customLightY, s.customLightZ);
        customLight.visible = true;
      }
    } else if (customLight) {
      customLight.visible = false;
    }
    if (currentVrm) {
      currentVrm.scene.traverse(obj => {
        if (!obj.isMesh || !obj.material || !obj.material.uniforms) return;
        const u = obj.material.uniforms;
        if (u.shadingToonyFactor) u.shadingToonyFactor.value = s.shadingToony;
        if (u.parametricRimFresnelPowerFactor) u.parametricRimFresnelPowerFactor.value = s.rimFresnelPower;
        if (u.parametricRimLiftFactor) u.parametricRimLiftFactor.value = s.rimLift;
      });
    }
  }

  var userPresets = JSON.parse(localStorage.getItem('ai-wife-render-presets') || '{}');
  var allPresets = {...RENDER_PRESETS, ...userPresets};

  function buildPresetSelect() {
    const sel = document.getElementById('render-preset-select');
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    Object.keys(allPresets).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    const customOpt = document.createElement('option');
    customOpt.value = '__custom__';
    customOpt.textContent = '— 自訂 —';
    sel.appendChild(customOpt);
    sel.value = '__custom__';
  }

  document.getElementById('render-preset-select').addEventListener('change', (e) => {
    const name = e.target.value;
    if (name === '__custom__') return;
    const preset = allPresets[name];
    if (preset) {
      renderSettings = {...preset};
      localStorage.setItem('ai-wife-render', JSON.stringify(renderSettings));
      buildRenderUI();
      applyRenderSettings();
    }
  });

  document.getElementById('reset-render-btn').addEventListener('click', () => {
    renderSettings = {...RENDER_DEFAULTS};
    localStorage.setItem('ai-wife-render', JSON.stringify(renderSettings));
    document.getElementById('render-preset-select').value = '預設';
    buildRenderUI();
    applyRenderSettings();
  });

  document.getElementById('save-preset-btn').addEventListener('click', () => {
    const name = prompt('模式名稱：');
    if (!name || !name.trim()) return;
    userPresets[name.trim()] = {...renderSettings};
    allPresets[name.trim()] = {...renderSettings};
    localStorage.setItem('ai-wife-render-presets', JSON.stringify(userPresets));
    buildPresetSelect();
    document.getElementById('render-preset-select').value = name.trim();
    showToast('已儲存：' + name.trim());
  });

  buildPresetSelect();
  buildRenderUI();
  setTimeout(applyRenderSettings, 1000);

  // ── Emotion & Expression Test Buttons ─────────────────────────────────
  const emotionTestSection = document.createElement('div');
  emotionTestSection.style.cssText = 'margin-top:16px;padding-top:12px;border-top:1px solid #333;';
  const emotionTitle = document.createElement('div');
  emotionTitle.style.cssText = 'color:#FF69B4;font-size:13px;font-weight:bold;margin-bottom:8px;';
  emotionTitle.textContent = '🎭 表情 / 情緒測試';
  emotionTestSection.appendChild(emotionTitle);

  // Emotion buttons
  const emotions = [
    { id: 'happy',     label: '😊 開心' },
    { id: 'sad',       label: '😢 難過' },
    { id: 'angry',     label: '😠 生氣' },
    { id: 'surprised', label: '😲 驚訝' },
    { id: 'relaxed',   label: '😌 放鬆' },
    { id: 'horny',     label: '😏 害羞' },
    { id: 'neutral',   label: '😐 普通' },
  ];

  const emotionRow = document.createElement('div');
  emotionRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;';
  for (const emo of emotions) {
    const btn = document.createElement('button');
    btn.textContent = emo.label;
    btn.style.cssText = 'padding:6px 10px;border:1px solid #555;border-radius:8px;background:rgba(30,30,50,0.8);color:#eee;cursor:pointer;font-size:12px;';
    btn.onmouseenter = () => { btn.style.borderColor = '#FF69B4'; };
    btn.onmouseleave = () => { btn.style.borderColor = '#555'; };
    btn.onclick = () => {
      if (setEmotion) setEmotion(emo.id);
      showToast('表情: ' + emo.label);
      // Auto-return to neutral after 3s (except if clicking neutral)
      if (emo.id !== 'neutral') {
        setTimeout(() => { if (setEmotion) setEmotion('neutral'); }, 3000);
      }
    };
    emotionRow.appendChild(btn);
  }
  emotionTestSection.appendChild(emotionRow);

  // Mouth shape test buttons
  const mouthTitle = document.createElement('div');
  mouthTitle.style.cssText = 'color:#FF69B4;font-size:13px;font-weight:bold;margin:8px 0;';
  mouthTitle.textContent = '👄 口形測試';
  emotionTestSection.appendChild(mouthTitle);

  const mouthShapes = [
    { id: 'aa', label: 'あ (aa)' },
    { id: 'ih', label: 'い (ih)' },
    { id: 'ou', label: 'う (ou)' },
    { id: 'ee', label: 'え (ee)' },
    { id: 'oh', label: 'お (oh)' },
  ];

  const mouthRow = document.createElement('div');
  mouthRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px;';
  for (const shape of mouthShapes) {
    const btn = document.createElement('button');
    btn.textContent = shape.label;
    btn.style.cssText = 'padding:6px 12px;border:1px solid #555;border-radius:8px;background:rgba(30,30,50,0.8);color:#eee;cursor:pointer;font-size:12px;';
    btn.onmouseenter = () => { btn.style.borderColor = '#FF69B4'; };
    btn.onmouseleave = () => { btn.style.borderColor = '#555'; };
    btn.onclick = () => {
      if (!setMouthShape) {
        showToast('VRM 尚未載入');
        return;
      }
      setMouthShape(shape.id, 1.0, 2000);
      showToast('口形: ' + shape.label);
    };
    mouthRow.appendChild(btn);
  }
  emotionTestSection.appendChild(mouthRow);

  document.getElementById('tab-render').appendChild(emotionTestSection);

  // ── VRM Character Tab ─────────────────────────────────────────────────
  let currentVrmUrl = savedVrmPath || './static/models/character.vrm';
  const vrmModelList = document.getElementById('vrm-model-list');
  const currentVrmInfo = document.getElementById('current-vrm-info');
  const vrmUploadBtn = document.getElementById('vrm-upload-btn');
  const vrmUploadInput = document.getElementById('vrm-upload-input');
  const vrmUploadStatus = document.getElementById('vrm-upload-status');

  function vrmDisplayName(url) {
    return url.split('/').pop() || url;
  }

  function createVrmModelItem(m, isActive) {
    const item = document.createElement('div');
    item.style.cssText = `display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;border:1px solid ${isActive ? 'var(--accent)' : 'var(--glass-border)'};background:${isActive ? 'var(--accent-muted)' : 'rgba(28,30,42,0.4)'};`;

    const info = document.createElement('div');
    info.style.cssText = 'flex:1;min-width:0;';
    const nameEl = document.createElement('div');
    nameEl.style.cssText = 'font-size:12px;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
    nameEl.textContent = m.filename;
    if (m.isDefault) {
      const tag = document.createElement('span');
      tag.style.cssText = 'color:var(--text-muted);font-size:10px;margin-left:4px;';
      tag.textContent = '(預設)';
      nameEl.appendChild(tag);
    }
    info.appendChild(nameEl);
    if (m.size) {
      const sizeEl = document.createElement('div');
      sizeEl.style.cssText = 'font-size:10px;color:var(--text-muted);';
      sizeEl.textContent = (m.size / 1024 / 1024).toFixed(1) + ' MB';
      info.appendChild(sizeEl);
    }
    item.appendChild(info);

    if (!isActive) {
      const useBtn = document.createElement('button');
      useBtn.textContent = '使用';
      useBtn.style.cssText = 'padding:4px 10px;background:var(--accent);color:var(--bg-primary);border:none;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600;white-space:nowrap;';
      useBtn.onclick = async () => {
        currentVrmUrl = m.url;
        localStorage.setItem('ai-wife-vrm-model', m.url);
        currentVrmInfo.textContent = '目前：' + m.filename;
        await loadModel(m.url);
        refreshVrmList();
      };
      item.appendChild(useBtn);
    } else {
      const badge = document.createElement('span');
      badge.textContent = '使用中';
      badge.style.cssText = 'font-size:10px;color:var(--accent);font-weight:600;white-space:nowrap;';
      item.appendChild(badge);
    }

    if (!m.isDefault) {
      const delBtn = document.createElement('button');
      delBtn.textContent = '刪除';
      delBtn.style.cssText = 'padding:4px 8px;background:rgba(255,80,80,0.2);color:#ff6b6b;border:1px solid rgba(255,80,80,0.3);border-radius:4px;cursor:pointer;font-size:10px;white-space:nowrap;';
      delBtn.onclick = async () => {
        if (!confirm('確定刪除 ' + m.filename + '？')) return;
        try {
          await fetch('/api/vrm/' + encodeURIComponent(m.filename), { method: 'DELETE' });
          if (currentVrmUrl === m.url) {
            currentVrmUrl = './static/models/character.vrm';
            localStorage.setItem('ai-wife-vrm-model', currentVrmUrl);
            currentVrmInfo.textContent = '目前：character.vrm';
            await loadModel(currentVrmUrl);
          }
          refreshVrmList();
        } catch (e) { console.error('Delete failed:', e); }
      };
      item.appendChild(delBtn);
    }
    return item;
  }

  async function refreshVrmList() {
    vrmModelList.textContent = '';
    const models = [];
    models.push({ filename: 'character.vrm', url: './static/models/character.vrm', isDefault: true });
    try {
      const res = await fetch('/api/vrm/list');
      const data = await res.json();
      for (const m of data.models || []) {
        models.push({ filename: m.filename, url: '/vrm/' + encodeURIComponent(m.filename), size: m.size, uploaded_at: m.uploaded_at, isDefault: false });
      }
    } catch (e) { console.warn('Failed to fetch VRM list:', e); }

    for (const m of models) {
      const isActive = currentVrmUrl === m.url || (m.isDefault && currentVrmUrl === './static/models/character.vrm');
      vrmModelList.appendChild(createVrmModelItem(m, isActive));
    }
  }

  vrmUploadBtn.onclick = () => vrmUploadInput.click();
  vrmUploadInput.onchange = async () => {
    const file = vrmUploadInput.files[0];
    if (!file) return;
    vrmUploadStatus.textContent = '上傳中...';
    vrmUploadBtn.disabled = true;
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/vrm/upload', { method: 'POST', body: form });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Upload failed'); }
      const data = await res.json();
      vrmUploadStatus.textContent = '上傳成功：' + data.filename;
      currentVrmUrl = '/vrm/' + encodeURIComponent(data.filename);
      localStorage.setItem('ai-wife-vrm-model', currentVrmUrl);
      currentVrmInfo.textContent = '目前：' + data.filename;
      await loadModel(currentVrmUrl);
      refreshVrmList();
    } catch (e) {
      vrmUploadStatus.textContent = '上傳失敗：' + e.message;
    }
    vrmUploadBtn.disabled = false;
    vrmUploadInput.value = '';
  };

  // PMX upload + convert
  const pmxUploadBtn = document.getElementById('pmx-upload-btn');
  const pmxUploadInput = document.getElementById('pmx-upload-input');
  pmxUploadBtn.onclick = () => pmxUploadInput.click();
  pmxUploadInput.onchange = async () => {
    const file = pmxUploadInput.files[0];
    if (!file) return;
    vrmUploadStatus.textContent = 'PMX 轉換中（可能需要 1-2 分鐘）...';
    vrmUploadStatus.style.color = 'var(--accent)';
    pmxUploadBtn.disabled = true;
    vrmUploadBtn.disabled = true;
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/vrm/convert-pmx', { method: 'POST', body: form });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Conversion failed'); }
      const data = await res.json();
      vrmUploadStatus.textContent = '轉換成功：' + data.filename;
      vrmUploadStatus.style.color = 'var(--accent)';
      currentVrmUrl = data.url;
      localStorage.setItem('ai-wife-vrm-model', currentVrmUrl);
      currentVrmInfo.textContent = '目前：' + data.filename;
      await loadModel(currentVrmUrl);
      refreshVrmList();
    } catch (e) {
      vrmUploadStatus.textContent = 'PMX 轉換失敗：' + e.message;
      vrmUploadStatus.style.color = '#ff6b6b';
    }
    pmxUploadBtn.disabled = false;
    vrmUploadBtn.disabled = false;
    pmxUploadInput.value = '';
  };

  // Load VRM list when character tab is activated
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === 'tab-character') refreshVrmList();
    });
  });

  currentVrmInfo.textContent = '目前：' + vrmDisplayName(currentVrmUrl);

  // ── Animation Management Tab ──────────────────────────────────────────
  const animList = document.getElementById('anim-list');
  const animUploadBtn = document.getElementById('anim-upload-btn');
  const animUploadInput = document.getElementById('anim-upload-input');
  const animUploadStatus = document.getElementById('anim-upload-status');
  const animIdInput = document.getElementById('anim-id-input');
  const animLabelInput = document.getElementById('anim-label-input');
  const animLoopCheck = document.getElementById('anim-loop-check');
  const animReturnSelect = document.getElementById('anim-return-select');

  const CORE_ANIMS = new Set(['idle', 'wave', 'think']);

  function createAnimItem(entry) {
    const item = document.createElement('div');
    item.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:6px;border:1px solid var(--glass-border);background:rgba(28,30,42,0.4);';

    const info = document.createElement('div');
    info.style.cssText = 'flex:1;min-width:0;';
    const nameEl = document.createElement('div');
    nameEl.style.cssText = 'font-size:12px;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
    nameEl.textContent = entry.label + ' (' + entry.id + ')';
    info.appendChild(nameEl);
    const metaEl = document.createElement('div');
    metaEl.style.cssText = 'font-size:10px;color:var(--text-muted);';
    const tags = [];
    if (entry.loop) tags.push('循環');
    if (entry.autoReturnTo) tags.push('→' + entry.autoReturnTo);
    if (CORE_ANIMS.has(entry.id)) tags.push('核心');
    metaEl.textContent = tags.join(' · ');
    info.appendChild(metaEl);
    item.appendChild(info);

    const playBtn = document.createElement('button');
    playBtn.textContent = '▶';
    playBtn.style.cssText = 'padding:4px 8px;background:var(--accent-muted);color:var(--accent);border:1px solid var(--glass-border);border-radius:4px;cursor:pointer;font-size:12px;';
    playBtn.onclick = () => {
      if (animController && animController.actions.has(entry.id)) {
        animController.play(entry.id);
      }
    };
    item.appendChild(playBtn);

    if (!CORE_ANIMS.has(entry.id)) {
      const delBtn = document.createElement('button');
      delBtn.textContent = '刪除';
      delBtn.style.cssText = 'padding:4px 8px;background:rgba(255,80,80,0.2);color:#ff6b6b;border:1px solid rgba(255,80,80,0.3);border-radius:4px;cursor:pointer;font-size:10px;white-space:nowrap;';
      delBtn.onclick = async () => {
        if (!confirm('確定刪除動作 ' + entry.label + '？')) return;
        try {
          const res = await fetch('/api/animations/' + encodeURIComponent(entry.id), { method: 'DELETE' });
          if (!res.ok) { const err = await res.json(); alert(err.detail); return; }
          refreshAnimList();
        } catch (e) { console.error('Delete animation failed:', e); }
      };
      item.appendChild(delBtn);
    }

    return item;
  }

  async function refreshAnimList() {
    animList.textContent = '';
    try {
      const res = await fetch('/api/animations/list');
      const data = await res.json();
      for (const entry of data.animations || []) {
        animList.appendChild(createAnimItem(entry));
      }
    } catch (e) { console.warn('Failed to fetch animations:', e); }
  }

  animUploadBtn.onclick = () => {
    if (!animIdInput.value.trim()) {
      animUploadStatus.textContent = '請先填寫動作 ID';
      animUploadStatus.style.color = '#ff6b6b';
      return;
    }
    animUploadInput.click();
  };

  animUploadInput.onchange = async () => {
    const file = animUploadInput.files[0];
    if (!file) return;
    const id = animIdInput.value.trim();
    if (!id) { animUploadStatus.textContent = '請填寫動作 ID'; return; }

    animUploadStatus.textContent = '上傳中...';
    animUploadStatus.style.color = 'var(--text-muted)';
    animUploadBtn.disabled = true;

    try {
      const form = new FormData();
      form.append('file', file);
      form.append('id', id);
      form.append('label', animLabelInput.value.trim() || id);
      form.append('loop', animLoopCheck.checked);
      form.append('autoReturnTo', animReturnSelect.value);
      form.append('lookAtWeight', '0.6');
      form.append('priority', '2');

      const res = await fetch('/api/animations/upload', { method: 'POST', body: form });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Upload failed'); }
      const data = await res.json();
      animUploadStatus.textContent = '上傳成功：' + data.id;
      animUploadStatus.style.color = 'var(--accent)';

      // Signal the main module to reload animations
      document.dispatchEvent(new CustomEvent('settings:reload-animations'));

      refreshAnimList();
      animIdInput.value = '';
      animLabelInput.value = '';
      animLoopCheck.checked = false;
    } catch (e) {
      animUploadStatus.textContent = '上傳失敗：' + e.message;
      animUploadStatus.style.color = '#ff6b6b';
    }
    animUploadBtn.disabled = false;
    animUploadInput.value = '';
  };

  // Refresh animation list when tab is shown
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === 'tab-animations') refreshAnimList();
    });
  });

  // ── Music Settings Controls ──────────────────────────────────────────
  const bgmToggleBtn = document.getElementById('bgm-toggle');
  const bgmVolSlider = document.getElementById('bgm-vol-slider');
  const bgmSelectEl = document.getElementById('bgm-select');
  const ambientToggleBtn = document.getElementById('ambient-toggle');
  const ambientVolSlider = document.getElementById('ambient-vol-slider');

  bgmToggleBtn.textContent = isBgmEnabled() ? 'ON' : 'OFF';
  bgmToggleBtn.style.color = isBgmEnabled() ? 'var(--accent)' : 'var(--text-muted)';
  bgmVolSlider.value = Math.round(getBgmVolume() * 100);
  ambientVolSlider.value = Math.round(getAmbientVolume() * 100);

  let ambientEnabled = localStorage.getItem('ai-wife-ambient') !== 'off';
  ambientToggleBtn.textContent = ambientEnabled ? 'ON' : 'OFF';
  ambientToggleBtn.style.color = ambientEnabled ? 'var(--accent)' : 'var(--text-muted)';

  let bgmManualUrl = localStorage.getItem('ai-wife-bgm-select') || 'auto';
  bgmSelectEl.value = bgmManualUrl;

  bgmToggleBtn.onclick = () => {
    setBgmEnabled(!isBgmEnabled());
    bgmToggleBtn.textContent = isBgmEnabled() ? 'ON' : 'OFF';
    bgmToggleBtn.style.color = isBgmEnabled() ? 'var(--accent)' : 'var(--text-muted)';
    if (isBgmEnabled()) {
      const url = bgmManualUrl === 'auto' ? (SCENE_BGM[currentSceneTheme] || SCENE_BGM.home) : bgmManualUrl;
      playBgm(url);
    } else if (getBgmAudio()) {
      getBgmAudio().pause();
      setCurrentBgmUrl('');
    }
  };

  bgmVolSlider.oninput = () => {
    setBgmVolume(bgmVolSlider.value / 100);
    if (getBgmGain()) getBgmGain().gain.value = getBgmVolume();
  };

  bgmSelectEl.onchange = () => {
    bgmManualUrl = bgmSelectEl.value;
    localStorage.setItem('ai-wife-bgm-select', bgmManualUrl);
    if (!isBgmEnabled()) return;
    if (bgmManualUrl === 'auto') {
      playBgm(SCENE_BGM[currentSceneTheme] || SCENE_BGM.home);
    } else {
      playBgm(bgmManualUrl);
    }
  };

  ambientToggleBtn.onclick = () => {
    ambientEnabled = !ambientEnabled;
    localStorage.setItem('ai-wife-ambient', ambientEnabled ? 'on' : 'off');
    ambientToggleBtn.textContent = ambientEnabled ? 'ON' : 'OFF';
    ambientToggleBtn.style.color = ambientEnabled ? 'var(--accent)' : 'var(--text-muted)';
    if (ambientEnabled) {
      playAmbient(SCENE_AMBIENT[currentSceneTheme] || null);
    } else {
      stopAmbient();
    }
  };

  ambientVolSlider.oninput = () => {
    setAmbientVolume(ambientVolSlider.value / 100);
    if (getAmbientGain()) getAmbientGain().gain.value = getAmbientVolume();
  };

  // Override sceneAudioSwitcher to respect manual BGM selection
  sceneAudioSwitcher = function(sceneName) {
    if (isBgmEnabled()) {
      if (bgmManualUrl === 'auto') {
        playBgm(SCENE_BGM[sceneName] || SCENE_BGM.home);
      }
    }
    if (ambientEnabled) {
      playAmbient(SCENE_AMBIENT[sceneName] || null);
    }
  };

  // ── Custom BGM Upload ─────────────────────────────────────────────────
  const customBgmList = document.getElementById('custom-bgm-list');
  const bgmUploadBtn = document.getElementById('bgm-upload-btn');
  const bgmUploadInput = document.getElementById('bgm-upload-input');
  const bgmUploadStatusEl = document.getElementById('bgm-upload-status');

  async function refreshCustomBgmList() {
    customBgmList.textContent = '';
    try {
      const res = await fetch('/api/bgm/list');
      const data = await res.json();
      const customs = (data.bgm || []).filter(b => b.custom);
      if (customs.length === 0) {
        customBgmList.textContent = '尚無自訂 BGM';
        customBgmList.style.color = 'var(--text-muted)';
        customBgmList.style.fontSize = '11px';
        return;
      }
      for (const b of customs) {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:4px;background:rgba(28,30,42,0.4);';
        const nameEl = document.createElement('span');
        nameEl.style.cssText = 'flex:1;font-size:11px;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
        nameEl.textContent = b.filename;
        row.appendChild(nameEl);
        const playBtnEl = document.createElement('button');
        playBtnEl.textContent = '▶';
        playBtnEl.style.cssText = 'padding:2px 6px;background:var(--accent-muted);color:var(--accent);border:1px solid var(--glass-border);border-radius:4px;cursor:pointer;font-size:11px;';
        playBtnEl.onclick = () => { bgmSelectEl.value = b.url; bgmManualUrl = b.url; localStorage.setItem('ai-wife-bgm-select', b.url); playBgm(b.url); };
        row.appendChild(playBtnEl);
        const delBtnEl = document.createElement('button');
        delBtnEl.textContent = '刪';
        delBtnEl.style.cssText = 'padding:2px 6px;background:rgba(255,80,80,0.2);color:#ff6b6b;border:1px solid rgba(255,80,80,0.3);border-radius:4px;cursor:pointer;font-size:10px;';
        delBtnEl.onclick = async () => {
          await fetch('/api/bgm/' + encodeURIComponent(b.filename), { method: 'DELETE' });
          refreshCustomBgmList();
        };
        row.appendChild(delBtnEl);
        customBgmList.appendChild(row);
        // Add to <select> if not already there
        let alreadyInSelect = false;
        for (const opt of bgmSelectEl.options) {
          if (opt.value === b.url) { alreadyInSelect = true; break; }
        }
        if (!alreadyInSelect) {
          const opt = document.createElement('option');
          opt.value = b.url;
          opt.textContent = '★ ' + b.filename;
          bgmSelectEl.appendChild(opt);
        }
      }
    } catch (e) { console.warn('Failed to load custom BGM list:', e); }
  }

  bgmUploadBtn.onclick = () => bgmUploadInput.click();
  bgmUploadInput.onchange = async () => {
    const file = bgmUploadInput.files[0];
    if (!file) return;
    bgmUploadStatusEl.textContent = '上傳中...';
    bgmUploadBtn.disabled = true;
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/bgm/upload', { method: 'POST', body: form });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
      const data = await res.json();
      bgmUploadStatusEl.textContent = '上傳成功：' + data.filename;
      refreshCustomBgmList();
    } catch (e) {
      bgmUploadStatusEl.textContent = '上傳失敗：' + e.message;
    }
    bgmUploadBtn.disabled = false;
    bgmUploadInput.value = '';
  };

  // Load custom list when music tab is shown
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab === 'tab-music') refreshCustomBgmList();
    });
  });

  // ── Return to Setup from Settings ───────────────────────────────────
  const settingsTabs = document.querySelector('.tabs');
  const returnBtn = document.createElement('button');
  returnBtn.className = 'tab-btn';
  returnBtn.textContent = '⚙️ 系統';
  returnBtn.onclick = () => {
    settingsModal.classList.remove('visible'); settingsModal.classList.add('hidden');
    setupScreen.classList.remove('hidden');
    enterBtn.classList.remove('ready');
    ['llm','tts','stt','skills'].forEach(t => setStatus('test-' + t, 'pending'));
  };
  settingsTabs.appendChild(returnBtn);

  // Auto-run tests on setup screen show
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((m) => {
      if (m.attributeName === 'class' && !setupScreen.classList.contains('hidden')) {
        ['llm','tts','stt','skills'].forEach(t => setStatus('test-' + t, 'pending'));
        enterBtn.classList.remove('ready');
      }
    });
  });
  observer.observe(setupScreen, { attributes: true });

  // ── Always show setup screen on reload ──────────────────────────────
  setTimeout(() => {
    if (animController && animController.actions.has('wave')) {
      animController.play('wave');
      setTimeout(() => { if (animController) animController.play('idle'); }, 3000);
    }
  }, 2000);
}
