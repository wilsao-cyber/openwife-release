import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../services/chat_provider.dart';
import '../utils/constants.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/voice_input_button.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _isLoading = false;
  String _language = Constants.defaultLanguage;

  @override
  void initState() {
    super.initState();
    _loadLanguage();
  }

  Future<void> _loadLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    final lang = prefs.getString('language') ?? Constants.defaultLanguage;
    if (mounted) {
      setState(() => _language = lang);
    }
  }

  void _sendMessage(String text) {
    if (text.trim().isEmpty) return;
    final now = DateTime.now().toIso8601String();
    final chatProvider = context.read<ChatProvider>();
    chatProvider.addMessage({'role': 'user', 'content': text, 'timestamp': now});
    setState(() => _isLoading = true);
    _controller.clear();
    _sendToServer(text);
  }

  Future<void> _sendToServer(String text) async {
    try {
      final apiService = context.read<ApiService>();
      final result = await apiService.sendChat(text, _language);
      _handleChatResponse(result);
    } catch (e) {
      final chatProvider = context.read<ChatProvider>();
      final now = DateTime.now().toIso8601String();
      chatProvider.addMessage({
        'role': 'assistant',
        'content': Constants.getError('send_failed', _language),
        'timestamp': now,
      });
      setState(() => _isLoading = false);
    }
  }

  void _handleChatResponse(Map<String, dynamic> response) {
    final text = response['text'] as String? ?? response['content'] as String? ?? '';
    final emotion = response['emotion'] as String? ?? 'neutral';

    final chatProvider = context.read<ChatProvider>();
    final now = DateTime.now().toIso8601String();
    chatProvider.addMessage({'role': 'assistant', 'content': text, 'timestamp': now});
    chatProvider.setExpression(emotion);

    setState(() => _isLoading = false);

    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) {
        chatProvider.setExpression('neutral');
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
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                final messages = chatProvider.messages;
                return ListView.builder(
                  padding: const EdgeInsets.all(16),
                  reverse: true,
                  itemCount: messages.length,
                  itemBuilder: (context, index) {
                    final msg = messages[messages.length - 1 - index];
                    final timestamp = msg['timestamp'] != null
                        ? DateTime.tryParse(msg['timestamp']) ?? DateTime.now()
                        : DateTime.now();
                    return ChatBubble(
                      text: msg['content'] ?? '',
                      isUser: msg['role'] == 'user',
                      timestamp: timestamp,
                    );
                  },
                );
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

  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          VoiceInputButton(
            language: _language,
            onResult: _sendMessage,
          ),
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
