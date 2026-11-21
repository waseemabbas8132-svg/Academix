import 'dart:convert';

import 'package:academix/core/network/api_client.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/features/classes/data/repositories/class_stream_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'announcement list uses the authenticated class stream endpoint',
    () async {
      final client = MockClient((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/api/v1/classes/class-1/announcements');
        expect(request.headers['Authorization'], 'Bearer test-token');
        return http.Response(
          jsonEncode([
            {
              'id': 'announcement-1',
              'class_id': 'class-1',
              'teacher_id': 'teacher@academix.app',
              'title': 'Welcome',
              'content': 'Welcome to the class.',
              'is_pinned': true,
              'created_at': '2026-11-14T09:00:00Z',
              'updated_at': '2026-11-14T09:00:00Z',
            },
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final repository = HttpClassStreamRepository(
        apiClient: ApiClient(client: client),
      );

      final announcements = await repository.listAnnouncements(
        token: 'test-token',
        classId: 'class-1',
      );

      expect(announcements, hasLength(1));
      expect(announcements.single.title, 'Welcome');
      expect(announcements.single.isPinned, isTrue);
    },
  );

  test('announcement repository preserves forbidden API errors', () async {
    final client = MockClient(
      (_) async => http.Response('{"detail":"Forbidden"}', 403),
    );
    final repository = HttpClassStreamRepository(
      apiClient: ApiClient(client: client),
    );

    await expectLater(
      repository.listAnnouncements(token: 'test-token', classId: 'class-1'),
      throwsA(isA<ForbiddenException>()),
    );
  });

  test(
    'announcement validation failures map to a validation exception',
    () async {
      final client = MockClient(
        (_) async => http.Response('{"detail":"Title cannot be blank"}', 422),
      );
      final repository = HttpClassStreamRepository(
        apiClient: ApiClient(client: client),
      );

      await expectLater(
        repository.listAnnouncements(token: 'test-token', classId: 'class-1'),
        throwsA(isA<ValidationException>()),
      );
    },
  );
}
