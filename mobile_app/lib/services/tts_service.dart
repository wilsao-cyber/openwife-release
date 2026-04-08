import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'dart:convert';
import '../utils/constants.dart';

/// TTS modes: local (flutter_tts) or remote (backend Voicebox)
enum TTSMode { local, remote }

class TTSService {
  final FlutterTts _flutterTts = FlutterTts();
  final AudioPlayer _audioPlayer = AudioPlayer();
  String _language = 'zh-TW';
  TTSMode mode = TTSMode.remote; // Default to backend TTS

  TTSService() {
    _flutterTts.setLanguage(_language);
    _flutterTts.setSpeechRate(0.5);
    _flutterTts.setPitch(1.2);
  }

  Future<void> setLanguage(String lang) async {
    _language = lang;
    await _flutterTts.setLanguage(lang);
  }

  Future<void> speak(String text, {String emotion = 'neutral'}) async {
    if (mode == TTSMode.remote) {
      await _speakRemote(text, emotion: emotion);
    } else {
      await _flutterTts.speak(text);
    }
  }

  Future<void> _speakRemote(String text, {String emotion = 'neutral'}) async {
    try {
      final response = await http.post(
        Uri.parse('${Constants.serverUrl}/api/tts'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'text': text,
          'language': _language,
          'emotion': emotion,
        }),
      ).timeout(const Duration(seconds: 60));

      if (response.statusCode != 200) return;
      final data = jsonDecode(response.body);
      final audioUrl = data['audio_url'] as String?;
      if (audioUrl == null) return;

      // Download and play audio
      final fullUrl = '${Constants.serverUrl}$audioUrl';
      await _audioPlayer.play(UrlSource(fullUrl));
    } catch (e) {
      debugPrint('Remote TTS failed, falling back to local: $e');
      await _flutterTts.speak(text);
    }
  }

  Future<void> stop() async {
    await _flutterTts.stop();
    await _audioPlayer.stop();
  }

  void dispose() {
    _audioPlayer.dispose();
  }
}

/// STT modes: local (speech_to_text) or remote (backend SenseVoice)
enum STTMode { local, remote }

class STTService {
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _isInitialized = false;
  STTMode mode = STTMode.remote; // Default to backend STT
  String? lastEmotion; // Emotion detected by SenseVoice

  Future<bool> initialize() async {
    _isInitialized = await _speech.initialize();
    return _isInitialized;
  }

  /// Listen using local speech-to-text (partial results, streaming)
  Future<void> listen({Function(String)? onResult}) async {
    if (mode == STTMode.remote) {
      // Remote mode doesn't use streaming — use transcribeAudio instead
      return;
    }
    if (!_isInitialized) await initialize();
    _speech.listen(
      onResult: (result) {
        onResult?.call(result.recognizedWords);
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      partialResults: true,
    );
  }

  /// Send recorded audio bytes to backend SenseVoice for transcription
  Future<String> transcribeAudio(Uint8List audioBytes, {String language = 'zh'}) async {
    lastEmotion = null;
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('${Constants.serverUrl}/api/stt'),
      );
      request.files.add(http.MultipartFile.fromBytes(
        'audio',
        audioBytes,
        filename: 'recording.wav',
      ));
      request.fields['language'] = language;

      final response = await request.send().timeout(const Duration(seconds: 30));
      final body = await response.stream.bytesToString();
      final data = jsonDecode(body);
      lastEmotion = data['emotion'] as String?;
      return data['text'] as String? ?? '';
    } catch (e) {
      debugPrint('Remote STT failed: $e');
      return '';
    }
  }

  Future<void> stop() async {
    await _speech.stop();
  }
}
