class AssignmentFile {
  const AssignmentFile({
    required this.id,
    required this.filename,
    required this.contentType,
    required this.sizeBytes,
    required this.downloadUrl,
  });

  final String id;
  final String filename;
  final String contentType;
  final int sizeBytes;
  final String downloadUrl;

  factory AssignmentFile.fromJson(Map<String, dynamic> json) => AssignmentFile(
    id: json['id'] as String,
    filename: json['filename'] as String,
    contentType: json['content_type'] as String,
    sizeBytes: (json['size_bytes'] as num).toInt(),
    downloadUrl: json['download_url'] as String,
  );
}

class Assignment {
  const Assignment({
    required this.id,
    required this.classId,
    required this.teacherId,
    required this.title,
    required this.instructions,
    required this.totalMarks,
    required this.dueDate,
    required this.isPublished,
    required this.isArchived,
    required this.createdAt,
    required this.updatedAt,
    required this.attachments,
    required this.submittedCount,
    required this.pendingCount,
    required this.gradedCount,
    this.deadlineStatus = 'unknown',
  });

  final String id;
  final String classId;
  final String teacherId;
  final String title;
  final String instructions;
  final double totalMarks;
  final DateTime dueDate;
  final bool isPublished;
  final bool isArchived;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<AssignmentFile> attachments;
  final int submittedCount;
  final int pendingCount;
  final int gradedCount;
  final String deadlineStatus;

  factory Assignment.fromJson(Map<String, dynamic> json) => Assignment(
    id: json['id'] as String,
    classId: json['class_id'] as String,
    teacherId: json['teacher_id'] as String,
    title: json['title'] as String,
    instructions: json['instructions'] as String,
    totalMarks: _asDouble(json['total_marks']),
    dueDate: DateTime.parse(json['due_date'] as String).toLocal(),
    isPublished: json['is_published'] as bool,
    isArchived: json['is_archived'] as bool,
    createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
    updatedAt: DateTime.parse(json['updated_at'] as String).toLocal(),
    attachments: _asList(json['attachments'])
        .map((item) => AssignmentFile.fromJson(item))
        .toList(),
    submittedCount: (json['submitted_count'] as num?)?.toInt() ?? 0,
    pendingCount: (json['pending_count'] as num?)?.toInt() ?? 0,
    gradedCount: (json['graded_count'] as num?)?.toInt() ?? 0,
    deadlineStatus: json['deadline_status'] as String? ?? 'unknown',
  );
}

double _asDouble(Object? value) =>
    value is num ? value.toDouble() : double.parse(value.toString());

List<Map<String, dynamic>> _asList(Object? value) =>
    (value as List<dynamic>? ?? []).cast<Map<String, dynamic>>();

class StudentRubricCriterion {
  const StudentRubricCriterion({
    required this.description,
    required this.marks,
  });

  final String description;
  final double marks;

  factory StudentRubricCriterion.fromJson(Map<String, dynamic> json) =>
      StudentRubricCriterion(
        description: json['description'] as String,
        marks: _asDouble(json['marks']),
      );
}

class StudentRubricQuestion {
  const StudentRubricQuestion({
    required this.questionId,
    required this.prompt,
    required this.maxMarks,
    required this.criteria,
    required this.partialCreditRules,
  });

  final String questionId;
  final String prompt;
  final double maxMarks;
  final List<StudentRubricCriterion> criteria;
  final List<String> partialCreditRules;

  factory StudentRubricQuestion.fromJson(Map<String, dynamic> json) =>
      StudentRubricQuestion(
        questionId: json['question_id'] as String,
        prompt: json['prompt'] as String,
        maxMarks: _asDouble(json['max_marks']),
        criteria: (json['criteria'] as List<dynamic>? ?? [])
            .map(
              (item) =>
                  StudentRubricCriterion.fromJson(item as Map<String, dynamic>),
            )
            .toList(),
        partialCreditRules:
            (json['partial_credit_rules'] as List<dynamic>? ?? [])
                .cast<String>(),
      );
}

class StudentAssignmentRubric {
  const StudentAssignmentRubric({
    required this.assignmentId,
    required this.questions,
  });

  final String assignmentId;
  final List<StudentRubricQuestion> questions;

  factory StudentAssignmentRubric.fromJson(Map<String, dynamic> json) =>
      StudentAssignmentRubric(
        assignmentId: json['assignment_id'] as String,
        questions: (json['questions'] as List<dynamic>)
            .map(
              (item) =>
                  StudentRubricQuestion.fromJson(item as Map<String, dynamic>),
            )
            .toList(),
      );
}
