import 'dart:typed_data';

import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';
import 'package:academix/features/assignments/presentation/screens/submission_screens.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAuthProvider extends AuthProvider {
  @override
  String? get token => 'test-token';
}

class _FakeAssignmentRepository implements AssignmentRepository {
  Submission? savedSubmission;
  List<AssignmentUpload> uploadedFiles = [];
  double? gradedMarks;
  String? gradedFeedback;

  @override
  Future<Submission> submit(
    String token,
    String assignmentId, {
    String? text,
    required bool isDraft,
    required List<AssignmentUpload> files,
  }) async {
    uploadedFiles = files;
    return savedSubmission = _submission(status: isDraft ? 'draft' : 'submitted');
  }

  @override
  Future<Submission> gradeSubmission(
    String token,
    String submissionId, {
    double? marks,
    String? feedback,
  }) async {
    gradedMarks = marks;
    gradedFeedback = feedback;
    return savedSubmission = _submission(
      status: marks == null ? 'returned' : 'graded',
      marks: marks,
      feedback: feedback,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeAssignmentFilePicker implements AssignmentFilePicker {
  @override
  Future<List<AssignmentUpload>> pickFiles() async => [
    AssignmentUpload(
      name: 'answer.pdf',
      bytes: Uint8List.fromList([37, 80, 68, 70]),
    ),
  ];

  @override
  Future<void> saveFile(AssignmentFile file, Uint8List bytes) async {}
}

Assignment _assignment() => Assignment(
  id: 'assignment-1',
  classId: 'class-1',
  teacherId: 'teacher@academix.app',
  title: 'Lab report',
  instructions: 'Upload your report.',
  totalMarks: 20,
  dueDate: DateTime.now().add(const Duration(days: 3)),
  isPublished: true,
  isArchived: false,
  createdAt: DateTime.now(),
  updatedAt: DateTime.now(),
  attachments: const [],
  submittedCount: 0,
  pendingCount: 1,
  gradedCount: 0,
);

Submission _submission({
  String status = 'submitted',
  double? marks,
  String? feedback,
}) => Submission(
  id: 'submission-1',
  assignmentId: 'assignment-1',
  studentId: 'student@academix.app',
  submissionText: 'My response',
  status: status,
  isLate: false,
  submittedAt: DateTime.now(),
  updatedAt: DateTime.now(),
  marksObtained: marks,
  teacherFeedback: feedback,
  gradedAt: marks == null ? null : DateTime.now(),
  attachments: const [],
  revisions: const [],
  assignmentTitle: 'Lab report',
  totalMarks: 20,
  dueDate: DateTime.now().add(const Duration(days: 3)),
);

void main() {
  testWidgets('student can attach a file and submit assignment work', (
    tester,
  ) async {
    final repository = _FakeAssignmentRepository();
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => FilledButton(
                onPressed: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => SubmissionFormScreen(
                      assignment: _assignment(),
                      repository: repository,
                      filePicker: _FakeAssignmentFilePicker(),
                    ),
                  ),
                ),
                child: const Text('Open submission form'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open submission form'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Attach files'));
    await tester.pumpAndSettle();

    expect(find.text('answer.pdf'), findsOneWidget);
    await tester.tap(find.text('Submit assignment'));
    await tester.pumpAndSettle();

    expect(find.text('Submission received'), findsOneWidget);
    expect(repository.uploadedFiles, hasLength(1));
    expect(repository.uploadedFiles.single.name, 'answer.pdf');
  });

  testWidgets('teacher grading validates marks and saves feedback', (
    tester,
  ) async {
    final repository = _FakeAssignmentRepository();
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => FilledButton(
                onPressed: () => Navigator.push<Submission>(
                  context,
                  MaterialPageRoute<Submission>(
                    builder: (_) => GradeSubmissionScreen(
                      submission: _submission(),
                      totalMarks: 20,
                      repository: repository,
                    ),
                  ),
                ),
                child: const Text('Open grading form'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Open grading form'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, '21');
    await tester.tap(find.text('Save grade and feedback'));
    await tester.pumpAndSettle();
    expect(find.text('Marks must be between 0 and 20.0.'), findsOneWidget);
    expect(repository.gradedMarks, isNull);

    await tester.enterText(find.byType(TextField).first, '18');
    await tester.enterText(find.byType(TextField).last, 'Clear explanation.');
    await tester.tap(find.text('Save grade and feedback'));
    await tester.pumpAndSettle();

    expect(repository.gradedMarks, 18);
    expect(repository.gradedFeedback, 'Clear explanation.');
  });
}
