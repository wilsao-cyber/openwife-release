import 'package:flutter/material.dart';
import '../utils/theme.dart';
import '../services/vrm_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _serverUrl = 'http://192.168.1.100:8000';
  String _language = 'zh-TW';
  String _ttsProvider = 'cosyvoice';
  bool _autoConnect = true;
  bool _voiceEnabled = true;
  final VrmService _vrmService = VrmService();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          _buildSection('伺服器設定', [
            _buildTextField('伺服器 URL', _serverUrl, (v) => _serverUrl = v),
            SwitchListTile(
              title: const Text('自動連線'),
              subtitle: const Text('啟動時自動連線到伺服器'),
              value: _autoConnect,
              onChanged: (v) => setState(() => _autoConnect = v),
            ),
          ]),
          _buildSection('語言設定', [
            _buildDropdown('介面語言', _language, {
              'zh-TW': '繁體中文',
              'ja': '日本語',
              'en': 'English',
            }, (v) => setState(() => _language = v!)),
          ]),
          _buildSection('語音設定', [
            SwitchListTile(
              title: const Text('啟用語音'),
              value: _voiceEnabled,
              onChanged: (v) => setState(() => _voiceEnabled = v),
            ),
            _buildDropdown('TTS 引擎', _ttsProvider, {
              'cosyvoice': 'CosyVoice (推薦)',
              'gpt_sovits': 'GPT-SoVITS',
            }, (v) => setState(() => _ttsProvider = v!)),
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

  Widget _buildTextField(String label, String value, Function(String) onChanged) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: TextField(
        decoration: InputDecoration(labelText: label),
        controller: TextEditingController(text: value),
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
}
