class CalendarEvent {
  final String id;
  final String title;
  final DateTime startTime;
  final DateTime endTime;
  final String? location;
  final String? description;

  CalendarEvent({
    required this.id,
    required this.title,
    required this.startTime,
    required this.endTime,
    this.location,
    this.description,
  });

  factory CalendarEvent.fromJson(Map<String, dynamic> json) {
    return CalendarEvent(
      id: json['id'] ?? '',
      title: json['summary'] ?? json['title'] ?? '無標題',
      startTime: DateTime.parse(json['start']),
      endTime: DateTime.parse(json['end']),
      location: json['location'],
      description: json['description'],
    );
  }
}
