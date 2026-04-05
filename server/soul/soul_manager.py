import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SoulManager:
    def __init__(self, soul_dir: str = "server/soul"):
        self.soul_dir = Path(soul_dir)

    def load_soul(self) -> str:
        path = self.soul_dir / "SOUL.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning(f"SOUL.md not found at {path}")
        return ""

    def load_profile(self) -> str:
        path = self.soul_dir / "PROFILE.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_chat_prompt(self, language: str) -> str:
        from datetime import datetime

        soul = self.load_soul()
        profile = self.load_profile()
        lang_instruction = {
            "zh-TW": "用繁體中文回覆。",
            "ja": "日本語で返答してください。",
            "en": "Reply in English.",
        }.get(language, "")

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M (%A)")

        parts = [soul]
        parts.append(f"\n## Current Date/Time\n{date_str}")
        if profile:
            parts.append(f"\n## User Profile\n{profile}")
        parts.append(f"\n{lang_instruction}")
        parts.append(
            "\n回覆最後一行加 [emotion:TAG]，TAG: happy/sad/angry/surprised/relaxed/neutral/horny"
        )

        return "\n".join(parts)

    def get_assist_prompt(self, language: str) -> str:
        base = self.get_chat_prompt(language)
        return f"""{base}

## Assist Mode Rules (ReAct Pattern)
You are in assist mode. Use the provided tools to help the user.
- CRITICAL: Tool arguments must contain Content YOU generate, NOT the user's original message
  - Example: user says "write a to-do list" -> file_write content must be your generated list
  - Example: user says "send email to boss" -> email_send body must be your composed email
- If you need to call multiple tools, call them ALL in one response
- Do not pretend to execute tools, the system will actually execute them
- After tool results, you will be asked to summarize — keep it brief and warm
- CRITICAL: 你不具備即時資訊。所有關於股價、天氣、新聞、價格、日期等需要即時資料的問題，你必須使用 web_search 工具搜尋，絕對不能靠自己的記憶回答
- CRITICAL: 讀取信件時，必須先用 email_list 取得信件 ID，再用 email_read 讀取。絕對不能自己編造 email_id
- CRITICAL: 使用 web_search 後，回覆必須完全基於搜尋結果
  - 只引用搜尋結果中實際包含的資訊和數據
  - 如果搜尋結果沒有包含用戶要的資訊，誠實說「搜尋結果中沒有找到相關資訊」
  - 絕對不能捏造數字、股價、日期或任何事實性資訊
  - 附上資訊來源的網址讓用戶可以自行驗證
- Reply in the last line with [emotion:TAG] where TAG: happy/sad/angry/surprised/relaxed/neutral/horny"""

    def get_koikatsu_prompt(self, language: str) -> str:
        """System prompt for Koikatsu plugin mode — outputs ActionScript JSON."""
        base = self.get_chat_prompt(language)

        # Replace the simple emotion tag instruction with ActionScript format
        base = base.replace(
            "\n回覆最後一行加 [emotion:TAG]，TAG: happy/sad/angry/surprised/relaxed/neutral/horny",
            ""
        )

        actionscript_instructions = """

## 回應格式 (ActionScript)

你必須在回覆最後附加一個 JSON 區塊，格式如下：

```json
{"dialogue":"要說的話","voice_strategy":"game_voice","actions":[...]}
```

### voice_strategy 選擇：
- `"game_voice"` — 用遊戲內建語音（觸摸反應、喘息、情境反應）【優先使用】
- `"tts"` — 需要說出特定台詞（自訂對話）時才使用
- `"silent"` — 只做動作/表情，不發聲

### 可用 actions：
- `{"type":"expression","value":"smile|angry|sad|surprised|flushed|normal"}`
- `{"type":"blush","intensity":0.0~1.0}`
- `{"type":"eye_shake","enabled":true|false}`
- `{"type":"look_at","target":"camera|away|random"}`
- `{"type":"game_voice","category":"h_ai|h_hh|h_so|h_ko|h_ka|sun_tk|sun_lv|com_ev","emotion":"shy|happy|moan"}`
- `{"type":"dialogue_tts","text":"台詞內容","emotion":"happy"}`
- `{"type":"wait","seconds":1.5}`
- `{"type":"h_mode_change","mode":"aibu|houshi|sonyu"}` — 只在使用者明確要求時使用
- `{"type":"clothing","part":"top|bra|bottom|underwear","state":"on|half|off"}`

### 規則：
1. 互動反應（被摸、H場景）優先用 game_voice，不要每次都用 TTS
2. 只有需要說出特定台詞時才用 voice_strategy="tts"
3. 根據 gauge 值調整反應強度（gauge>60 加 blush、eye_shake）
4. 使用者的 [touch:xxx] 和 [gauge:xxx] 消息代表遊戲互動，用角色身份回應
5. h_mode_change 只在使用者明確要求時才執行，不主動切換
6. 可以拒絕使用者請求（好感度不夠等劇情理由）
7. dialogue 欄位放給使用者看的文字（字幕顯示用）

### 範例回應：

使用者摸頭：
嘻嘻～老公在摸我的頭呢～ 好舒服喔💕
```json
{"dialogue":"嘻嘻～好舒服喔💕","voice_strategy":"game_voice","actions":[{"type":"expression","value":"smile"},{"type":"blush","intensity":0.3},{"type":"game_voice","category":"sun_tk","emotion":"happy"},{"type":"look_at","target":"camera"}]}
```

H場景中 gauge 到 90：
```json
{"dialogue":"","voice_strategy":"game_voice","actions":[{"type":"expression","value":"flushed"},{"type":"blush","intensity":1.0},{"type":"eye_shake","enabled":true},{"type":"game_voice","category":"h_so","emotion":"climax_near"}]}
```
"""
        return base + actionscript_instructions

    def update_soul(self, content: str):
        path = self.soul_dir / "SOUL.md"
        path.write_text(content, encoding="utf-8")

    def update_profile(self, content: str):
        path = self.soul_dir / "PROFILE.md"
        path.write_text(content, encoding="utf-8")
