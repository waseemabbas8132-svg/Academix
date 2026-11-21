import 'dart:convert';

import 'package:academix/core/network/api_client.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/features/classes/data/models/announcement.dart';
import 'package:academix/features/classes/data/models/classroom_summary.dart';

abstract interface class ClassStreamRepository {
  Future<List<ClassroomSummary>> listClasses({required String token});

  Future<List<Announcement>> listAnnouncements({
    required String token,
    required String classId,
  });

  Future<Announcement> createAnnouncement({
    required String token,
    required String classId,
    required String title,
    required String content,
  });

  Future<Announcement> updateAnnouncement({
    required String token,
    required String announcementId,
    required String title,
    required String content,
  });

  Future<void> deleteAnnouncement({
    required String token,
    required String announcementId,
  });

  Future<Announcement> setPinned({
    required String token,
    required String announcementId,
    required bool isPinned,
  });
}

class HttpClassStreamRepository implements ClassStreamRepository {
  HttpClassStreamRepository({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Map<String, String> _headers(String token) => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Future<void> createClass(String token, Map<String, String> fields) async {
    await _apiClient.post(
      '/api/v1/classes',
      headers: _headers(token),
      body: fields,
    );
  }

  Future<void> joinClass(String token, String code) async {
    try {
      await _apiClient.post(
        '/api/v1/classes/join',
        headers: _headers(token),
        body: {'class_code': code},
      );
    } on NotFoundException {
      throw const NotFoundException(message: 'Class code is invalid.');
    }
  }

  Future<List<({String name, String email})>> listStudents(
    String token,
    String classId,
  ) async {
    final response = await _apiClient.get(
      '/api/v1/classes/$classId/students',
      headers: _headers(token),
    );
    return (jsonDecode(response.body) as List<dynamic>)
        .map(
          (row) =>
              (name: row['name'] as String, email: row['student_id'] as String),
        )
        .toList();
  }

  @override
  Future<List<ClassroomSummary>> listClasses({required String token}) async {
    final response = await _apiClient.get(
      '/api/v1/classes',
      headers: _headers(token),
    );
    final items = jsonDecode(response.body) as List<dynamic>;
    return items
        .map((item) => ClassroomSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Announcement>> listAnnouncements({
    required String token,
    required String classId,
  }) async {
    final response = await _apiClient.get(
      '/api/v1/classes/$classId/announcements',
      headers: _headers(token),
    );
    final items = jsonDecode(response.body) as List<dynamic>;
    return items
        .map((item) => Announcement.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Announcement> createAnnouncement({
    required String token,
    required String classId,
    required String title,
    required String content,
  }) async {
    final response = await _apiClient.post(
      '/api/v1/classes/$classId/announcements',
      headers: _headers(token),
      body: {'title': title, 'content': content},
    );
    return Announcement.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  @override
  Future<Announcement> updateAnnouncement({
    required String token,
    required String announcementId,
    required String title,
    required String content,
  }) async {
    final response = await _apiClient.put(
      '/api/v1/announcements/$announcementId',
      headers: _headers(token),
      body: {'title': title, 'content': content},
    );
    return Announcement.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  @override
  Future<void> deleteAnnouncement({
    required String token,
    required String announcementId,
  }) async {
    await _apiClient.delete(
      '/api/v1/announcements/$announcementId',
      headers: _headers(token),
    );
  }

  @override
  Future<Announcement> setPinned({
    required String token,
    required String announcementId,
    required bool isPinned,
  }) async {
    final response = await _apiClient.patch(
      '/api/v1/announcements/$announcementId/pin',
      headers: _headers(token),
      body: {'is_pinned': isPinned},
    );
    return Announcement.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}
