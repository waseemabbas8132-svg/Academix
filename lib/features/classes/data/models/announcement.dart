class Announcement {
  const Announcement({
    required this.id,
    required this.classId,
    required this.teacherId,
    required this.title,
    required this.content,
    required this.isPinned,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String classId;
  final String teacherId;
  final String title;
  final String content;
  final bool isPinned;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory Announcement.fromJson(Map<String, dynamic> json) => Announcement(
    id: json['id'] as String,
    classId: json['class_id'] as String,
    teacherId: json['teacher_id'] as String,
    title: json['title'] as String,
    content: json['content'] as String,
    isPinned: json['is_pinned'] as bool,
    createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
    updatedAt: DateTime.parse(json['updated_at'] as String).toLocal(),
  );
}
