import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:academix/features/assignments/data/repositories/assignment_repository.dart';
import 'package:academix/features/assignments/data/repositories/ai_evaluation_repository.dart';
import 'package:academix/features/assignments/data/repositories/review_repository.dart';
import 'package:academix/features/assignments/data/services/assignment_file_picker.dart';
import 'package:academix/features/assignments/presentation/screens/manual_review_screen.dart';
import 'package:academix/features/assignments/presentation/screens/attachment_viewer_screen.dart';
import 'package:academix/shared/widgets/academic_dashboard.dart';

class _Auth extends AuthProvider {
  @override
  String? get token => 'private-token';
}

class _Assignments implements AssignmentRepository {
  int downloads = 0;
  @override
  Future<Uint8List> downloadFile(String token, AssignmentFile file) async {
    downloads++;
    return _png;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _Picker implements AssignmentFilePicker {
  int saves = 0;
  @override
  Future<void> saveFile(AssignmentFile file, Uint8List bytes) async {
    saves++;
  }

  @override
  Future<List<AssignmentUpload>> pickFiles() async => [];
}

class _AI implements AIEvaluationRepository {
  EvaluationJob? job;
  int calls = 0;
  @override
  Future<EvaluationJob?> getLatest(String token, String submissionId) async {
    calls++;
    return job;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw StateError('Only existing suggestion reads are permitted.');
}

final _png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==',
);
const _file = AssignmentFile(
  id: 'file',
  filename: 'original.pdf',
  contentType: 'application/pdf',
  sizeBytes: 200,
  downloadUrl: '/api/v1/files/file',
);
Submission _submission() => Submission(
  id: 's',
  assignmentId: 'a',
  studentId: 'student@school.test',
  submissionText: 'Original work',
  status: 'submitted',
  isLate: false,
  submittedAt: DateTime.utc(2026),
  updatedAt: DateTime.utc(2026),
  marksObtained: null,
  teacherFeedback: null,
  gradedAt: null,
  attachments: const [],
  revisions: const [],
  assignmentTitle: 'Science',
  totalMarks: 10,
  dueDate: DateTime.utc(2026, 12),
);

class _Reviews extends ReviewRepository {
  Map<String, dynamic>? latest;
  Map<String, dynamic>? saved;
  Map<String, dynamic>? actionBody;
  String? performed;
  bool fail = false;
  String kind = 'pdf';
  List<int> pages = [];
  Map<String, dynamic> dashboard = {
    'message': 'Welcome, Teacher',
    'server_now': '2026-11-17T12:00:00Z',
    'statistics': {'classes': 2, 'pending_manual_reviews': 3},
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
  @override
  Future<Map<String, dynamic>> get(
    String token,
    String path, {
    Map<String, dynamic>? query,
  }) async {
    expect(token, 'private-token');
    if (fail) {
      throw const ConflictException(
        message: 'A newer review exists. Reload before saving.',
      );
    }
    if (path.endsWith('/dashboard')) return dashboard;
    if (path.endsWith('/preview')) {
      return {'kind': kind, 'page_count': kind == 'download_only' ? 0 : 2};
    }
    if (path.endsWith('/history')) {
      return {
        'items': latest == null ? [] : [latest],
        'total': latest == null ? 0 : 1,
      };
    }
    return jsonDecode(
      jsonEncode({
        'source_updated_at': '2026-01-01T00:00:00Z',
        'rubric_signature': 'a' * 64,
        'source_revision': 1,
        'source_text': 'Original work',
        'source_files': [],
        'official_marks': performed == 'release' ? '6' : null,
        'official_status': performed == 'release' ? 'graded' : 'submitted',
        'total_marks': '10',
        'stale': false,
        'latest': latest,
        'questions': [
          {
            'question_id': 'q1',
            'prompt': 'Explain your answer',
            'max_marks': '10',
            'criteria': [],
          },
        ],
      }),
    ) as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> save(
    String token,
    String id,
    Map<String, dynamic> body,
  ) async {
    if (fail) {
      throw const ConflictException(
        message: 'A newer review exists. Reload before saving.',
      );
    }
    saved = body;
    latest = {
      ...body,
      'version': (latest?['version'] as int? ?? 0) + 1,
      'created_at': '2026-11-17T12:00:00Z',
      'actor': 'teacher@school.test',
      'total': body['questions'][0]['marks'],
    };
    return latest!;
  }

  @override
  Future<Map<String, dynamic>> action(
    String token,
    String id,
    String action,
    Map<String, dynamic> body,
  ) async {
    performed = action;
    actionBody = body;
    latest = {
      ...?latest,
      'version': (latest?['version'] as int? ?? 0) + 1,
      'state': action == 'release' ? 'released' : 'returned',
      'reason': body['reason'],
      'created_at': '2026-11-17T12:00:00Z',
      'actor': 'teacher@school.test',
    };
    return latest!;
  }

  @override
  Future<Uint8List> page(String token, String fileId, int page) async {
    pages.add(page);
    return _png;
  }

  @override
  Future<Map<String, dynamic>?> released(String token, String id) async =>
      latest?['state'] == 'released'
      ? {
          'questions': latest!['questions'],
          'released_at': '2026-11-17',
          'total': '6',
        }
      : null;
}

void main() {
  Future<void> pump(
    WidgetTester tester,
    Widget child, {
    Size size = const Size(1000, 1600),
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _Auth(),
        child: MaterialApp(home: child),
      ),
    );
    await tester.pumpAndSettle();
  }

  ManualReviewScreen manual(_Reviews reviews, {_AI? ai}) => ManualReviewScreen(
    submission: _submission(),
    assignments: _Assignments(),
    reviews: reviews,
    ai: ai ?? _AI(),
  );
  Future<void> tap(WidgetTester tester, String text) async {
    if (find.text(text).evaluate().isEmpty) {
      final pageScroll = find.descendant(
        of: find.byType(ListView).first,
        matching: find.byType(Scrollable),
      ).first;
      await tester.scrollUntilVisible(
        find.text(text),
        250,
        scrollable: pageScroll,
      );
    }
    final finder = find.text(text).last;
    await tester.ensureVisible(finder);
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  Future<void> fill(WidgetTester tester) async {
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Teacher mark q1'),
      '6',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Overall teacher feedback'),
      'Good evidence',
    );
  }

  testWidgets(
    'private draft restores marks and feedback after leaving the screen',
    (tester) async {
      final reviews = _Reviews();
      await pump(tester, manual(reviews));
      await fill(tester);
      await tap(tester, 'Save private draft');
      expect(reviews.saved!['state'], 'draft');
      expect(reviews.performed, isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await pump(tester, manual(reviews));
      expect(find.text('6'), findsWidgets);
      expect(find.text('Good evidence'), findsOneWidget);
      final release = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Release official grade'),
      );
      expect(release.onPressed, isNull);
    },
  );
  testWidgets(
    'reviewed marks require explicit release confirmation and do not auto-release',
    (tester) async {
      final reviews = _Reviews();
      await pump(tester, manual(reviews));
      await fill(tester);
      await tap(tester, 'Mark reviewed');
      expect(reviews.performed, isNull);
      await tap(tester, 'Release official grade');
      expect(find.text('Release official grade?'), findsOneWidget);
      expect(reviews.performed, isNull);
      await tap(tester, 'Release grade');
      expect(reviews.performed, 'release');
      expect(reviews.actionBody!['expected_version'], 1);
    },
  );
  testWidgets(
    'invalid marks and incomplete review cannot be saved as reviewed',
    (tester) async {
      final reviews = _Reviews();
      await pump(tester, manual(reviews));
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Teacher mark q1'),
        '11',
      );
      await tap(tester, 'Mark reviewed');
      expect(reviews.saved, isNull);
      expect(
        find.textContaining('with at most 2 decimal places'),
        findsOneWidget,
      );
      await tester.enterText(
        find.widgetWithText(TextFormField, 'Teacher mark q1'),
        '6',
      );
      await tap(tester, 'Mark reviewed');
      expect(reviews.saved, isNull);
      expect(
        find.textContaining('Complete every question mark'),
        findsOneWidget,
      );
    },
  );
  testWidgets('return requires teacher reason and saves a revision request', (
    tester,
  ) async {
    final reviews = _Reviews();
    await pump(tester, manual(reviews));
    await tap(tester, 'Return for revision');
    await tester.enterText(
      find.widgetWithText(TextField, 'Required revision reason'),
      'Please show the calculation',
    );
    await tap(tester, 'Return work');
    expect(reviews.performed, 'return');
    expect(reviews.actionBody!['reason'], 'Please show the calculation');
    await tester.pump(const Duration(seconds: 2));
  });
  testWidgets('save conflict stays visible and retains unsaved teacher marks', (
    tester,
  ) async {
    final reviews = _Reviews();
    await pump(tester, manual(reviews));
    await fill(tester);
    reviews.fail = true;
    await tap(tester, 'Save private draft');
    expect(find.textContaining('A newer review exists'), findsOneWidget);
    expect(find.text('6'), findsWidgets);
  });
  testWidgets(
    'existing AI suggestions are read only and never prefill manual marks',
    (tester) async {
      final ai = _AI()
        ..job = const EvaluationJob(
          id: 'job',
          submissionId: 's',
          status: 'completed',
          attemptCount: 1,
          extractedAnswers: [],
          evaluation: AIEvaluation(
            id: 'eval',
            suggestedTotal: 9,
            maximumMarks: 10,
            confidence: 0.8,
            explanation: 'Suggestion',
            feedback: 'AI feedback',
            modelName: 'cached',
            modelVersion: 'v1',
            reviewStatus: 'pending',
            questions: [],
            feedbackItems: [],
          ),
        );
      final reviews = _Reviews();
      await pump(tester, manual(reviews, ai: ai));
      expect(find.textContaining('Existing AI suggestions'), findsOneWidget);
      expect(ai.calls, 1);
      final field = tester.widget<TextFormField>(
        find.widgetWithText(TextFormField, 'Teacher mark q1'),
      );
      expect(field.controller!.text, isEmpty);
      expect(reviews.saved, isNull);
    },
  );
  testWidgets('manual review fits a narrow screen without overflow', (
    tester,
  ) async {
    await pump(tester, manual(_Reviews()), size: const Size(320, 700));
    await tap(tester, 'Save private draft');
    expect(tester.takeException(), isNull);
  });
  testWidgets(
    'PDF preview pages, fit and original download use authenticated repositories',
    (tester) async {
      final previews = _Reviews(),
          assignments = _Assignments(),
          picker = _Picker();
      await pump(
        tester,
        AttachmentViewerScreen(
          file: _file,
          repository: assignments,
          previews: previews,
          filePicker: picker,
        ),
      );
      expect(find.text('Page 1 of 2'), findsOneWidget);
      expect(previews.pages, [1]);
      await tester.tap(find.byTooltip('Next page'));
      await tester.pumpAndSettle();
      expect(previews.pages, [1, 2]);
      expect(find.text('Page 2 of 2'), findsOneWidget);
      await tester.tap(find.byTooltip('Fit to screen'));
      await tester.tap(find.byTooltip('Download original'));
      await tester.pumpAndSettle();
      expect(assignments.downloads, 1);
      expect(picker.saves, 1);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'unsupported document offers original download; preview errors offer retry',
    (tester) async {
      final previews = _Reviews()..kind = 'download_only';
      await pump(
        tester,
        AttachmentViewerScreen(
          file: _file,
          repository: _Assignments(),
          previews: previews,
        ),
      );
      expect(
        find.textContaining('In-app preview is unavailable'),
        findsOneWidget,
      );
      expect(previews.pages, isEmpty);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      await pump(
        tester,
        AttachmentViewerScreen(
          file: _file,
          repository: _Assignments(),
          previews: _Reviews()..fail = true,
        ),
      );
      expect(find.text('Retry preview'), findsOneWidget);
    },
  );
  testWidgets(
    'dashboard displays real counts with empty performance at narrow width',
    (tester) async {
      await pump(
        tester,
        AcademicDashboard(role: 'teacher', repository: _Reviews()),
        size: const Size(360, 800),
      );
      expect(find.text('2'), findsOneWidget);
      expect(find.text('pending manual reviews'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text(
          'No current released manual question reviews yet. Existing total-only grades cannot provide question analytics.',
        ),
        300,
      );
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('dashboard API failures have a retry state', (tester) async {
    await pump(
      tester,
      AcademicDashboard(role: 'student', repository: _Reviews()..fail = true),
    );
    expect(find.textContaining('Dashboard unavailable'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);
  });
  testWidgets('students display only released question feedback', (
    tester,
  ) async {
    final reviews = _Reviews()
      ..latest = {
        'state': 'draft',
        'questions': [
          {
            'question_id': 'q1',
            'marks': '6',
            'max_marks': '10',
            'feedback': 'Private',
          },
        ],
      };
    await pump(
      tester,
      Scaffold(
        body: ReleasedQuestionMarks(submissionId: 's', repository: reviews),
      ),
    );
    expect(find.text('Private'), findsNothing);
    expect(find.text('Released question marks'), findsNothing);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
    reviews.latest!['state'] = 'released';
    await pump(
      tester,
      Scaffold(
        body: ReleasedQuestionMarks(submissionId: 's', repository: reviews),
      ),
    );
    await tap(tester, 'Released question marks');
    expect(find.text('Private'), findsOneWidget);
  });
}
