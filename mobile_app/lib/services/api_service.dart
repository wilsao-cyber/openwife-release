import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter/foundation.dart';

class ApiService extends ChangeNotifier {
  final String baseUrl;
  WebSocketChannel? _wsChannel;
  bool _isConnected = false;

  bool get isConnected => _isConnected;

  ApiService({required this.baseUrl});

  Future<void> connectWebSocket(String clientId) async {
    try {
      final wsUrl = baseUrl.replaceFirst('http', 'ws');
      _wsChannel = WebSocketChannel.connect(
        Uri.parse('$wsUrl/ws/$clientId'),
      );
      _isConnected = true;
      notifyListeners();
    } catch (e) {
      debugPrint('WebSocket connection failed: $e');
      _isConnected = false;
    }
  }

  Stream<dynamic> get messageStream {
    if (_wsChannel == null) return const Stream.empty();
    return _wsChannel!.stream.map((event) => jsonDecode(event));
  }

  void sendMessage(Map<String, dynamic> message) {
    if (_wsChannel != null && _isConnected) {
      _wsChannel!.sink.add(jsonEncode(message));
    }
  }

  Future<Map<String, dynamic>> sendChat(String message, String language) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'message': message, 'language': language}),
    );
    return jsonDecode(response.body);
  }

  Future<String> sendSTT(List<int> audioData) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/stt'),
    );
    request.files.add(http.MultipartFile.fromBytes(
      'audio',
      audioData,
      filename: 'recording.wav',
    ));
    final response = await request.send();
    final body = await response.stream.bytesToString();
    return jsonDecode(body)['text'];
  }

  Future<List<int>> sendTTS(String text, String language) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/tts'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'text': text, 'language': language}),
    );
    return response.bodyBytes;
  }

  Future<Map<String, dynamic>> sendEmailAction(String action, Map<String, dynamic> params) async {
    sendMessage({'type': 'email_action', 'action': action, 'params': params});
    return {};
  }

  Future<Map<String, dynamic>> sendCalendarAction(String action, Map<String, dynamic> params) async {
    sendMessage({'type': 'calendar_action', 'action': action, 'params': params});
    return {};
  }

  Future<Map<String, dynamic>> sendWebSearch(String query) async {
    sendMessage({'type': 'web_search', 'query': query});
    return {};
  }

  Future<Map<String, dynamic>> sendOpenCodeTask(String task, String projectPath) async {
    sendMessage({
      'type': 'opencode_task',
      'task': task,
      'project_path': projectPath,
    });
    return {};
  }

  void disconnect() {
    _wsChannel?.sink.close();
    _isConnected = false;
    notifyListeners();
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
