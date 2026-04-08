import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:shared_preferences/shared_preferences.dart';

class Constants {
  static const String _defaultTailscaleUrl = 'http://100.92.220.125:8000';

  /// Default server URL per platform
  static String get _platformDefault {
    if (kIsWeb) return 'http://localhost:8000';
    if (Platform.isAndroid) return _defaultTailscaleUrl;
    return 'http://localhost:8000';
  }

  // Cached runtime URL (set by init or settings)
  static String _serverUrl = '';
  static String _wsUrl = '';

  static String get serverUrl => _serverUrl.isNotEmpty ? _serverUrl : _platformDefault;
  static String get wsUrl => _wsUrl.isNotEmpty ? _wsUrl : _deriveWsUrl(_platformDefault);

  /// Call once at app startup to load saved URL
  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString('server_url');
    if (saved != null && saved.isNotEmpty) {
      _serverUrl = saved;
      _wsUrl = _deriveWsUrl(saved);
    } else {
      _serverUrl = _platformDefault;
      _wsUrl = _deriveWsUrl(_platformDefault);
    }
  }

  /// Update server URL at runtime (from settings)
  static Future<void> setServerUrl(String url) async {
    url = url.trim();
    if (url.endsWith('/')) url = url.substring(0, url.length - 1);
    _serverUrl = url;
    _wsUrl = _deriveWsUrl(url);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', url);
  }

  static String _deriveWsUrl(String httpUrl) {
    return httpUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
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
