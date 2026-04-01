# S2: Server Feature Completion — Gemini 3.1 Pro Instructions

## Your Role
You are responsible for completing all stub/mock implementations in the server backend.
Read the full design at: `docs/superpowers/specs/2026-04-01-project-improvement-design.md`

## Important Rules
- **ONLY modify these files**: `server/vision_analyzer.py`, `server/stt_engine.py`, `server/tts_engine.py`, `server/config.py`
- **For `server/tools/calendar_tool.py`**: WAIT until S1 (Claude) finishes async fixes, then add timezone config. Check git log to confirm S1's changes are committed before touching this file.
- **DO NOT touch**: `server/main.py`, `server/agent.py`, `server/llm_client.py`, `server/websocket_manager.py`, `server/tools/email_tool.py`, or anything in `mobile_app/`

---

## Task 1: Vision Analyzer (`server/vision_analyzer.py`)

**Current state**: Returns hardcoded fallback strings. No actual vision model integration.

**What to do**:
1. Read the current file to understand the interface (`analyze_single`, `analyze_stream`, `has_significant_change`)
2. Import `httpx` and `base64`
3. In `analyze_single(image_data, language)`:
   - Base64 encode the image bytes
   - POST to Ollama multimodal endpoint:
     ```python
     async with httpx.AsyncClient(timeout=60.0) as client:
         response = await client.post(
             f"{self.base_url}/api/generate",
             json={
                 "model": self.model,  # "llava" from config
                 "prompt": prompt,     # language-aware prompt
                 "images": [b64_image],
                 "stream": False
             }
         )
     ```
   - Use language-appropriate prompts:
     - zh-TW: "請用繁體中文描述你在這張圖片中看到了什麼"
     - ja: "この画像に何が映っているか日本語で説明してください"
     - en: "Describe what you see in this image"
   - Return the response text
   - On error: return a meaningful error message, NOT a fake response

4. In `has_significant_change(current_frame, previous_frame)`:
   - Keep MD5 hash comparison but make it work with actual image bytes
   - Return bool

5. Read `server/config.py` to find VisionConfig — use `model` and `change_threshold` from config
6. The Ollama base_url should come from LLMConfig (same Ollama instance), currently `http://localhost:9090`

---

## Task 2: STT Mock Fix (`server/stt_engine.py`)

**Current state**: Line ~65, mock `transcribe()` returns hardcoded Chinese text pretending to be a real transcription.

**What to do**:
1. Change mock return to clearly indicate the service isn't running:
   ```python
   return {"text": "[Speech recognition service not available - Whisper not installed]", "language": "en"}
   ```
2. Keep the real Whisper implementation unchanged
3. Add a log warning when falling back to mock

---

## Task 3: TTS Mock Fix (`server/tts_engine.py`)

**Current state**: Mock creates empty files when TTS libraries aren't installed.

**What to do**:
1. Generate a valid WAV file with 0.5s of silence instead of empty file:
   ```python
   import struct
   def _generate_silence_wav(self, output_path: str, duration: float = 0.5):
       sample_rate = self.config.sample_rate  # 22050
       num_samples = int(sample_rate * duration)
       # Write valid WAV header + zero samples
       with open(output_path, 'wb') as f:
           # RIFF header
           data_size = num_samples * 2  # 16-bit samples
           f.write(b'RIFF')
           f.write(struct.pack('<I', 36 + data_size))
           f.write(b'WAVE')
           # fmt chunk
           f.write(b'fmt ')
           f.write(struct.pack('<I', 16))  # chunk size
           f.write(struct.pack('<H', 1))   # PCM
           f.write(struct.pack('<H', 1))   # mono
           f.write(struct.pack('<I', sample_rate))
           f.write(struct.pack('<I', sample_rate * 2))
           f.write(struct.pack('<H', 2))   # block align
           f.write(struct.pack('<H', 16))  # bits per sample
           # data chunk
           f.write(b'data')
           f.write(struct.pack('<I', data_size))
           f.write(b'\x00' * data_size)
   ```
2. Use this in the mock path instead of creating empty files
3. Add a log warning when using mock TTS

---

## Task 4: Viseme Improvement (`server/tts_engine.py`)

**Current state**: `_generate_visemes()` uses only amplitude to pick mouth shapes randomly.

**What to do**:
1. Add a basic phoneme-to-viseme mapping dict:
   ```python
   PHONEME_VISEME_MAP = {
       'a': 'aa', 'o': 'oh', 'u': 'ou', 'e': 'ee', 'i': 'ih',
       'b': 'oh', 'p': 'oh', 'm': 'oh',
       'f': 'ih', 'v': 'ih',
       's': 'ee', 'z': 'ee', 'sh': 'ee',
       't': 'ih', 'd': 'ih', 'n': 'ih', 'l': 'ih',
       'k': 'aa', 'g': 'aa',
       'r': 'oh', 'w': 'ou', 'y': 'ee',
   }
   ```
2. Keep amplitude-based timing, but use the mapping to select more appropriate visemes when text is available
3. Fallback to current random selection if no text context

---

## Task 5: Timezone Config (`server/config.py` + `server/tools/calendar_tool.py`)

**⚠️ DO THIS LAST — after confirming S1 has committed async fixes to calendar_tool.py**

**config.py**:
1. Add `timezone: str = "Asia/Taipei"` to `CalendarConfig` class

**server_config.yaml** (`config/server_config.yaml`):
1. Add `timezone: "Asia/Taipei"` under the `calendar:` section

**calendar_tool.py**:
1. Find all hardcoded `'Asia/Taipei'` strings (lines ~84, ~131, ~133)
2. Replace with `self.config.timezone` (CalendarTool should receive config in __init__)
3. If CalendarTool doesn't have config reference, add it to constructor

---

## Verification

After all changes, run:
```bash
cd /home/wilsao6666/ai_wife_app/server
python -c "from vision_analyzer import VisionAnalyzer; print('vision OK')"
python -c "from tts_engine import TTSEngine; print('tts OK')"
python -c "from stt_engine import STTEngine; print('stt OK')"
python -c "from config import load_config; c = load_config(); print(f'timezone: {c.calendar.timezone}')"
```

## Commit Convention
```
feat: <what you did>
```
One commit per task is fine, or batch related changes together.
