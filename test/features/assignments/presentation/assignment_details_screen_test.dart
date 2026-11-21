import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_details_screen.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _Auth extends AuthProvider {
  @override
  String? get token => 'student-token';
}

class _Assignments implements AssignmentRepository {
  int rubricCalls = 0;

  @override
  Future<Assignment> getAssignment(String token, String assignmentId) async =>
      _assignment;

  @override
  Future<List<Submission>> listMySubmissions(String token) async => [];

  @override
  Future<StudentAssignmentRubric> getStudentRubric(
    String token,
    String assignmentId,
  ) async {
    rubricCalls++;
    return const StudentAssignmentRubric(
      assignmentId: 'assignment-1',
      questions: [
        StudentRubricQuestion(
          questionId: 'q1',
          prompt: 'Explain evaporation.',
          maxMarks: 10,
          criteria: [
            StudentRubricCriterion(
              description: 'Names the energy source',
              marks: 2,
            ),
          ],
          partialCreditRules: ['Award partial credit for correct terminology.'],
        ),
      ],
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

final _assignment = Assignment(
  id: 'assignment-1',
  classId: 'class-1',
  teacherId: 'teacher@academix.app',
  title: 'Water cycle',
  instructions: 'Answer the question.',
  totalMarks: 10,
  dueDate: DateTime(2026, 11, 26),
  isPublished: true,
  isArchived: false,
  createdAt: DateTime(2026, 11, 1),
  updatedAt: DateTime(2026, 11, 1),
  attachments: const [],
  submittedCount: 0,
  pendingCount: 1,
  gradedCount: 0,
);

void main() {
  testWidgets('students see published questions and scoring guidance', (
    tester,
  ) async {
    final repository = _Assignments();
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _Auth(),
        child: MaterialApp(
          home: AssignmentDetailsScreen(
            assignment: _assignment,
            isTeacher: false,
            repository: repository,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(repository.rubricCalls, 1);
    expect(find.text('Question rubric'), findsOneWidget);
    expect(find.text('Explain evaporation.'), findsOneWidget);
    expect(find.text('Names the energy source · 2.0 marks'), findsOneWidget);
    expect(
      find.text('Award partial credit for correct terminology.'),
      findsOneWidget,
    );
  });
}
