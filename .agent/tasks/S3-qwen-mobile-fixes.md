# S3: Mobile Fixes — Qwen 3.6 Instructions

## Your Role
You are responsible for fixing all Flutter/Dart issues in the mobile app.
Read the full design at: `docs/superpowers/specs/2026-04-01-project-improvement-design.md`

## Important Rules
- **ONLY modify files in**: `mobile_app/lib/`
- **DO NOT touch**: anything in `server/`, `config/`, or `.agent/`
- All changes are Dart/Flutter only

---

## Task 1: Dynamic Language for Voice Input

**File**: `mobile_app/lib/widgets/voice_input_button.dart`

**Problem**: Line ~114 has `localeId: 'zh_TW'` hardcoded. It ignores the user's language setting.

**What to do**:
1. Add a `language` parameter to `VoiceInputButton`:
   ```dart
   class VoiceInputButton extends StatefulWidget {
     final Function(String) onResult;
     final String language;  // Add this: 'zh-TW', 'ja', or 'en'

     const VoiceInputButton({
       super.key,
       required this.onResult,
       this.language = 'zh-TW',
     });
   ```

2. Create a language mapping method in State:
   ```dart
   String _mapLocale(String lang) {
     switch (lang) {
       case 'zh-TW': return 'zh_TW';
       case 'ja': return 'ja_JP';
       case 'en': return 'en_US';
       default: return 'zh_TW';
     }
   }
   ```

3. Use it in `speech.listen()`:
   ```dart
   localeId: _mapLocale(widget.language),
   ```

4. Update all parents that use `VoiceInputButton` to pass the current language from settings. Check `chat_screen.dart` and `home_screen.dart` — read SharedPreferences for the `language` key.

---

## Task 2: Fix State Management in Chat Screen

**File**: `mobile_app/lib/screens/chat_screen.dart`

**Problem**: Line ~56 uses `context.findAncestorStateOfType<HomeScreenState>()` to access VRM controller. This is fragile and breaks if widget tree changes.

**What to do**:

1. Create a new file `mobile_app/lib/services/chat_provider.dart`:
   ```dart
   import 'package:flutter/foundation.dart';

   class ChatProvider extends ChangeNotifier {
     final List<Map<String, dynamic>> _messages = [];
     String _currentExpression = 'neutral';

     List<Map<String, dynamic>> get messages => List.unmodifiable(_messages);
     String get currentExpression => _currentExpression;

     void addMessage(Map<String, dynamic> message) {
       _messages.add(message);
       if (_messages.length > 50) {
         _messages.removeAt(0);
       }
       notifyListeners();
     }

     void setExpression(String expression) {
       _currentExpression = expression;
       notifyListeners();
     }

     void clearMessages() {
       _messages.clear();
       notifyListeners();
     }
   }
   ```

2. Register it in `mobile_app/lib/main.dart` inside `MultiProvider`:
   ```dart
   ChangeNotifierProvider(create: (_) => ChatProvider()),
   ```

3. In `chat_screen.dart`:
   - Remove the `findAncestorStateOfType` call
   - Use `context.read<ChatProvider>()` to add messages
   - Use `context.watch<ChatProvider>()` to display messages
   - When emotion is detected, call `chatProvider.setExpression(emotion)`

4. In `home_screen.dart`:
   - Watch `ChatProvider.currentExpression` to update VRM viewer
   - When expression changes, call VRM controller's `setExpression()`

---

## Task 3: WebSocket Connection

**File**: `mobile_app/lib/services/api_service.dart`

**Problem**: `connectWebSocket()` method exists but is never called. Real-time messaging doesn't work.

**What to do**:

1. In `ApiService`, add auto-connect on initialization:
   ```dart
   Future<void> init(String clientId) async {
     await connectWebSocket(clientId);
   }
   ```

2. Add reconnection logic:
   ```dart
   int _reconnectAttempts = 0;
   static const int _maxReconnectAttempts = 5;
   Timer? _reconnectTimer;

   void _onDisconnected() {
     if (_reconnectAttempts < _maxReconnectAttempts) {
       _reconnectTimer = Timer(
         Duration(seconds: 3),
         () {
           _reconnectAttempts++;
           connectWebSocket(_currentClientId);
         },
       );
     }
   }

   void _onConnected() {
     _reconnectAttempts = 0;
   }
   ```

3. Handle incoming WebSocket messages — parse JSON, dispatch to appropriate handlers (chat message, expression update, etc.)

4. In `home_screen.dart` `initState()`, call:
   ```dart
   final api = context.read<ApiService>();
   api.init('mobile_client_${DateTime.now().millisecondsSinceEpoch}');
   ```

---

## Task 4: Message Persistence

**File**: `mobile_app/lib/services/api_service.dart` (or the new `chat_provider.dart`)

**Problem**: Chat history is lost when app restarts. Stored only in memory.

**What to do**:

1. Add persistence methods to `ChatProvider`:
   ```dart
   import 'dart:convert';
   import 'package:shared_preferences/shared_preferences.dart';

   static const String _storageKey = 'chat_history';

   Future<void> loadHistory() async {
     final prefs = await SharedPreferences.getInstance();
     final data = prefs.getString(_storageKey);
     if (data != null) {
       final List<dynamic> decoded = jsonDecode(data);
       _messages.clear();
       _messages.addAll(decoded.cast<Map<String, dynamic>>());
       notifyListeners();
     }
   }

   Future<void> _saveHistory() async {
     final prefs = await SharedPreferences.getInstance();
     // Keep only last 50
     final toSave = _messages.length > 50
         ? _messages.sublist(_messages.length - 50)
         : _messages;
     await prefs.setString(_storageKey, jsonEncode(toSave));
   }
   ```

2. Call `_saveHistory()` inside `addMessage()` after adding
3. Call `loadHistory()` in `home_screen.dart` initState or in the provider constructor

---

## Task 5: Error Messages i18n

**Problem**: Error snackbars and banners show Chinese-only error messages.

**What to do**:

1. Create a simple error message map in `mobile_app/lib/utils/constants.dart`:
   ```dart
   static const Map<String, Map<String, String>> errorMessages = {
     'connection_failed': {
       'zh-TW': '連線失敗，請檢查伺服器',
       'ja': '接続に失敗しました。サーバーを確認してください',
       'en': 'Connection failed, please check the server',
     },
     'send_failed': {
       'zh-TW': '發送失敗',
       'ja': '送信に失敗しました',
       'en': 'Failed to send',
     },
     'load_failed': {
       'zh-TW': '載入失敗',
       'ja': '読み込みに失敗しました',
       'en': 'Failed to load',
     },
     'voice_permission': {
       'zh-TW': '需要麥克風權限',
       'ja': 'マイクの権限が必要です',
       'en': 'Microphone permission required',
     },
   };

   static String getError(String key, String language) {
     return errorMessages[key]?[language] ?? errorMessages[key]?['en'] ?? key;
   }
   ```

2. Replace hardcoded Chinese error strings across screens:
   - `email_screen.dart` — loading/send errors
   - `calendar_screen.dart` — loading/create errors
   - `chat_screen.dart` — send errors
   - `voice_input_button.dart` — permission errors

3. Read current language from SharedPreferences (key: `language`, default: `zh-TW`)

---

## Task 6: Enforce Chat History Limit

**File**: `mobile_app/lib/screens/chat_screen.dart`

**Problem**: `Constants.maxChatHistory = 50` is declared but never enforced.

**What to do**:
If you implemented Task 2 correctly (ChatProvider), this is already handled by the `addMessage()` method which trims at 50. Just verify it works.

If chat_screen.dart still manages its own list, add:
```dart
if (_messages.length > Constants.maxChatHistory) {
  _messages.removeAt(0);
}
```

---

## Verification

After all changes:
```bash
cd /home/wilsao6666/ai_wife_app/mobile_app
flutter analyze
```

There should be **zero errors**. Warnings are OK but try to minimize them.

## Commit Convention
```
fix: <what you fixed>
```
You can batch all changes into one commit or split by task — your choice.
