import 'package:flutter/material.dart';
import 'constants.dart';

enum SceneTheme { home, sakura, fantasy, night }

class SceneConfig {
  final String id;
  final String name;
  final String emoji;
  final Color backgroundColor;
  final Color overlayColor;
  final String? bgmPath;
  final String? ambientPath;

  const SceneConfig({
    required this.id,
    required this.name,
    required this.emoji,
    required this.backgroundColor,
    required this.overlayColor,
    this.bgmPath,
    this.ambientPath,
  });

  String? get bgmUrl => bgmPath != null ? '${Constants.serverUrl}/audio-assets/$bgmPath' : null;
  String? get ambientUrl => ambientPath != null ? '${Constants.serverUrl}/audio-assets/$ambientPath' : null;
}

const Map<SceneTheme, SceneConfig> sceneConfigs = {
  SceneTheme.home: SceneConfig(
    id: 'home',
    name: '居家',
    emoji: '🏠',
    backgroundColor: Color(0xFF2a1f18),
    overlayColor: Color(0xCC1a1510),
    bgmPath: 'bgm/kks_bgm_07.wav',
  ),
  SceneTheme.sakura: SceneConfig(
    id: 'sakura',
    name: '櫻花',
    emoji: '🌸',
    backgroundColor: Color(0xFF2a1a24),
    overlayColor: Color(0xCC1a1018),
    bgmPath: 'bgm/kks_bgm_08.wav',
    ambientPath: 'se/map/se_ks_action_006.wav',
  ),
  SceneTheme.fantasy: SceneConfig(
    id: 'fantasy',
    name: '奇幻',
    emoji: '✨',
    backgroundColor: Color(0xFF1a1a30),
    overlayColor: Color(0xCC10102a),
    bgmPath: 'bgm/kks_bgm_16.wav',
    ambientPath: 'se/map/se_ks_action_001.wav',
  ),
  SceneTheme.night: SceneConfig(
    id: 'night',
    name: '夜景',
    emoji: '🌃',
    backgroundColor: Color(0xFF0f1018),
    overlayColor: Color(0xCC080810),
    bgmPath: 'bgm/kks_bgm_15.wav',
    ambientPath: 'se/map/se_ks_action_004.wav',
  ),
};
