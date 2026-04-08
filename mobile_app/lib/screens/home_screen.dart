import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart';
import '../models/message.dart';
import '../models/vrm_model.dart';
import '../services/api_service.dart';
import '../services/chat_provider.dart';
import '../services/audio_service.dart';
import '../utils/constants.dart';
import '../utils/theme.dart';
import '../utils/scene_themes.dart';
import '../widgets/vrm_viewer_widget.dart';
import '../widgets/chat_input_bar.dart';
import 'email_screen.dart';
import 'calendar_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => HomeScreenState();
}

class HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    final api = context.read<ApiService>();
    api.init('mobile_client_${DateTime.now().millisecondsSinceEpoch}');
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      const _MainTab(),
      const EmailScreen(),
      const CalendarScreen(),
      const SettingsScreen(),
    ];

    return Scaffold(
      body: screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
        type: BottomNavigationBarType.fixed,
        backgroundColor: AppTheme.surfaceColor,
        selectedItemColor: AppTheme.primaryColor,
        unselectedItemColor: AppTheme.textSecondaryColor,
        selectedFontSize: 11,
        unselectedFontSize: 11,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.email), label: 'Email'),
          BottomNavigationBarItem(icon: Icon(Icons.calendar_today), label: 'Calendar'),
          BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}

// ── Main Tab ──────────────────────────────────────────────────────────

class _MainTab extends StatefulWidget {
  const _MainTab();

  @override
  State<_MainTab> createState() => _MainTabState();
}

class _MainTabState extends State<_MainTab> {
  final vrmController = VrmViewerController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _ttsPlayer = AudioPlayer();
  final List<Message> _messages = [];

  SceneTheme _currentScene = SceneTheme.home;
  bool _ttsEnabled = true;
  bool _isSending = false;
  bool _modelReady = false;
  bool _chatExpanded = true;

  // VRM position/size (user adjustable)
  double _vrmTop = 0;
  double _vrmHeight = 0.45; // fraction of screen height

  @override
  void initState() {
    super.initState();
    _loadPrefs();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    final sceneName = prefs.getString('scene_theme') ?? 'home';
    setState(() {
      _currentScene = SceneTheme.values.firstWhere(
        (e) => e.name == sceneName, orElse: () => SceneTheme.home,
      );
      _ttsEnabled = prefs.getBool('tts_enabled') ?? true;
      _vrmHeight = prefs.getDouble('vrm_height') ?? 0.45;
    });
    if (mounted) {
      final audio = context.read<AudioService>();
      audio.switchScene(sceneConfigs[_currentScene]!);
    }
  }

  void _switchScene(SceneTheme theme) async {
    setState(() => _currentScene = theme);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('scene_theme', theme.name);
    if (mounted) {
      final audio = context.read<AudioService>();
      audio.switchScene(sceneConfigs[theme]!);
    }
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage(String text) async {
    if (text.isEmpty || _isSending) return;
    setState(() {
      _isSending = true;
      _chatExpanded = true;
      _messages.add(Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        role: 'user',
        content: text,
        timestamp: DateTime.now(),
      ));
    });
    _scrollToBottom();

    try {
      final api = context.read<ApiService>();
      final result = await api.sendChat(text, Constants.defaultLanguage);
      final responseText = result['text'] as String? ?? '';
      final emotion = result['emotion'] as String? ?? 'neutral';

      setState(() {
        _messages.add(Message(
          id: '${DateTime.now().millisecondsSinceEpoch}_ai',
          role: 'assistant',
          content: responseText,
          timestamp: DateTime.now(),
          metadata: {'emotion': emotion},
        ));
      });
      _scrollToBottom();

      // VRM expression
      if (_modelReady) {
        final expr = VrmExpression.values.firstWhere(
          (e) => e.name == emotion, orElse: () => VrmExpression.neutral,
        );
        vrmController.setExpression(expr);
        Future.delayed(const Duration(seconds: 4), () {
          if (mounted) vrmController.setExpression(VrmExpression.neutral);
        });
      }

      // Emotion BGM
      if (mounted) {
        final audio = context.read<AudioService>();
        audio.triggerEmotionBgm(emotion, sceneConfigs[_currentScene]!);
      }

      // TTS — backend returns audio_url, play it
      if (_ttsEnabled && responseText.isNotEmpty) {
        _playTTS(responseText, emotion);
      }
    } catch (e) {
      setState(() {
        _messages.add(Message(
          id: '${DateTime.now().millisecondsSinceEpoch}_err',
          role: 'assistant',
          content: '連線錯誤',
          timestamp: DateTime.now(),
        ));
      });
    }

    setState(() => _isSending = false);
    _scrollToBottom();
  }

  Future<void> _playTTS(String text, String emotion) async {
    try {
      final resp = await http.post(
        Uri.parse('${Constants.serverUrl}/api/tts'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'text': text, 'language': Constants.defaultLanguage, 'emotion': emotion}),
      ).timeout(const Duration(seconds: 60));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        final audioUrl = data['audio_url'] as String?;
        // scene_audio is TTS + SFX mixed
        final sceneAudio = data['scene_audio'] as String?;
        final url = sceneAudio ?? audioUrl;
        if (url != null) {
          await _ttsPlayer.play(UrlSource('${Constants.serverUrl}$url'));
        }
      }
    } catch (e) {
      debugPrint('TTS failed: $e');
    }
  }

  @override
  void dispose() {
    vrmController.dispose();
    _scrollController.dispose();
    _ttsPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final config = sceneConfigs[_currentScene]!;
    final screenH = MediaQuery.of(context).size.height;
    final isLandscape = MediaQuery.of(context).orientation == Orientation.landscape;

    return Container(
      color: config.backgroundColor,
      child: SafeArea(
        child: isLandscape ? _buildLandscape(config, screenH) : _buildPortrait(config, screenH),
      ),
    );
  }

  // ── Portrait Layout ──────────────────────────────────────────────────
  Widget _buildPortrait(SceneConfig config, double screenH) {
    return Column(
      children: [
        _buildTopBar(config),
        // VRM character (resizable)
        GestureDetector(
          onVerticalDragUpdate: (d) {
            setState(() {
              _vrmHeight = (_vrmHeight + d.delta.dy / screenH).clamp(0.2, 0.7);
            });
          },
          onVerticalDragEnd: (_) async {
            final prefs = await SharedPreferences.getInstance();
            prefs.setDouble('vrm_height', _vrmHeight);
          },
          child: SizedBox(
            height: screenH * _vrmHeight,
            child: Stack(
              children: [
                Positioned.fill(
                  child: VrmViewerWidget(
                    modelSource: VrmModelSource.asset(Constants.defaultVrmModel),
                    enableInteraction: true,
                    enableIdleAnimation: true,
                    controller: vrmController,
                    onReady: () => setState(() => _modelReady = true),
                    onError: (e) => debugPrint('VRM error: $e'),
                  ),
                ),
                // Resize handle
                Positioned(
                  bottom: 0, left: 0, right: 0,
                  child: Center(
                    child: Container(
                      width: 40, height: 4,
                      margin: const EdgeInsets.only(bottom: 4),
                      decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        // Chat messages
        Expanded(child: _buildChatList()),
        // Input bar
        ChatInputBar(onSend: _sendMessage, enabled: !_isSending),
        if (_isSending) _buildLoadingIndicator(),
      ],
    );
  }

  // ── Landscape Layout ─────────────────────────────────────────────────
  Widget _buildLandscape(SceneConfig config, double screenH) {
    return Row(
      children: [
        // Left: VRM character
        Expanded(
          flex: 5,
          child: Column(
            children: [
              _buildTopBar(config),
              Expanded(
                child: VrmViewerWidget(
                  modelSource: VrmModelSource.asset(Constants.defaultVrmModel),
                  enableInteraction: true,
                  enableIdleAnimation: true,
                  controller: vrmController,
                  onReady: () => setState(() => _modelReady = true),
                  onError: (e) => debugPrint('VRM error: $e'),
                ),
              ),
            ],
          ),
        ),
        // Right: Chat
        Expanded(
          flex: 5,
          child: Container(
            color: Colors.black.withValues(alpha: 0.3),
            child: Column(
              children: [
                Expanded(child: _buildChatList()),
                ChatInputBar(onSend: _sendMessage, enabled: !_isSending),
                if (_isSending) _buildLoadingIndicator(),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ── Shared Widgets ───────────────────────────────────────────────────

  Widget _buildTopBar(SceneConfig config) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      color: Colors.black.withValues(alpha: 0.3),
      child: Row(
        children: [
          // Scene selector
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.black38,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.white12),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<SceneTheme>(
                value: _currentScene,
                dropdownColor: AppTheme.surfaceColor,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                iconEnabledColor: Colors.white54,
                isDense: true,
                items: SceneTheme.values.map((t) {
                  final c = sceneConfigs[t]!;
                  return DropdownMenuItem(value: t, child: Text('${c.emoji} ${c.name}'));
                }).toList(),
                onChanged: (v) { if (v != null) _switchScene(v); },
              ),
            ),
          ),
          const Spacer(),
          // TTS toggle
          IconButton(
            icon: Icon(
              _ttsEnabled ? Icons.volume_up : Icons.volume_off,
              color: _ttsEnabled ? AppTheme.primaryColor : Colors.white38,
              size: 20,
            ),
            onPressed: () => setState(() => _ttsEnabled = !_ttsEnabled),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
          ),
          // Connection status
          Consumer<ApiService>(
            builder: (_, api, __) => Container(
              width: 8, height: 8,
              margin: const EdgeInsets.only(left: 6),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: api.isConnected ? Colors.green : Colors.red,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatList() {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: _messages.length,
      itemBuilder: (context, index) {
        final msg = _messages[index];
        final isUser = msg.role == 'user';
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Align(
            alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primaryColor.withValues(alpha: 0.85)
                    : Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: isUser ? null : Border(left: BorderSide(color: AppTheme.primaryColor, width: 2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (msg.metadata?['emotion'] != null && msg.metadata!['emotion'] != 'neutral')
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Text(
                        msg.metadata!['emotion'],
                        style: TextStyle(fontSize: 10, color: AppTheme.primaryColor, fontWeight: FontWeight.w500),
                      ),
                    ),
                  Text(
                    msg.content,
                    style: TextStyle(
                      color: isUser ? Colors.white : Colors.white.withValues(alpha: 0.9),
                      fontSize: 14, height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(width: 14, height: 14,
            child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primaryColor),
          ),
          const SizedBox(width: 8),
          const Text('思考中...', style: TextStyle(color: Colors.white54, fontSize: 12)),
        ],
      ),
    );
  }
}
