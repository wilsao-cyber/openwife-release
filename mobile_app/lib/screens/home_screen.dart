import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/vrm_model.dart';
import '../services/api_service.dart';
import '../utils/constants.dart';
import '../utils/theme.dart';
import '../widgets/voice_input_button.dart';
import '../widgets/vrm_viewer_widget.dart';
import 'chat_screen.dart';
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

  final vrmController = VrmViewerController();

  List<Widget> get _screens => [
    _HomeTab(vrmController: vrmController),
    const ChatScreen(),
    const EmailScreen(),
    const CalendarScreen(),
    const SettingsScreen(),
  ];

  @override
  void dispose() {
    vrmController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
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
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              flex: 3,
              child: VrmViewerWidget(
                modelSource: VrmModelSource.asset(Constants.defaultVrmModel),
                enableInteraction: true,
                enableIdleAnimation: true,
                controller: widget.vrmController,
                onReady: () => setState(() => _modelReady = true),
                onError: (e) => debugPrint('VRM error: $e'),
              ),
            ),
            Expanded(
              flex: 1,
              child: Container(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Text(
                      'Hello~ 老公今天想做什麼呢？',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.textColor,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        _QuickAction(icon: Icons.mic, label: '語音對話', onTap: () {}),
                        _QuickAction(icon: Icons.email, label: '查看郵件', onTap: () {}),
                        _QuickAction(icon: Icons.calendar_today, label: '今日行程', onTap: () {}),
                        _QuickAction(icon: Icons.search, label: '搜尋資料', onTap: () {}),
                        if (_arSupported)
                          _QuickAction(
                            icon: Icons.view_in_ar,
                            label: 'AR',
                            onTap: () => widget.vrmController.enterAR(),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    const VoiceInputButton(),
                  ],
                ),
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
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.cardColor,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: AppTheme.primaryColor),
          ),
          const SizedBox(height: 4),
          Text(label, style: TextStyle(fontSize: 12, color: AppTheme.textSecondaryColor)),
        ],
      ),
    );
  }
}
