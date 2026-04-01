import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';

class ChatProvider extends ChangeNotifier {
  final List<Map<String, dynamic>> _messages = [];
  String _currentExpression = 'neutral';

  List<Map<String, dynamic>> get messages => List.unmodifiable(_messages);
  String get currentExpression => _currentExpression;

  ChatProvider() {
    loadHistory();
  }

  static const String _storageKey = 'chat_history';

  Future<void> loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final data = prefs.getString(_storageKey);
    if (data != null) {
      final List<dynamic> decoded = jsonDecode(data);
      _messages.clear();
      _messages.addAll(decoded.cast<Map<String, dynamic>>());
      notifyListeners();
    }
  }

  Future<void> _saveHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final toSave = _messages.length > Constants.maxChatHistory
        ? _messages.sublist(_messages.length - Constants.maxChatHistory)
        : _messages;
    await prefs.setString(_storageKey, jsonEncode(toSave));
  }

  void addMessage(Map<String, dynamic> message) {
    _messages.add(message);
    if (_messages.length > Constants.maxChatHistory) {
      _messages.removeAt(0);
    }
    _saveHistory();
    notifyListeners();
  }

  void setExpression(String expression) {
    _currentExpression = expression;
    notifyListeners();
  }

  void clearMessages() {
    _messages.clear();
    _saveHistory();
    notifyListeners();
  }
}
