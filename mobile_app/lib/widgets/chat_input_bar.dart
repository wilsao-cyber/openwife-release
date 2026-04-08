import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import '../services/tts_service.dart';
import '../utils/constants.dart';
import '../utils/theme.dart';

class ChatInputBar extends StatefulWidget {
  final Function(String text) onSend;
  final bool enabled;

  const ChatInputBar({super.key, required this.onSend, this.enabled = true});

  @override
  State<ChatInputBar> createState() => _ChatInputBarState();
}

class _ChatInputBarState extends State<ChatInputBar> {
  final TextEditingController _controller = TextEditingController();
  final STTService _sttService = STTService();
  bool _isRecording = false;
  bool _isTranscribing = false;

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty || !widget.enabled) return;
    widget.onSend(text);
    _controller.clear();
  }

  Future<void> _toggleRecording() async {
    if (_isRecording) {
      // Stop recording
      await _sttService.stop();
      setState(() => _isRecording = false);
    } else {
      // Start recording with local STT, send to backend on result
      setState(() => _isRecording = true);
      await _sttService.initialize();
      _sttService.mode = STTMode.local;
      _sttService.listen(onResult: (text) {
        if (text.isNotEmpty) {
          _controller.text = text;
        }
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.6),
        border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.1))),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            // Mic button
            GestureDetector(
              onTap: _toggleRecording,
              child: Container(
                width: 40, height: 40,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _isRecording
                      ? Colors.red.withValues(alpha: 0.3)
                      : Colors.white.withValues(alpha: 0.1),
                  border: Border.all(
                    color: _isRecording ? Colors.red : Colors.white.withValues(alpha: 0.2),
                  ),
                ),
                child: Center(
                  child: _isTranscribing
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(
                          _isRecording ? '⏹️' : '🎙️',
                          style: const TextStyle(fontSize: 18),
                        ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Text input
            Expanded(
              child: TextField(
                controller: _controller,
                enabled: widget.enabled,
                style: const TextStyle(color: Colors.white, fontSize: 14),
                decoration: InputDecoration(
                  hintText: '輸入訊息...',
                  hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.4)),
                  filled: false,
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
                onSubmitted: (_) => _send(),
              ),
            ),
            const SizedBox(width: 8),
            // Send button
            GestureDetector(
              onTap: _send,
              child: Container(
                width: 40, height: 40,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    colors: [AppTheme.primaryColor, AppTheme.secondaryColor],
                  ),
                ),
                child: const Center(
                  child: Icon(Icons.send, color: Colors.white, size: 18),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
