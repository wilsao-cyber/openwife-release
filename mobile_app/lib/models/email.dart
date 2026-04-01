class EmailListItem {
  final String id;
  final String subject;
  final String from;
  final String date;
  final String snippet;
  final bool isUnread;

  EmailListItem({
    required this.id,
    required this.subject,
    required this.from,
    required this.date,
    required this.snippet,
    this.isUnread = false,
  });

  factory EmailListItem.fromJson(Map<String, dynamic> json) {
    return EmailListItem(
      id: json['id'] ?? '',
      subject: json['subject'] ?? '無標題',
      from: json['from'] ?? '',
      date: json['date'] ?? '',
      snippet: json['snippet'] ?? '',
      isUnread: json['is_unread'] ?? false,
    );
  }
}

