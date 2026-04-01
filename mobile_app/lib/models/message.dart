class Message {
  final String id;
  final String role;
  final String content;
  final DateTime timestamp;
  final String? audioUrl;
  final Map<String, dynamic>? metadata;

  Message({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.audioUrl,
    this.metadata,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      timestamp: json['timestamp'] != null
          ? DateTime.parse(json['timestamp'])
          : DateTime.now(),
      audioUrl: json['audio_url'],
      metadata: json['metadata'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'role': role,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'audio_url': audioUrl,
      'metadata': metadata,
    };
  }

  bool get isUser => role == 'user';
}
