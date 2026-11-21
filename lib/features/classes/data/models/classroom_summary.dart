class ClassroomSummary {
  const ClassroomSummary({
    required this.id,
    required this.name,
    required this.section,
    required this.subject,
    this.room,
    this.description,
    this.teacherId,
    this.classCode,
  });

  final String id;
  final String name;
  final String section;
  final String subject;
  final String? room;
  final String? description;
  final String? teacherId;
  final String? classCode;

  factory ClassroomSummary.fromJson(Map<String, dynamic> json) =>
      ClassroomSummary(
        id: json['id'] as String,
        name: json['name'] as String,
        section: json['section'] as String,
        subject: json['subject'] as String,
        room: json['room'] as String?,
        description: json['description'] as String?,
        teacherId: json['teacher_id'] as String?,
        classCode: json['class_code'] as String?,
      );
}
