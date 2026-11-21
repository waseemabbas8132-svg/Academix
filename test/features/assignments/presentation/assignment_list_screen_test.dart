import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/presentation/screens/assignment_list_screen.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAuthProvider extends AuthProvider {
  @override
  String? get token => 'test-token';
}

class _FakeAssignmentRepository implements AssignmentRepository {
  _FakeAssignmentRepository({
    this.assignments = const [],
    this.shouldFail = false,
  });

  final List<Assignment> assignments;
  final bool shouldFail;

  @override
  Future<List<Assignment>> listStudentAssignments(String token) async {
    if (shouldFail) throw Exception('network unavailable');
    return assignments;
  }

  @override
  Future<List<Submission>> listMySubmissions(String token) async => [];

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  Future<void> pumpScreen(
    WidgetTester tester,
    AssignmentRepository repository,
  ) async {
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: StudentAssignmentsScreen(repository: repository),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('shows an empty state when the student has no published work', (
    tester,
  ) async {
    await pumpScreen(tester, _FakeAssignmentRepository());

    expect(find.text('No assignments yet'), findsOneWidget);
    expect(find.byTooltip('My submissions'), findsOneWidget);
  });

  testWidgets('shows upcoming assignment data from the repository', (
    tester,
  ) async {
    final assignment = Assignment(
      id: 'assignment-1',
      classId: 'class-1',
      teacherId: 'teacher@academix.app',
      title: 'Read chapter three',
      instructions: 'Submit a short response.',
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
      deadlineStatus: 'upcoming',
    );
    await pumpScreen(
      tester,
      _FakeAssignmentRepository(assignments: [assignment]),
    );

    expect(find.text('Read chapter three'), findsOneWidget);
    expect(find.text('Upcoming'), findsNWidgets(2));
    expect(find.textContaining('20.0 points'), findsOneWidget);
  });

  testWidgets('offers a retry when loading assignments fails', (tester) async {
    await pumpScreen(tester, _FakeAssignmentRepository(shouldFail: true));

    expect(find.text('Unable to load your assignments.'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });
}
