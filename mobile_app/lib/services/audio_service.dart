import 'dart:async';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import '../utils/scene_themes.dart';

class AudioService extends ChangeNotifier {
  final AudioPlayer _bgmPlayer = AudioPlayer();
  final AudioPlayer _ambientPlayer = AudioPlayer();

  bool bgmEnabled = true;
  bool ambientEnabled = true;
  double bgmVolume = 0.15;
  double ambientVolume = 0.10;
  String? _currentBgmUrl;
  String? _currentAmbientUrl;
  Timer? _emotionRevertTimer;

  AudioService() {
    _bgmPlayer.setReleaseMode(ReleaseMode.loop);
    _ambientPlayer.setReleaseMode(ReleaseMode.loop);
  }

  Future<void> playBgm(String? url) async {
    if (!bgmEnabled || url == null) return;
    if (url == _currentBgmUrl) return;
    _currentBgmUrl = url;
    await _bgmPlayer.setVolume(bgmVolume);
    await _bgmPlayer.play(UrlSource(url));
  }

  Future<void> stopBgm() async {
    await _bgmPlayer.stop();
    _currentBgmUrl = null;
  }

  Future<void> playAmbient(String? url) async {
    if (!ambientEnabled || url == null) {
      await stopAmbient();
      return;
    }
    if (url == _currentAmbientUrl) return;
    _currentAmbientUrl = url;
    await _ambientPlayer.setVolume(ambientVolume);
    await _ambientPlayer.play(UrlSource(url));
  }

  Future<void> stopAmbient() async {
    await _ambientPlayer.stop();
    _currentAmbientUrl = null;
  }

  Future<void> switchScene(SceneConfig config) async {
    await playBgm(config.bgmUrl);
    await playAmbient(config.ambientUrl);
  }

  /// Temporarily override BGM based on emotion, revert after duration
  Future<void> triggerEmotionBgm(String emotion, SceneConfig currentScene, {Duration revert = const Duration(seconds: 30)}) async {
    const emotionBgmPaths = {
      'sad': 'bgm/kks_bgm_17.wav',
      'happy': 'bgm/kks_bgm_08.wav',
      'horny': 'bgm/kks_bgm_02.wav',
    };
    final path = emotionBgmPaths[emotion];
    if (path == null) return;

    // Build full URL using same pattern as SceneConfig
    final url = '${currentScene.bgmUrl?.replaceAll(RegExp(r'/audio-assets/.*'), '')}/audio-assets/$path';
    await playBgm(url);

    _emotionRevertTimer?.cancel();
    _emotionRevertTimer = Timer(revert, () {
      playBgm(currentScene.bgmUrl);
    });
  }

  void setBgmVolume(double vol) {
    bgmVolume = vol;
    _bgmPlayer.setVolume(vol);
    notifyListeners();
  }

  void setAmbientVolume(double vol) {
    ambientVolume = vol;
    _ambientPlayer.setVolume(vol);
    notifyListeners();
  }

  void toggleBgm(bool enabled) {
    bgmEnabled = enabled;
    if (!enabled) stopBgm();
    notifyListeners();
  }

  void toggleAmbient(bool enabled) {
    ambientEnabled = enabled;
    if (!enabled) stopAmbient();
    notifyListeners();
  }

  @override
  void dispose() {
    _emotionRevertTimer?.cancel();
    _bgmPlayer.dispose();
    _ambientPlayer.dispose();
    super.dispose();
  }
}
