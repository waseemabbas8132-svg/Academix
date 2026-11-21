import 'package:academix/features/assignments/data/repositories/demo_ai_evaluation_repository.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/shared/widgets/academic_dashboard.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAuthProvider extends AuthProvider {
  @override
  String? get token => 'test-token';
}

class _DashboardRepository extends ReviewRepository {
  @override
  Future<Map<String, dynamic>> get(
    String token,
    String path, {
    Map<String, dynamic>? query,
  }) async => {
    'message': 'Welcome',
    'server_now': '2026-11-16T12:00:00Z',
    'statistics': {'classes': 1},
    'deadlines': [],
    'activity': [],
    'performance': [],
    'progress': [],
    'question_performance': [],
    'question_analytics_scope': 'Latest released manual reviews',
    'total_assignments': 0,
    'total_performance_assignments': 0,
    'total_progress_students': 0,
  };
}

Widget _withAuth(Widget child) => ChangeNotifierProvider<AuthProvider>.value(
  value: _TestAuthProvider(),
  child: MaterialApp(home: child),
);

void main() {
  testWidgets('only teachers can open the isolated evaluation fixture', (
    tester,
  ) async {
    await tester.pumpWidget(
      _withAuth(
        AcademicDashboard(role: 'teacher', repository: _DashboardRepository()),
      ),
    );
    await tester.pumpAndSettle();

    final launch = find.text('Open isolated AI evaluation demo');
    expect(launch, findsOneWidget);
    await tester.tap(launch);
    await tester.pumpAndSettle();
    expect(find.text(demoAIFixtureDisclosure), findsOneWidget);
    expect(find.text('The Water Cycle — Demo Assignment'), findsOneWidget);

    await tester.pumpWidget(
      _withAuth(
        AcademicDashboard(role: 'student', repository: _DashboardRepository()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Open isolated AI evaluation demo'), findsNothing);
  });

  testWidgets(
    'fixture preview loads local pages and edit, approve, and publish stay local',
    (tester) async {
      final repository = DemoAIEvaluationRepository();
      await tester.pumpWidget(
        _withAuth(
          TeacherAIEvaluationScreen(
            assignmentId: demoAIWaterCycleAssignmentId,
            assignmentTitle: demoAIWaterCycleAssignmentTitle,
            submissionId: demoAIWaterCycleSubmissionId,
            totalMarks: 20,
            submission: createDemoWaterCycleSubmission(),
            repository: repository,
            isDemoFixture: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text(demoAIFixtureDisclosure), findsOneWidget);
      final preview = find.text('View original handwritten sample');
      await tester.scrollUntilVisible(
        preview,
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(preview);
      await tester.pumpAndSettle();
      expect(find.text(demoAIFixtureDisclosure), findsOneWidget);
      expect(find.byType(Image), findsNWidgets(2));
      expect(
        find.text(
          'Synthetic handwritten-page previews bundled with the app. These are not student uploads and were not processed by OCR.',
        ),
        findsOneWidget,
      );
      Navigator.of(tester.element(find.byType(Scaffold).last)).pop();
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Illustrative fixture marks: 16.0 / 20.0'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Illustrative fixture marks: 16.0 / 20.0'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Provisional fixture percentage: 80.0%'),
        findsOneWidget,
      );
      expect(find.text('Publish approved grade'), findsNothing);
      expect(find.text('Run a new evaluation'), findsNothing);

      final markFields = find.byWidgetPredicate(
        (widget) =>
            widget is TextField &&
            widget.decoration?.labelText == 'Teacher-approved marks',
      );
      await tester.enterText(markFields.at(0), '8');
      await tester.enterText(markFields.at(1), '9');
      await tester.enterText(
        find.widgetWithText(TextField, 'Teacher feedback for student'),
        'Teacher checked the sample answers.',
      );
      await tester.enterText(
        find
            .widgetWithText(
              TextField,
              'Teacher feedback for this answer (optional)',
            )
            .first,
        'Explain the water-state change.',
      );

      final save = find.text('Save review changes privately');
      await tester.scrollUntilVisible(
        save,
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(save);
      await tester.pumpAndSettle();
      expect(repository.isPublished, isFalse);
      expect(find.text('Approve evaluation'), findsOneWidget);

      final approve = find.text('Approve evaluation');
      await tester.scrollUntilVisible(
        approve,
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.tap(approve);
      await tester.pumpAndSettle();
      expect(find.text('Review approved'), findsOneWidget);
      expect(
        find.textContaining('Teacher-approved total: 17.0 / 20.0'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Approved in-memory fixture only'),
        findsOneWidget,
      );
      expect(repository.isPublished, isFalse);

      final publish = find.text('Publish fixture grade locally');
      await tester.ensureVisible(publish);
      await tester.pumpAndSettle();
      await tester.tap(publish);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Publish fixture grade'));
      await tester.pumpAndSettle();

      expect(repository.isPublished, isTrue);
      expect(
        find.textContaining(
          'Published locally in this fixture only; no real student record was changed.',
        ),
        findsOneWidget,
      );
      final published = await repository.isGradePublished(
        '',
        demoAIWaterCycleSubmissionId,
        approvedMarks: 17,
        teacherFeedback: 'Teacher checked the sample answers.',
      );
      expect(published, isTrue);
    },
  );
}
