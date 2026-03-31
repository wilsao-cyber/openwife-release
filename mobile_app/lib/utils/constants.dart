class Constants {
  static const String serverUrl = 'http://192.168.1.100:8000';
  static const String wsUrl = 'ws://192.168.1.100:8000';
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
}
