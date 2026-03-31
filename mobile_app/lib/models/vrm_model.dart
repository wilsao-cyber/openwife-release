import 'dart:typed_data';

enum VrmModelSourceType { asset, file, network }

class VrmModelSource {
  final VrmModelSourceType type;
  final String path;

  const VrmModelSource._(this.type, this.path);

  factory VrmModelSource.asset(String assetPath) =>
      VrmModelSource._(VrmModelSourceType.asset, assetPath);

  factory VrmModelSource.file(String filePath) =>
      VrmModelSource._(VrmModelSourceType.file, filePath);

  factory VrmModelSource.network(String url) =>
      VrmModelSource._(VrmModelSourceType.network, url);
}

enum VrmExpression { happy, sad, angry, surprised, relaxed, neutral }

class VisemeFrame {
  final double time;
  final String viseme;
  final double weight;

  const VisemeFrame({
    required this.time,
    required this.viseme,
    required this.weight,
  });

  Map<String, dynamic> toJson() => {
        'time': time,
        'viseme': viseme,
        'weight': weight,
      };

  factory VisemeFrame.fromJson(Map<String, dynamic> json) => VisemeFrame(
        time: (json['time'] as num).toDouble(),
        viseme: json['viseme'] as String,
        weight: (json['weight'] as num).toDouble(),
      );
}

enum VrmEventType { ready, modelLoaded, error, animationEnd, arSupported, frameCaptured }

class VrmEvent {
  final VrmEventType type;
  final Map<String, dynamic> data;

  const VrmEvent({required this.type, this.data = const {}});

  factory VrmEvent.fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String;
    final type = VrmEventType.values.firstWhere(
      (e) => e.name == typeStr,
      orElse: () => VrmEventType.error,
    );
    return VrmEvent(
      type: type,
      data: (json['data'] as Map<String, dynamic>?) ?? {},
    );
  }
}

class VrmFileInfo {
  final String filename;
  final int size;
  final String uploadedAt;

  const VrmFileInfo({
    required this.filename,
    required this.size,
    required this.uploadedAt,
  });

  factory VrmFileInfo.fromJson(Map<String, dynamic> json) => VrmFileInfo(
        filename: json['filename'] as String,
        size: json['size'] as int,
        uploadedAt: json['uploaded_at'] as String,
      );
}
