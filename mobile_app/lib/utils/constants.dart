import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

class Constants {
  /// Server base URL, auto-detected per platform:
  /// - Web: localhost (same machine)
  /// - Android emulator: 10.0.2.2 (host loopback alias)
  /// - Real device: LAN IP (change this to your server's IP)
  static String get serverUrl {
    if (kIsWeb) return 'http://localhost:8000';
    if (Platform.isAndroid) return 'http://10.0.2.2:8000';
    return 'http://localhost:8000';
  }

  static String get wsUrl {
    if (kIsWeb) return 'ws://localhost:8000';
    if (Platform.isAndroid) return 'ws://10.0.2.2:8000';
    return 'ws://localhost:8000';
  }

  static const String defaultLanguage = 'zh-TW';
  static const List<String> supportedLanguages = ['zh-TW', 'ja', 'en'];
  static const int maxChatHistory = 50;
  static const Duration connectionTimeout = Duration(seconds: 30);
  static const Duration requestTimeout = Duration(seconds: 60);

  // VRM
  static const String defaultVrmModel = 'assets/models/character.vrm';
  static const int maxVrmFileSizeMB = 50;
  static const int maxVrmFileSizeBytes = maxVrmFileSizeMB * 1024 * 1024;
  static const List<int> gltfMagicBytes = [0x67, 0x6C, 0x54, 0x46]; // glTF

  // Vision
  static const int visionFrameIntervalSeconds = 3;
  static const double visionChangeThreshold = 0.3;

  // i18n Error Messages
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
}
