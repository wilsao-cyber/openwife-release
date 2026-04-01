import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:flutter/foundation.dart';

class ApiService extends ChangeNotifier {
  final String baseUrl;
  WebSocketChannel? _wsChannel;
  bool _isConnected = false;
  String _currentClientId = '';

  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;
  Timer? _reconnectTimer;

  bool get isConnected => _isConnected;

  ApiService({required this.baseUrl});

  Future<void> init(String clientId) async {
    _currentClientId = clientId;
    await connectWebSocket(clientId);
  }

  Future<void> connectWebSocket(String clientId) async {
    _currentClientId = clientId;
    _reconnectTimer?.cancel();

    try {
      final wsUrl = baseUrl.replaceFirst('http', 'ws');
      _wsChannel = WebSocketChannel.connect(
        Uri.parse('$wsUrl/ws/$clientId'),
      );
      _isConnected = true;
      _reconnectAttempts = 0;
      notifyListeners();

      _listenToMessages();
    } catch (e) {
      debugPrint('WebSocket connection failed: $e');
      _isConnected = false;
      _scheduleReconnect(clientId);
    }
  }

  void _listenToMessages() {
    if (_wsChannel == null) return;
    _wsChannel!.stream.listen(
      (event) {
        try {
          final data = jsonDecode(event as String) as Map<String, dynamic>;
          _handleIncomingMessage(data);
        } catch (e) {
          debugPrint('Failed to parse WebSocket message: $e');
        }
      },
      onError: (error) {
        debugPrint('WebSocket error: $error');
        _onDisconnected();
      },
      onDone: () {
        debugPrint('WebSocket connection closed');
        _onDisconnected();
      },
    );
  }

  void _handleIncomingMessage(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    switch (type) {
      case 'chat_message':
      case 'text':
        break;
      case 'expression':
        break;
      case 'web_search_result':
        break;
      default:
        break;
    }
  }

  void _onDisconnected() {
    _isConnected = false;
    notifyListeners();
    if (_reconnectAttempts < _maxReconnectAttempts) {
      _scheduleReconnect(_currentClientId);
    }
  }

  void _scheduleReconnect(String clientId) {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(
      const Duration(seconds: 3),
      () {
        _reconnectAttempts++;
        debugPrint('Reconnecting... attempt $_reconnectAttempts/$_maxReconnectAttempts');
        connectWebSocket(clientId);
      },
    );
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
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/email/$action'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(params),
      );
      return jsonDecode(response.body);
    } catch (e) {
      return {'error': e.toString(), 'emails': []};
    }
  }

  Future<Map<String, dynamic>> sendCalendarAction(String action, Map<String, dynamic> params) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/calendar/$action'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(params),
      );
      return jsonDecode(response.body);
    } catch (e) {
      return {'error': e.toString(), 'events': []};
    }
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

  Future<Map<String, dynamic>> uploadVrm(String filePath) async {
    final uri = Uri.parse('$baseUrl/api/vrm/upload');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(await http.MultipartFile.fromPath('file', filePath));
    final response = await request.send();
    final body = await response.stream.bytesToString();
    return jsonDecode(body);
  }

  Future<List<Map<String, dynamic>>> listVrm() async {
    final response = await http.get(Uri.parse('$baseUrl/api/vrm/list'));
    final data = jsonDecode(response.body);
    return List<Map<String, dynamic>>.from(data['models']);
  }

  Future<void> deleteVrm(String filename) async {
    await http.delete(Uri.parse('$baseUrl/api/vrm/$filename'));
  }

  Future<Map<String, dynamic>> sendVisionCapture(List<int> imageData, String language) async {
    final uri = Uri.parse('$baseUrl/api/vision/capture');
    final request = http.MultipartRequest('POST', uri)
      ..fields['language'] = language
      ..files.add(http.MultipartFile.fromBytes('image', imageData, filename: 'frame.jpg'));
    final response = await request.send();
    final body = await response.stream.bytesToString();
    return jsonDecode(body);
  }

  Future<Map<String, dynamic>> sendVisionStream(
    List<int> imageData,
    String language,
    String context,
  ) async {
    final uri = Uri.parse('$baseUrl/api/vision/stream');
    final request = http.MultipartRequest('POST', uri)
      ..fields['language'] = language
      ..fields['context'] = context
      ..files.add(http.MultipartFile.fromBytes('image', imageData, filename: 'frame.jpg'));
    final response = await request.send();
    final body = await response.stream.bytesToString();
    return jsonDecode(body);
  }

  void disconnect() {
    _reconnectTimer?.cancel();
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
