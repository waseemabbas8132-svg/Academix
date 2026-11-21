import 'package:academix/features/assignments/data/models/assignment.dart';

class SubmissionRevision {
  const SubmissionRevision({
    required this.revisionNumber,
    required this.submissionText,
    required this.status,
    required this.isLate,
    required this.submittedAt,
    required this.marksObtained,
    required this.teacherFeedback,
    required this.gradedAt,
    required this.createdAt,
    this.attachments = const [],
  });

  final int revisionNumber;
  final String? submissionText;
  final String status;
  final bool isLate;
  final DateTime? submittedAt;
  final double? marksObtained;
  final String? teacherFeedback;
  final DateTime? gradedAt;
  final DateTime createdAt;
  final List<AssignmentFile> attachments;

  factory SubmissionRevision.fromJson(Map<String, dynamic> json) =>
      SubmissionRevision(
        revisionNumber: (json['revision_number'] as num).toInt(),
        submissionText: json['submission_text'] as String?,
        status: json['status'] as String,
        isLate: json['is_late'] as bool,
        submittedAt: _parseDate(json['submitted_at']),
        marksObtained: _asNullableDouble(json['marks_obtained']),
        teacherFeedback: json['teacher_feedback'] as String?,
        gradedAt: _parseDate(json['graded_at']),
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        attachments: (json['attachments'] as List? ?? [])
            .map((f) => AssignmentFile.fromJson(f as Map<String, dynamic>))
            .toList(),
      );
}

class Submission {
  const Submission({
    required this.id,
    required this.assignmentId,
    required this.studentId,
    this.studentName,
    required this.submissionText,
    required this.status,
    required this.isLate,
    required this.submittedAt,
    required this.updatedAt,
    required this.marksObtained,
    required this.teacherFeedback,
    required this.gradedAt,
    required this.attachments,
    required this.revisions,
    required this.assignmentTitle,
    required this.totalMarks,
    required this.dueDate,
  });

  final String id;
  final String assignmentId;
  final String studentId;
  final String? studentName;
  final String? submissionText;
  final String status;
  final bool isLate;
  final DateTime? submittedAt;
  final DateTime updatedAt;
  final double? marksObtained;
  final String? teacherFeedback;
  final DateTime? gradedAt;
  final List<AssignmentFile> attachments;
  final List<SubmissionRevision> revisions;
  final String? assignmentTitle;
  final double? totalMarks;
  final DateTime? dueDate;

  factory Submission.fromJson(Map<String, dynamic> json) => Submission(
    id: json['id'] as String,
    assignmentId: json['assignment_id'] as String,
    studentId: json['student_id'] as String,
    studentName: json['student_name'] as String?,
    submissionText: json['submission_text'] as String?,
    status: json['status'] as String,
    isLate: json['is_late'] as bool,
    submittedAt: _parseDate(json['submitted_at']),
    updatedAt: DateTime.parse(json['updated_at'] as String).toLocal(),
    marksObtained: _asNullableDouble(json['marks_obtained']),
    teacherFeedback: json['teacher_feedback'] as String?,
    gradedAt: _parseDate(json['graded_at']),
    attachments: (json['attachments'] as List<dynamic>? ?? [])
        .map((item) => AssignmentFile.fromJson(item as Map<String, dynamic>))
        .toList(),
    revisions: (json['revisions'] as List<dynamic>? ?? [])
        .map(
          (item) => SubmissionRevision.fromJson(item as Map<String, dynamic>),
        )
        .toList(),
    assignmentTitle: json['assignment_title'] as String?,
    totalMarks: _asNullableDouble(json['total_marks']),
    dueDate: _parseDate(json['due_date']),
  );
}

DateTime? _parseDate(Object? value) =>
    value == null ? null : DateTime.parse(value as String).toLocal();

double? _asNullableDouble(Object? value) {
  if (value == null) return null;
  return value is num ? value.toDouble() : double.parse(value.toString());
}
