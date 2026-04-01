import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import '../utils/constants.dart';

class VoiceInputButton extends StatefulWidget {
  final Function(String text)? onResult;
  final String language;

  const VoiceInputButton({super.key, this.onResult, this.language = 'zh-TW'});

  @override
  State<VoiceInputButton> createState() => _VoiceInputButtonState();
}

class _VoiceInputButtonState extends State<VoiceInputButton>
    with SingleTickerProviderStateMixin {
  final SpeechToText _speech = SpeechToText();

  bool _isInitialized = false;
  bool _isListening = false;

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.35).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    if (_isListening) {
      _speech.stop();
    }
    super.dispose();
  }

  // ── Initialization ──────────────────────────────────────────────────────────

  Future<bool> _ensureInitialized() async {
    if (_isInitialized) return true;

    final available = await _speech.initialize(
      onError: _onSpeechError,
      onStatus: _onSpeechStatus,
    );

    if (available) {
      setState(() => _isInitialized = true);
    } else {
      _showSnackbar(Constants.getError('voice_permission', widget.language));
    }

    return available;
  }

  // ── Callbacks ────────────────────────────────────────────────────────────────

  void _onSpeechResult(SpeechRecognitionResult result) {
    if (result.finalResult && result.recognizedWords.isNotEmpty) {
      widget.onResult?.call(result.recognizedWords);
    }
  }

  void _onSpeechError(SpeechRecognitionError error) {
    // permanent-error or no-match are common non-critical events; only surface
    // errors the user can act on.
    if (error.errorMsg == 'error_permission_blocked' ||
        error.errorMsg == 'error_permission_denied') {
      _showSnackbar(Constants.getError('voice_permission', widget.language));
    }
    if (_isListening) {
      setState(() => _isListening = false);
      _pulseController.stop();
      _pulseController.reset();
    }
  }

  void _onSpeechStatus(String status) {
    // 'done' / 'notListening' fires after silence auto-stop or manual stop
    if (status == 'done' || status == 'notListening') {
      if (_isListening) {
        setState(() => _isListening = false);
        _pulseController.stop();
        _pulseController.reset();
      }
    }
  }

  // ── Toggle ───────────────────────────────────────────────────────────────────

  String _mapLocale(String lang) {
    switch (lang) {
      case 'zh-TW': return 'zh_TW';
      case 'ja': return 'ja_JP';
      case 'en': return 'en_US';
      default: return 'zh_TW';
    }
  }

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _speech.stop();
      setState(() => _isListening = false);
      _pulseController.stop();
      _pulseController.reset();
      return;
    }

    final ready = await _ensureInitialized();
    if (!ready) return;

    await _speech.listen(
      onResult: _onSpeechResult,
      localeId: _mapLocale(widget.language),
      listenMode: ListenMode.confirmation,
      pauseFor: const Duration(seconds: 3),
      cancelOnError: false,
    );

    setState(() => _isListening = true);
    _pulseController.repeat(reverse: true);
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  void _showSnackbar(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _toggleListening,
      child: AnimatedBuilder(
        animation: _pulseAnimation,
        builder: (context, child) {
          final scale = _isListening ? _pulseAnimation.value : 1.0;
          return Transform.scale(
            scale: scale,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isListening ? Colors.red : Colors.pink,
                boxShadow: _isListening
                    ? [
                        BoxShadow(
                          color: Colors.red.withOpacity(0.55),
                          blurRadius: 18,
                          spreadRadius: 6,
                        ),
                      ]
                    : [],
              ),
              child: Icon(
                _isListening ? Icons.mic : Icons.mic_none,
                color: Colors.white,
                size: 28,
              ),
            ),
          );
        },
      ),
    );
  }
}
