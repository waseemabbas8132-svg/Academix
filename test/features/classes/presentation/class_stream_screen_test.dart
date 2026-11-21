import 'package:academix/features/authentication/domain/entities/user.dart';
import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:academix/features/classes/data/models/announcement.dart';
import 'package:academix/features/classes/data/models/classroom_summary.dart';
import 'package:academix/features/classes/data/repositories/class_stream_repository.dart';
import 'package:academix/features/classes/presentation/screens/class_stream_screen.dart';
import 'package:academix/features/classes/presentation/screens/classes_screen.dart';
import 'package:academix/shared/enums/user_role.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAuthProvider extends AuthProvider {
  _TestAuthProvider([this.role = UserRole.teacher]);

  final UserRole role;

  @override
  String? get token => 'test-token';

  @override
  User? get currentUser => User(
    id: 'teacher-1',
    name: 'Teacher',
    email: 'teacher@academix.app',
    role: role,
  );
}

class _FakeClassStreamRepository implements ClassStreamRepository {
  final announcement = Announcement(
    id: 'announcement-1',
    classId: 'class-1',
    teacherId: 'teacher@academix.app',
    title: 'Bring your lab notebook',
    content: 'We will start the experiment promptly.',
    isPinned: true,
    createdAt: DateTime(2026, 11, 14, 9),
    updatedAt: DateTime(2026, 11, 14, 9),
  );

  @override
  Future<List<ClassroomSummary>> listClasses({required String token}) async =>
      [];

  @override
  Future<List<Announcement>> listAnnouncements({
    required String token,
    required String classId,
  }) async => [announcement];

  @override
  Future<Announcement> createAnnouncement({
    required String token,
    required String classId,
    required String title,
    required String content,
  }) async => announcement;

  @override
  Future<Announcement> updateAnnouncement({
    required String token,
    required String announcementId,
    required String title,
    required String content,
  }) async => announcement;

  @override
  Future<void> deleteAnnouncement({
    required String token,
    required String announcementId,
  }) async {}

  @override
  Future<Announcement> setPinned({
    required String token,
    required String announcementId,
    required bool isPinned,
  }) async => announcement;
}

void main() {
  const classroom = ClassroomSummary(
    id: 'class-1',
    name: 'Biology 101',
    section: 'A',
    subject: 'Biology',
    teacherId: 'teacher@academix.app',
    classCode: 'BIO123',
  );

  for (final role in [UserRole.teacher, UserRole.student]) {
    testWidgets('${role.name} sees only the matching class action', (
      tester,
    ) async {
      final teacher = role == UserRole.teacher;
      final action = teacher ? 'Create class' : 'Join class';
      await tester.pumpWidget(
        ChangeNotifierProvider<AuthProvider>(
          create: (_) => _TestAuthProvider(role),
          child: MaterialApp(
            home: ClassesScreen(repository: _FakeClassStreamRepository()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text(teacher ? 'Join class' : 'Create class'), findsNothing);
      await tester.tap(find.text(action));
      await tester.pumpAndSettle();
      expect(find.text(teacher ? 'Class name' : 'Class code'), findsOneWidget);
      await tester.tap(find.text(teacher ? 'Create' : 'Join'));
      await tester.pumpAndSettle();
      expect(
        find.text(teacher ? 'Enter class name.' : 'Enter class code.'),
        findsOneWidget,
      );
    });
  }

  Future<void> pumpStream(
    WidgetTester tester, {
    required bool isTeacher,
  }) async {
    await tester.pumpWidget(
      ChangeNotifierProvider<AuthProvider>.value(
        value: _TestAuthProvider(),
        child: MaterialApp(
          home: ClassStreamScreen(
            classroom: classroom,
            isTeacher: isTeacher,
            repository: _FakeClassStreamRepository(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('only the teacher can see class code and roster controls', (
    tester,
  ) async {
    for (final teacher in [false, true]) {
      await tester.pumpWidget(const SizedBox.shrink());
      await pumpStream(tester, isTeacher: teacher);
      await tester.tap(find.text('About'));
      await tester.pumpAndSettle();
      expect(find.text('BIO123'), teacher ? findsOneWidget : findsNothing);
      expect(
        find.text('Enrolled students'),
        teacher ? findsOneWidget : findsNothing,
      );
    }
  });

  testWidgets(
    'student sees announcements and pinned status without management actions',
    (tester) async {
      await pumpStream(tester, isTeacher: false);

      expect(find.text('Stream'), findsOneWidget);
      expect(find.text('Bring your lab notebook'), findsOneWidget);
      expect(find.text('Pinned'), findsOneWidget);
      expect(find.byTooltip('Announcement actions'), findsNothing);
      expect(find.text('Announcement'), findsNothing);
    },
  );

  testWidgets('teacher sees announcement management and create actions', (
    tester,
  ) async {
    await pumpStream(tester, isTeacher: true);

    expect(find.byTooltip('Announcement actions'), findsOneWidget);
    expect(find.text('Announcement'), findsOneWidget);
  });
}
