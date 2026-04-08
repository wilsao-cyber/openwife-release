import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:provider/provider.dart';
import '../models/memory.dart';
import '../models/heartbeat_job.dart';
import '../services/api_service.dart';
import '../services/vrm_service.dart';
import '../utils/constants.dart';
import '../utils/theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> with SingleTickerProviderStateMixin {
  String _serverUrl = '';
  String _language = 'zh-TW';
  String _ttsProvider = 'cosyvoice';
  bool _autoConnect = true;
  bool _voiceEnabled = true;
  final VrmService _vrmService = VrmService();
  late TextEditingController _serverUrlController;
  late TabController _tabController;

  List<Memory> _memories = [];
  bool _memoriesLoading = false;

  String _soulContent = '';
  String _profileContent = '';
  bool _soulLoading = false;
  bool _soulSaving = false;

  List<HeartbeatJob> _jobs = [];
  bool _jobsLoading = false;
  late TextEditingController _soulController;
  late TextEditingController _profileController;

  @override
  void initState() {
    super.initState();
    _serverUrlController = TextEditingController();
    _tabController = TabController(length: 4, vsync: this);
    _soulController = TextEditingController();
    _profileController = TextEditingController();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _serverUrl = prefs.getString('server_url') ?? Constants.serverUrl;
      _language = prefs.getString('language') ?? 'zh-TW';
      _ttsProvider = prefs.getString('tts_provider') ?? 'cosyvoice';
      _autoConnect = prefs.getBool('auto_connect') ?? true;
      _voiceEnabled = prefs.getBool('voice_enabled') ?? true;
      _serverUrlController.text = _serverUrl;
    });
  }

  Future<void> _saveSetting(String key, dynamic value) async {
    final prefs = await SharedPreferences.getInstance();
    if (value is bool) {
      await prefs.setBool(key, value);
    } else if (value is String) {
      await prefs.setString(key, value);
    }
  }

  Future<void> _loadMemories() async {
    setState(() => _memoriesLoading = true);
    try {
      final api = context.read<ApiService>();
      final data = await api.listMemories(50);
      setState(() {
        _memories = data.map((e) => Memory.fromJson(e)).toList();
        _memoriesLoading = false;
      });
    } catch (e) {
      setState(() => _memoriesLoading = false);
    }
  }

  Future<void> _deleteMemory(int id) async {
    try {
      final api = context.read<ApiService>();
      await api.deleteMemory(id);
      _loadMemories();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(Constants.getError('send_failed', _language))),
        );
      }
    }
  }

  Future<void> _loadSoul() async {
    setState(() => _soulLoading = true);
    try {
      final api = context.read<ApiService>();
      final data = await api.getSoul();
      setState(() {
        _soulContent = data['soul'] as String? ?? '';
        _profileContent = data['profile'] as String? ?? '';
        _soulController.text = _soulContent;
        _profileController.text = _profileContent;
        _soulLoading = false;
      });
    } catch (e) {
      setState(() => _soulLoading = false);
    }
  }

  Future<void> _saveSoul() async {
    setState(() => _soulSaving = true);
    try {
      final api = context.read<ApiService>();
      await api.updateSoul(soul: _soulContent, profile: _profileContent);
      setState(() => _soulSaving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已儲存')),
        );
      }
    } catch (e) {
      setState(() => _soulSaving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(Constants.getError('send_failed', _language))),
        );
      }
    }
  }

  Future<void> _loadJobs() async {
    setState(() => _jobsLoading = true);
    try {
      final api = context.read<ApiService>();
      final data = await api.listHeartbeatJobs();
      setState(() {
        _jobs = data.map((e) => HeartbeatJob.fromJson(e)).toList();
        _jobsLoading = false;
      });
    } catch (e) {
      setState(() => _jobsLoading = false);
    }
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    _tabController.dispose();
    _soulController.dispose();
    _profileController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(icon: Icon(Icons.settings), text: '一般'),
            Tab(icon: Icon(Icons.psychology), text: '記憶'),
            Tab(icon: Icon(Icons.favorite), text: '靈魂'),
            Tab(icon: Icon(Icons.alarm), text: '心跳'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildGeneralTab(),
          _buildMemoryTab(),
          _buildSoulTab(),
          _buildHeartbeatTab(),
        ],
      ),
    );
  }

  Widget _buildGeneralTab() {
    return ListView(
      children: [
        _buildSection('伺服器設定', [
          _buildTextField('伺服器 URL', _serverUrlController, (v) {
            setState(() => _serverUrl = v);
          }),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                Consumer<ApiService>(
                  builder: (_, api, __) => Row(
                    children: [
                      Icon(
                        api.isConnected ? Icons.circle : Icons.circle_outlined,
                        color: api.isConnected ? Colors.green : Colors.red,
                        size: 12,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        api.isConnected ? '已連線' : '未連線',
                        style: TextStyle(
                          fontSize: 12,
                          color: api.isConnected ? Colors.green : Colors.red,
                        ),
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                ElevatedButton.icon(
                  onPressed: () async {
                    final url = _serverUrlController.text.trim();
                    if (url.isEmpty) return;
                    await Constants.setServerUrl(url);
                    if (!mounted) return;
                    final api = context.read<ApiService>();
                    await api.updateBaseUrl(url);
                    final ok = await api.checkConnection();
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(ok ? '連線成功' : '連線失敗')),
                      );
                    }
                  },
                  icon: const Icon(Icons.sync, size: 16),
                  label: const Text('連線'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          SwitchListTile(
            title: const Text('自動連線'),
            subtitle: const Text('啟動時自動連線到伺服器'),
            value: _autoConnect,
            onChanged: (v) {
              setState(() => _autoConnect = v);
              _saveSetting('auto_connect', v);
            },
          ),
        ]),
        _buildSection('語言設定', [
          _buildDropdown('介面語言', _language, {
            'zh-TW': '繁體中文',
            'ja': '日本語',
            'en': 'English',
          }, (v) {
            setState(() => _language = v!);
            _saveSetting('language', v!);
          }),
        ]),
        _buildSection('語音設定', [
          SwitchListTile(
            title: const Text('啟用語音'),
            value: _voiceEnabled,
            onChanged: (v) {
              setState(() => _voiceEnabled = v);
              _saveSetting('voice_enabled', v);
            },
          ),
          _buildDropdown('TTS 引擎', _ttsProvider, {
            'cosyvoice': 'CosyVoice (推薦)',
            'gpt_sovits': 'GPT-SoVITS',
          }, (v) {
            setState(() => _ttsProvider = v!);
            _saveSetting('tts_provider', v!);
          }),
        ]),
        _buildSection('角色設定', [
          ListTile(
            leading: const Icon(Icons.person),
            title: const Text('3D 模型路徑'),
            subtitle: const Text('assets/models/character.glb'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {},
          ),
          ListTile(
            leading: const Icon(Icons.mic),
            title: const Text('聲線樣本'),
            subtitle: const Text('voice_samples/'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {},
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: ElevatedButton.icon(
              onPressed: _changeVrmModel,
              icon: const Icon(Icons.upload_file),
              label: const Text('Upload VRM Model'),
            ),
          ),
        ]),
        _buildSection('關於', [
          const ListTile(
            leading: Icon(Icons.info),
            title: Text('版本'),
            subtitle: Text('1.0.0'),
          ),
        ]),
      ],
    );
  }

  Widget _buildMemoryTab() {
    return RefreshIndicator(
      onRefresh: _loadMemories,
      child: _memoriesLoading
          ? const Center(child: CircularProgressIndicator())
          : _memories.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.psychology, size: 64, color: AppTheme.textSecondaryColor),
                      const SizedBox(height: 16),
                      Text('沒有記憶', style: TextStyle(color: AppTheme.textSecondaryColor)),
                      const SizedBox(height: 8),
                      ElevatedButton(
                        onPressed: _loadMemories,
                        child: const Text('重新載入'),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _memories.length,
                  itemBuilder: (context, index) {
                    final mem = _memories[index];
                    return Dismissible(
                      key: Key('mem_${mem.id}'),
                      direction: DismissDirection.endToStart,
                      background: Container(
                        color: Colors.red,
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 16),
                        child: const Icon(Icons.delete, color: Colors.white),
                      ),
                      onDismissed: (_) => _deleteMemory(mem.id),
                      child: ListTile(
                        leading: Icon(
                          _categoryIcon(mem.category),
                          color: AppTheme.primaryColor,
                        ),
                        title: Text(mem.content, maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: Text(
                          '${mem.category} · 重要性 ${mem.importance.toStringAsFixed(1)} · 存取 ${mem.accessCount} 次',
                          style: const TextStyle(fontSize: 11),
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.red),
                          onPressed: () => _deleteMemory(mem.id),
                        ),
                      ),
                    );
                  },
                ),
    );
  }

  IconData _categoryIcon(String category) {
    switch (category) {
      case 'user_preference':
        return Icons.favorite;
      case 'event':
        return Icons.event;
      case 'fact':
        return Icons.info;
      case 'emotion':
        return Icons.mood;
      case 'habit':
        return Icons.repeat;
      default:
        return Icons.bookmark;
    }
  }

  Widget _buildSoulTab() {
    return RefreshIndicator(
      onRefresh: _loadSoul,
      child: _soulLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    '靈魂定義 (SOUL.md)',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _soulController,
                    onChanged: (v) => _soulContent = v,
                    maxLines: 12,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      hintText: 'AI 老婆的性格定義...',
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    '用戶檔案 (PROFILE.md)',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _profileController,
                    onChanged: (v) => _profileContent = v,
                    maxLines: 8,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      hintText: '用戶的偏好和資訊...',
                    ),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _soulSaving ? null : _saveSoul,
                    icon: _soulSaving
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.save),
                    label: Text(_soulSaving ? '儲存中...' : '儲存'),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildHeartbeatTab() {
    return RefreshIndicator(
      onRefresh: _loadJobs,
      child: _jobsLoading
          ? const Center(child: CircularProgressIndicator())
          : _jobs.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.alarm, size: 64, color: AppTheme.textSecondaryColor),
                      const SizedBox(height: 16),
                      Text('沒有心跳任務', style: TextStyle(color: AppTheme.textSecondaryColor)),
                      const SizedBox(height: 8),
                      ElevatedButton(
                        onPressed: _loadJobs,
                        child: const Text('重新載入'),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _jobs.length,
                  itemBuilder: (context, index) {
                    final job = _jobs[index];
                    return ListTile(
                      leading: Icon(
                        job.enabled ? Icons.alarm_on : Icons.alarm_off,
                        color: job.enabled ? Colors.green : Colors.grey,
                      ),
                      title: Text(job.action, maxLines: 2, overflow: TextOverflow.ellipsis),
                      subtitle: Text(job.cron, style: const TextStyle(fontFamily: 'monospace')),
                      trailing: Switch(
                        value: job.enabled,
                        onChanged: (v) {},
                      ),
                    );
                  },
                ),
    );
  }

  Widget _buildSection(String title, List<Widget> children) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: AppTheme.primaryColor,
            ),
          ),
        ),
        Card(
          margin: const EdgeInsets.symmetric(horizontal: 8),
          child: Column(children: children),
        ),
      ],
    );
  }

  Widget _buildTextField(String label, TextEditingController controller, Function(String) onChanged) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: TextField(
        decoration: InputDecoration(labelText: label),
        controller: controller,
        onChanged: onChanged,
      ),
    );
  }

  Widget _buildDropdown(String label, String value, Map<String, String> options, Function(String?) onChanged) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: DropdownButtonFormField<String>(
        decoration: InputDecoration(labelText: label),
        value: value,
        items: options.entries.map((e) {
          return DropdownMenuItem(value: e.key, child: Text(e.value));
        }).toList(),
        onChanged: onChanged,
      ),
    );
  }

  Future<void> _changeVrmModel() async {
    try {
      final path = await _vrmService.pickAndSaveVrm();
      if (path != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('VRM 模型已更新: ${path.split('/').last}')),
        );
      }
    } on FormatException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('錯誤: ${e.message}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('上傳失敗: $e')),
        );
      }
    }
  }
}
