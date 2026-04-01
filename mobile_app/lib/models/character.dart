class Character {
  final String id;
  final String name;
  final String modelPath;
  final String? voiceSamplePath;
  final String language;
  final String personality;

  Character({
    required this.id,
    required this.name,
    required this.modelPath,
    this.voiceSamplePath,
    this.language = 'zh-TW',
    this.personality = 'gentle',
  });

  factory Character.fromJson(Map<String, dynamic> json) {
    return Character(
      id: json['id'] ?? '',
      name: json['name'] ?? 'AI Wife',
      modelPath: json['model_path'] ?? '',
      voiceSamplePath: json['voice_sample_path'],
      language: json['language'] ?? 'zh-TW',
      personality: json['personality'] ?? 'gentle',
    );
  }
}
