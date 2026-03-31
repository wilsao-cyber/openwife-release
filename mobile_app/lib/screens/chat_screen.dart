import 'package:flutter/material.dart';
import '../models/vrm_model.dart';
import '../widgets/voice_input_button.dart';
import 'home_screen.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, dynamic>> _messages = [];
  bool _isLoading = false;

  void _sendMessage(String text) {
    if (text.trim().isEmpty) return;
    setState(() {
      _messages.add({'role': 'user', 'content': text, 'timestamp': DateTime.now()});
      _isLoading = true;
    });
    _controller.clear();
    _simulateResponse();
  }

  void _simulateResponse() {
    Future.delayed(const Duration(seconds: 1), () {
      _handleChatResponse({'text': '老公說的我都有在聽喔～', 'emotion': 'happy'});
    });
  }

  void _handleChatResponse(Map<String, dynamic> response) {
    final text = response['text'] as String? ?? response['content'] as String? ?? '';
    final emotion = response['emotion'] as String? ?? 'neutral';

    setState(() {
      _messages.add({'role': 'assistant', 'content': text, 'timestamp': DateTime.now()});
      _isLoading = false;
    });

    _setVrmExpression(emotion);
  }

  void _setVrmExpression(String emotion) {
    final homeState = context.findAncestorStateOfType<HomeScreenState>();
    if (homeState == null) return;
    final expression = VrmExpression.values.firstWhere(
      (e) => e.name == emotion,
      orElse: () => VrmExpression.neutral,
    );
    homeState.vrmController.setExpression(expression);

    // Reset to neutral after 5 seconds
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) {
        homeState.vrmController.setExpression(VrmExpression.neutral);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('與老婆聊天')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              reverse: true,
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[_messages.length - 1 - index];
                return _buildMessageBubble(msg);
              },
            ),
          ),
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: CircularProgressIndicator(),
            ),
          _buildInputArea(),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> msg) {
    final isUser = msg['role'] == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        decoration: BoxDecoration(
          color: isUser ? Colors.blue : Colors.pink,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          msg['content'],
          style: const TextStyle(color: Colors.white),
        ),
      ),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          const VoiceInputButton(),
          Expanded(
            child: TextField(
              controller: _controller,
              decoration: const InputDecoration(
                hintText: '輸入訊息...',
                border: OutlineInputBorder(),
              ),
              onSubmitted: _sendMessage,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.send),
            onPressed: () => _sendMessage(_controller.text),
          ),
        ],
      ),
    );
  }
}
