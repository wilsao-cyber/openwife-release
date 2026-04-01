import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:table_calendar/table_calendar.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/calendar_event.dart';
import '../services/api_service.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key});

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  CalendarFormat _calendarFormat = CalendarFormat.month;
  DateTime _focusedDay = DateTime.now();
  DateTime? _selectedDay;
  List<CalendarEvent> _events = [];
  String? _error;
  String _language = Constants.defaultLanguage;

  @override
  void initState() {
    super.initState();
    _selectedDay = _focusedDay;
    _loadLanguageAndEvents();
  }

  Future<void> _loadLanguageAndEvents() async {
    final prefs = await SharedPreferences.getInstance();
    _language = prefs.getString('language') ?? Constants.defaultLanguage;
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    try {
      final apiService = context.read<ApiService>();
      final result = await apiService.sendCalendarAction('view_events', {
        'days_ahead': 60,
      });

      if (result['error'] != null) {
        setState(() {
          _events = _getMockEvents();
          _error = '使用離線模式';
        });
      } else if (result['events'] != null) {
        setState(() {
          _events = (result['events'] as List)
              .map((e) => CalendarEvent.fromJson(e as Map<String, dynamic>))
              .toList();
          _error = null;
        });
      } else {
        setState(() => _events = _getMockEvents());
      }
    } catch (e) {
      setState(() {
        _events = _getMockEvents();
        _error = Constants.getError('load_failed', _language);
      });
    }
  }

  List<CalendarEvent> _getMockEvents() {
    return [
      CalendarEvent(
        id: '1',
        title: '團隊會議',
        startTime: DateTime.now().add(const Duration(hours: 2)),
        endTime: DateTime.now().add(const Duration(hours: 3)),
        location: '會議室 A',
        description: '本週進度報告',
      ),
      CalendarEvent(
        id: '2',
        title: '和老婆的約會',
        startTime: DateTime.now().add(const Duration(days: 1, hours: 10)),
        endTime: DateTime.now().add(const Duration(days: 1, hours: 14)),
        location: '信義區',
        description: '週末約會計畫',
      ),
    ];
  }

  List<CalendarEvent> _getEventsForDay(DateTime day) {
    return _events.where((event) {
      return event.startTime.year == day.year &&
          event.startTime.month == day.month &&
          event.startTime.day == day.day;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendar'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadEvents),
          IconButton(icon: const Icon(Icons.add), onPressed: _addEvent),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.orange.withOpacity(0.2),
              child: Text(_error!, style: const TextStyle(fontSize: 12, color: Colors.orange)),
            ),
          TableCalendar<CalendarEvent>(
            firstDay: DateTime.utc(2020, 1, 1),
            lastDay: DateTime.utc(2030, 12, 31),
            focusedDay: _focusedDay,
            calendarFormat: _calendarFormat,
            selectedDayPredicate: (day) => isSameDay(_selectedDay, day),
            onDaySelected: (selectedDay, focusedDay) {
              setState(() {
                _selectedDay = selectedDay;
                _focusedDay = focusedDay;
              });
            },
            onFormatChanged: (format) {
              setState(() => _calendarFormat = format);
            },
            eventLoader: _getEventsForDay,
            calendarStyle: CalendarStyle(
              todayDecoration: BoxDecoration(color: AppTheme.primaryColor, shape: BoxShape.circle),
              selectedDecoration: BoxDecoration(color: AppTheme.secondaryColor, shape: BoxShape.circle),
              markerDecoration: BoxDecoration(color: AppTheme.accentColor, shape: BoxShape.circle),
            ),
          ),
          const Divider(),
          Expanded(
            child: _getEventsForDay(_selectedDay ?? _focusedDay).isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.event_note, size: 48, color: AppTheme.textSecondaryColor),
                        const SizedBox(height: 8),
                        Text('這天沒有行程', style: TextStyle(color: AppTheme.textSecondaryColor)),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: _getEventsForDay(_selectedDay ?? _focusedDay).length,
                    itemBuilder: (context, index) {
                      final event = _getEventsForDay(_selectedDay ?? _focusedDay)[index];
                      return _EventCard(event: event);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  void _addEvent() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _AddEventSheet(onCreated: _loadEvents),
    );
  }
}

class _EventCard extends StatelessWidget {
  final CalendarEvent event;
  const _EventCard({required this.event});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: ListTile(
        leading: Container(
          width: 4, height: 40,
          decoration: BoxDecoration(color: AppTheme.primaryColor, borderRadius: BorderRadius.circular(2)),
        ),
        title: Text(event.title),
        subtitle: Text(
          '${_fmt(event.startTime)} - ${_fmt(event.endTime)}${event.location != null ? ' · ${event.location}' : ''}',
        ),
      ),
    );
  }

  String _fmt(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class _AddEventSheet extends StatefulWidget {
  final VoidCallback onCreated;
  const _AddEventSheet({required this.onCreated});

  @override
  State<_AddEventSheet> createState() => _AddEventSheetState();
}

class _AddEventSheetState extends State<_AddEventSheet> {
  final _titleController = TextEditingController();
  final _locationController = TextEditingController();
  final _descController = TextEditingController();
  bool _saving = false;

  Future<void> _save() async {
    if (_titleController.text.trim().isEmpty) return;
    setState(() => _saving = true);

    try {
      final apiService = context.read<ApiService>();
      final now = DateTime.now();
      await apiService.sendCalendarAction('create', {
        'title': _titleController.text.trim(),
        'location': _locationController.text.trim(),
        'description': _descController.text.trim(),
        'start_time': now.add(const Duration(hours: 1)).toIso8601String(),
        'end_time': now.add(const Duration(hours: 2)).toIso8601String(),
      });
      if (mounted) {
        Navigator.pop(context);
        widget.onCreated();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('行程已新增')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('新增失敗: $e')),
        );
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
        left: 16, right: 16, top: 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(controller: _titleController, decoration: const InputDecoration(labelText: '行程標題')),
          TextField(controller: _locationController, decoration: const InputDecoration(labelText: '地點')),
          TextField(controller: _descController, decoration: const InputDecoration(labelText: '描述'), maxLines: 3),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _saving ? null : _save,
            child: _saving ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('新增行程'),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}
