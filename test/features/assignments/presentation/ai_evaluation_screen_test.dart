import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:academix/features/assignments/data/repositories/ai_evaluation_repository.dart';
import 'package:academix/features/assignments/presentation/screens/ai_evaluation_screens.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAuthProvider extends AuthProvider {
  @override
  String? get token => 'test-token';
}

class _FakeEvaluationRepository implements AIEvaluationRepository {
  EvaluationJob? job;
  EvaluationJob? nextJob;
  bool published = false;
  double? approvedMarks;
  Map<String, double>? approvedQuestionMarks;
  String? approvedFeedback;
  String? savedFeedback;
  Map<String, double?>? savedQuestionMarks;
  Map<String, String>? savedQuestionFeedback;

  @override
  Future<AssignmentRubric> getRubric(String token, String assignmentId) async =>
      const AssignmentRubric(
        id: 'rubric-1',
        assignmentId: 'assignment-1',
        questions: [
          RubricQuestion(
            questionId: 'q1',
            prompt: 'Explain the result.',
            maxMarks: 10,
          ),
        ],
      );

  @override
  Future<EvaluationJob?> getLatest(String token, String submissionId) async =>
      job;

  @override
  Future<EvaluationJob> request(
    String token,
    String submissionId, {
    bool force = false,
  }) async => job =
      nextJob ??
      const EvaluationJob(
        id: 'job-1',
        submissionId: 'submission-1',
        status: 'pending',
        attemptCount: 0,
        extractedAnswers: [],
      );

  @override
  Future<AIEvaluation> approve(
    String token,
    String evaluationId, {
    required double marks,
    required String feedback,
    required Map<String, double> questionMarks,
    required Map<String, String> questionFeedback,
  }) async {
    approvedMarks = marks;
    approvedFeedback = feedback;
    approvedQuestionMarks = questionMarks;
    final evaluation = job!.evaluation!;
    final approved = AIEvaluation(
      id: evaluation.id,
      suggestedTotal: evaluation.suggestedTotal,
      maximumMarks: evaluation.maximumMarks,
      confidence: evaluation.confidence,
      explanation: evaluation.explanation,
      feedback: evaluation.feedback,
      modelName: evaluation.modelName,
      modelVersion: evaluation.modelVersion,
      reviewStatus: 'approved',
      approvedMarks: marks,
      teacherFeedback: feedback,
      questions: evaluation.questions
          .map(
            (q) => QuestionEvaluation(
              questionId: q.questionId,
              maximumMarks: q.maximumMarks,
              confidence: q.confidence,
              explanation: q.explanation,
              feedback: q.feedback,
              evidence: q.evidence,
              needsReview: q.needsReview,
              suggestedMarks: q.suggestedMarks,
              teacherMarks: questionMarks[q.questionId],
            ),
          )
          .toList(),
      feedbackItems: evaluation.feedbackItems,
    );
    job = EvaluationJob(
      id: job!.id,
      submissionId: job!.submissionId,
      status: job!.status,
      attemptCount: job!.attemptCount,
      extractedAnswers: job!.extractedAnswers,
      evaluation: approved,
    );
    return approved;
  }

  @override
  Future<AIEvaluation> saveReview(
    String token,
    String evaluationId, {
    required String feedback,
    required Map<String, double?> questionMarks,
    required Map<String, String> questionFeedback,
  }) async {
    savedFeedback = feedback;
    savedQuestionMarks = questionMarks;
    savedQuestionFeedback = questionFeedback;
    return job!.evaluation!;
  }

  @override
  Future<void> publish(String token, String evaluationId) async {
    published = true;
  }

  @override
  Future<bool> isGradePublished(
    String token,
    String submissionId, {
    required double approvedMarks,
    required String teacherFeedback,
  }) async => published;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  EvaluationJob completed(String id, {double? suggestion = 7}) => EvaluationJob(
    id: 'job-$id',
    submissionId: 'submission-1',
    status: 'completed',
    attemptCount: 1,
    extractedAnswers: const [],
    evaluation: AIEvaluation(
      id: id,
      maximumMarks: 10,
      confidence: .8,
      explanation: 'Reason.',
      feedback: 'Feedback.',
      modelName: 'fake',
      modelVersion: 'test',
      reviewStatus: 'pending',
      feedbackItems: const [],
      suggestedTotal: suggestion,
      questions: [
        QuestionEvaluation(
          questionId: 'q1',
          maximumMarks: 10,
          confidence: .8,
          explanation: 'Reason.',
          feedback: 'Feedback.',
          evidence: const [],
          needsReview: suggestion == null,
          suggestedMarks: suggestion,
        ),
      ],
    ),
  );

  Widget screen(_FakeEvaluationRepository repository) =>
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: TeacherAIEvaluationScreen(
            assignmentId: 'assignment-1',
            assignmentTitle: 'Assignment',
            submissionId: 'submission-1',
            totalMarks: 10,
            repository: repository,
          ),
        ),
      );

  testWidgets(
    'new evaluation identity resets marks and feedback even with identical question IDs',
    (tester) async {
      final repository = _FakeEvaluationRepository()..job = completed('first');
      await tester.pumpWidget(screen(repository));
      await tester.pumpAndSettle();
      final marks = find.widgetWithText(TextField, 'Teacher-approved marks');
      final feedback = find.widgetWithText(
        TextField,
        'Teacher feedback for student',
      );
      await tester.enterText(marks, '5');
      await tester.enterText(feedback, 'Old unsaved review');
      repository.nextJob = completed('second', suggestion: 3);
      final rerun = find.text('Run a new evaluation');
      tester.testTextInput.hide();
      await tester.pumpAndSettle();
      await tester.ensureVisible(rerun);
      await tester.pumpAndSettle();
      await tester.tap(rerun);
      await tester.pumpAndSettle();
      expect(tester.widget<TextField>(marks).controller!.text, '3.0');
      expect(tester.widget<TextField>(feedback).controller!.text, isEmpty);
    },
  );

  testWidgets(
    'teacher explicitly marks an unscored answer and reads back the approved override',
    (tester) async {
      final repository = _FakeEvaluationRepository()
        ..job = completed('unscored', suggestion: null);
      await tester.pumpWidget(screen(repository));
      await tester.pumpAndSettle();
      final marks = find.widgetWithText(TextField, 'Teacher-approved marks');
      expect(tester.widget<TextField>(marks).controller!.text, isEmpty);
      await tester.enterText(marks, '6');
      await tester.enterText(
        find.widgetWithText(TextField, 'Teacher feedback for student'),
        'Checked original image.',
      );
      final approve = find.text('Approve evaluation');
      tester.testTextInput.hide();
      await tester.pumpAndSettle();
      await tester.ensureVisible(approve);
      await tester.pumpAndSettle();
      await tester.tap(approve);
      await tester.pumpAndSettle();
      expect(repository.approvedMarks, 6);
      expect(
        find.textContaining('Teacher-approved total: 6.0'),
        findsOneWidget,
      );
      expect(find.textContaining('Teacher-approved 6.0'), findsOneWidget);
      expect(
        find.text('Teacher feedback: Checked original image.'),
        findsOneWidget,
      );
      expect(find.textContaining('(uncalibrated)'), findsWidgets);
      expect(find.text('Publish approved grade'), findsOneWidget);
    },
  );

  testWidgets('teacher can save review edits without approving or publishing', (
    tester,
  ) async {
    final repository = _FakeEvaluationRepository()..job = completed('draft');
    await tester.pumpWidget(screen(repository));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Teacher-approved marks'),
      '6.5',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Teacher feedback for student'),
      'Review the second step.',
    );
    await tester.enterText(
      find.widgetWithText(
        TextField,
        'Teacher feedback for this answer (optional)',
      ),
      'Show the intermediate calculation.',
    );
    final save = find.text('Save review changes privately');
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.pumpAndSettle();

    expect(repository.savedFeedback, 'Review the second step.');
    expect(repository.savedQuestionMarks, {'q1': 6.5});
    expect(repository.savedQuestionFeedback, {
      'q1': 'Show the intermediate calculation.',
    });
    expect(repository.approvedMarks, isNull);
    expect(repository.published, isFalse);
    expect(find.text('Approve evaluation'), findsOneWidget);
    expect(find.text('Publish approved grade'), findsNothing);
  });

  testWidgets('nonfinite teacher marks cannot reach the approval repository', (
    tester,
  ) async {
    final repository = _FakeEvaluationRepository()..job = completed('finite');
    await tester.pumpWidget(screen(repository));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextField, 'Teacher-approved marks'),
      'NaN',
    );
    await tester.enterText(
      find.widgetWithText(TextField, 'Teacher feedback for student'),
      'Review',
    );
    final approve = find.text('Approve evaluation');
    tester.testTextInput.hide();
    await tester.pumpAndSettle();
    await tester.ensureVisible(approve);
    await tester.pumpAndSettle();
    await tester.tap(approve);
    await tester.pumpAndSettle();
    expect(repository.approvedMarks, isNull);
    expect(find.textContaining('Enter a finite mark'), findsOneWidget);
  });

  testWidgets('teacher can request evaluation and sees processing status', (
    tester,
  ) async {
    final repository = _FakeEvaluationRepository();
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: TeacherAIEvaluationScreen(
            assignmentId: 'assignment-1',
            assignmentTitle: 'Lab report',
            submissionId: 'submission-1',
            totalMarks: 10,
            repository: repository,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No evaluation yet'), findsOneWidget);
    await tester.tap(find.text('Request evaluation'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Status: pending'), findsOneWidget);
    expect(find.textContaining('must review and approve'), findsOneWidget);
    expect(repository.job?.id, 'job-1');
  });

  testWidgets('teacher must approve before separately publishing a grade', (
    tester,
  ) async {
    final repository = _FakeEvaluationRepository()
      ..job = const EvaluationJob(
        id: 'job-2',
        submissionId: 'submission-1',
        status: 'completed',
        attemptCount: 1,
        extractedAnswers: [],
        evaluation: AIEvaluation(
          id: 'evaluation-1',
          suggestedTotal: 7,
          maximumMarks: 10,
          confidence: 0.8,
          explanation: 'A tentative suggestion.',
          feedback: 'Check the explanation.',
          modelName: 'local-model',
          modelVersion: 'test',
          reviewStatus: 'pending',
          feedbackItems: [],
          questions: [
            QuestionEvaluation(
              questionId: 'q1',
              suggestedMarks: 7,
              maximumMarks: 10,
              confidence: 0.8,
              explanation: 'Evidence was found.',
              feedback: 'Add detail.',
              evidence: ['supported quote'],
              needsReview: false,
            ),
          ],
        ),
      );
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: TeacherAIEvaluationScreen(
            assignmentId: 'assignment-1',
            assignmentTitle: 'Lab report',
            submissionId: 'submission-1',
            totalMarks: 10,
            repository: repository,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Approve evaluation'), findsOneWidget);

    await tester.enterText(
      find.widgetWithText(TextField, 'Teacher feedback for student'),
      'Reviewed by teacher.',
    );
    final approveButton = find.text('Approve evaluation');
    await tester.ensureVisible(approveButton);
    await tester.pumpAndSettle();
    await tester.tap(approveButton);
    await tester.pumpAndSettle();

    expect(repository.approvedMarks, 7);
    expect(repository.approvedQuestionMarks, {'q1': 7});
    expect(repository.approvedFeedback, 'Reviewed by teacher.');
    expect(find.text('Review approved'), findsOneWidget);
    expect(find.text('Publish approved grade'), findsOneWidget);

    final publishButton = find.text('Publish approved grade');
    await tester.ensureVisible(publishButton);
    await tester.pumpAndSettle();
    await tester.tap(publishButton);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Publish grade'));
    await tester.pumpAndSettle();
    expect(repository.published, isTrue);
    expect(find.text('Official grade: published to student'), findsOneWidget);
  });
}
