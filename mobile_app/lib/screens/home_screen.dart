import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/vrm_model.dart';
import '../services/api_service.dart';
import '../services/chat_provider.dart';
import '../services/vision_service.dart';
import '../utils/constants.dart';
import '../utils/theme.dart';
import '../widgets/voice_input_button.dart';
import '../widgets/vrm_viewer_widget.dart';
import 'chat_screen.dart';
import 'email_screen.dart';
import 'calendar_screen.dart';
import 'photo_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => HomeScreenState();
}

class HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  String _language = Constants.defaultLanguage;

  final vrmController = VrmViewerController();

  List<Widget> _screens(BuildContext context) => [
    _HomeTab(vrmController: vrmController),
    const ChatScreen(),
    const EmailScreen(),
    const CalendarScreen(),
    const SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    _loadLanguageAndInit();
  }

  Future<void> _loadLanguageAndInit() async {
    final prefs = await SharedPreferences.getInstance();
    final lang = prefs.getString('language') ?? Constants.defaultLanguage;
    if (mounted) {
      setState(() => _language = lang);
    }

    final api = context.read<ApiService>();
    api.init('mobile_client_${DateTime.now().millisecondsSinceEpoch}');
  }

  @override
  void dispose() {
    vrmController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens(context)[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        type: BottomNavigationBarType.fixed,
        backgroundColor: AppTheme.surfaceColor,
        selectedItemColor: AppTheme.primaryColor,
        unselectedItemColor: AppTheme.textSecondaryColor,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.chat), label: 'Chat'),
          BottomNavigationBarItem(icon: Icon(Icons.email), label: 'Email'),
          BottomNavigationBarItem(icon: Icon(Icons.calendar_today), label: 'Calendar'),
          BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}

class _HomeTab extends StatefulWidget {
  final VrmViewerController vrmController;

  const _HomeTab({required this.vrmController});

  @override
  State<_HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<_HomeTab> {
  bool _modelReady = false;
  bool _arSupported = false;
  VisionService? _visionService;
  bool _companionMode = false;

  @override
  void initState() {
    super.initState();
    widget.vrmController.events.listen((event) {
      if (event.type == VrmEventType.arSupported) {
        setState(() => _arSupported = event.data['supported'] == true);
      }
    });
  }

  @override
  void dispose() {
    _visionService?.dispose();
    super.dispose();
  }

  Future<void> _toggleCompanionMode() async {
    if (_companionMode) {
      _visionService?.stopContinuousVision();
      await _visionService?.dispose();
      _visionService = null;
      setState(() => _companionMode = false);
    } else {
      _visionService = VisionService(
        onFrameCaptured: _onVisionFrame,
      );
      await _visionService!.initCamera(front: true);
      _visionService!.startContinuousVision();
      setState(() => _companionMode = true);
    }
  }

  void _onVisionFrame(Uint8List frame) async {
    final apiService = context.read<ApiService>();
    try {
      final result = await apiService.sendVisionStream(
        frame,
        Constants.defaultLanguage,
        '',
      );
      if (result['changed'] == true && result['text'] != null) {
        final emotion = result['emotion'] as String? ?? 'neutral';
        final expression = VrmExpression.values.firstWhere(
          (e) => e.name == emotion,
          orElse: () => VrmExpression.neutral,
        );
        widget.vrmController.setExpression(expression);

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(result['text'])),
          );
        }

        Future.delayed(const Duration(seconds: 5), () {
          widget.vrmController.setExpression(VrmExpression.neutral);
        });
      }
    } catch (e) {
      debugPrint('Vision stream error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              flex: 3,
              child: Consumer<ChatProvider>(
                builder: (context, chatProvider, child) {
                  final expression = chatProvider.currentExpression;
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    if (mounted && _modelReady) {
                      final expr = VrmExpression.values.firstWhere(
                        (e) => e.name == expression,
                        orElse: () => VrmExpression.neutral,
                      );
                      widget.vrmController.setExpression(expr);
                    }
                  });
                  return VrmViewerWidget(
                    modelSource: VrmModelSource.asset(Constants.defaultVrmModel),
                    enableInteraction: true,
                    enableIdleAnimation: true,
                    controller: widget.vrmController,
                    onReady: () => setState(() => _modelReady = true),
                    onError: (e) => debugPrint('VRM error: $e'),
                  );
                },
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Hello~ 老公今天想做什麼呢？',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w500,
                      color: AppTheme.textColor,
                    ),
                  ),
                  const SizedBox(height: 8),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _QuickAction(icon: Icons.mic, label: '語音', onTap: () {}),
                        _QuickAction(icon: Icons.email, label: '郵件', onTap: () {}),
                        _QuickAction(icon: Icons.calendar_today, label: '行程', onTap: () {}),
                        _QuickAction(icon: Icons.search, label: '搜尋', onTap: () {}),
                        _QuickAction(
                          icon: _companionMode ? Icons.visibility : Icons.visibility_off,
                          label: _companionMode ? '關閉' : '陪伴',
                          onTap: _toggleCompanionMode,
                        ),
                        _QuickAction(
                          icon: Icons.camera_alt,
                          label: '合照',
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const PhotoScreen()),
                          ),
                        ),
                        if (_arSupported)
                          _QuickAction(
                            icon: Icons.view_in_ar,
                            label: 'AR',
                            onTap: () => widget.vrmController.enterAR(),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _QuickAction({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: GestureDetector(
        onTap: onTap,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.cardColor,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, size: 22, color: AppTheme.primaryColor),
            ),
            const SizedBox(height: 4),
            Text(label, style: TextStyle(fontSize: 11, color: AppTheme.textSecondaryColor)),
          ],
        ),
      ),
    );
  }
}
