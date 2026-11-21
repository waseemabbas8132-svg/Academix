import 'dart:convert';
import 'dart:typed_data';

import 'package:academix/core/network/api_client.dart';
import 'package:academix/features/assignments/data/models/assignment.dart';
import 'package:academix/features/assignments/data/models/submission.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

class AssignmentUpload {
  const AssignmentUpload({required this.name, required this.bytes});

  final String name;
  final Uint8List bytes;
}

abstract interface class AssignmentRepository {
  Future<List<Assignment>> listClassAssignments(String token, String classId);
  Future<List<Assignment>> listStudentAssignments(String token);
  Future<Assignment> getAssignment(String token, String assignmentId);
  Future<StudentAssignmentRubric> getStudentRubric(
    String token,
    String assignmentId,
  );
  Future<Assignment> createAssignment(
    String token,
    String classId,
    Map<String, dynamic> values,
  );
  Future<Assignment> updateAssignment(
    String token,
    String assignmentId,
    Map<String, dynamic> values,
  );
  Future<Assignment> setPublished(
    String token,
    String assignmentId,
    bool isPublished,
  );
  Future<void> archiveAssignment(String token, String assignmentId);
  Future<List<AssignmentFile>> uploadAssignmentFiles(
    String token,
    String assignmentId,
    List<AssignmentUpload> files,
  );
  Future<List<Submission>> listSubmissions(String token, String assignmentId);
  Future<Submission> gradeSubmission(
    String token,
    String submissionId, {
    double? marks,
    String? feedback,
  });
  Future<Submission> submit(
    String token,
    String assignmentId, {
    String? text,
    required bool isDraft,
    required List<AssignmentUpload> files,
  });
  Future<List<Submission>> listMySubmissions(String token);
  Future<Submission> getMySubmission(String token, String submissionId);
  Future<Uint8List> downloadFile(String token, AssignmentFile file);
}

class HttpAssignmentRepository implements AssignmentRepository {
  HttpAssignmentRepository({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Map<String, String> _headers(String token) => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Future<List<Assignment>> _assignmentList(http.Response response) async =>
      (jsonDecode(response.body) as List<dynamic>)
          .map((item) => Assignment.fromJson(item as Map<String, dynamic>))
          .toList();

  Future<List<Submission>> _submissionList(http.Response response) async =>
      (jsonDecode(response.body) as List<dynamic>)
          .map((item) => Submission.fromJson(item as Map<String, dynamic>))
          .toList();

  Assignment _assignment(http.Response response) =>
      Assignment.fromJson(jsonDecode(response.body) as Map<String, dynamic>);

  Submission _submission(http.Response response) =>
      Submission.fromJson(jsonDecode(response.body) as Map<String, dynamic>);

  @override
  Future<List<Assignment>> listClassAssignments(
    String token,
    String classId,
  ) async {
    final response = await _apiClient.get(
      '/api/v1/classes/$classId/assignments',
      headers: _headers(token),
    );
    return _assignmentList(response);
  }

  @override
  Future<List<Assignment>> listStudentAssignments(String token) async {
    final response = await _apiClient.get(
      '/api/v1/student/assignments',
      headers: _headers(token),
    );
    return _assignmentList(response);
  }

  @override
  Future<Assignment> getAssignment(String token, String assignmentId) async {
    final response = await _apiClient.get(
      '/api/v1/assignments/$assignmentId',
      headers: _headers(token),
    );
    return _assignment(response);
  }

  @override
  Future<StudentAssignmentRubric> getStudentRubric(
    String token,
    String assignmentId,
  ) async {
    final response = await _apiClient.get(
      '/api/v1/student/assignments/$assignmentId/rubric',
      headers: _headers(token),
    );
    return StudentAssignmentRubric.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  @override
  Future<Assignment> createAssignment(
    String token,
    String classId,
    Map<String, dynamic> values,
  ) async {
    final response = await _apiClient.post(
      '/api/v1/classes/$classId/assignments',
      headers: _headers(token),
      body: values,
    );
    return _assignment(response);
  }

  @override
  Future<Assignment> updateAssignment(
    String token,
    String assignmentId,
    Map<String, dynamic> values,
  ) async {
    final response = await _apiClient.put(
      '/api/v1/assignments/$assignmentId',
      headers: _headers(token),
      body: values,
    );
    return _assignment(response);
  }

  @override
  Future<Assignment> setPublished(
    String token,
    String assignmentId,
    bool isPublished,
  ) async {
    final response = await _apiClient.patch(
      '/api/v1/assignments/$assignmentId/publish',
      headers: _headers(token),
      body: {'is_published': isPublished},
    );
    return _assignment(response);
  }

  @override
  Future<void> archiveAssignment(String token, String assignmentId) async {
    await _apiClient.delete(
      '/api/v1/assignments/$assignmentId',
      headers: _headers(token),
    );
  }

  @override
  Future<List<AssignmentFile>> uploadAssignmentFiles(
    String token,
    String assignmentId,
    List<AssignmentUpload> files,
  ) async {
    if (files.isEmpty) return [];
    final response = await _apiClient.multipartPost(
      '/api/v1/assignments/$assignmentId/attachments',
      headers: {'Authorization': 'Bearer $token'},
      fields: const {},
      files: files.map(_multipartFile).toList(),
    );
    return (jsonDecode(response.body) as List<dynamic>)
        .map((item) => AssignmentFile.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Submission>> listSubmissions(
    String token,
    String assignmentId,
  ) async {
    final response = await _apiClient.get(
      '/api/v1/assignments/$assignmentId/submissions',
      headers: _headers(token),
    );
    return _submissionList(response);
  }

  @override
  Future<Submission> gradeSubmission(
    String token,
    String submissionId, {
    double? marks,
    String? feedback,
  }) async {
    final body = <String, dynamic>{};
    if (marks != null) body['marks_obtained'] = marks;
    if (feedback != null && feedback.trim().isNotEmpty) {
      body['teacher_feedback'] = feedback.trim();
    }
    final response = await _apiClient.post(
      '/api/v1/submissions/$submissionId/grade',
      headers: _headers(token),
      body: body,
    );
    return _submission(response);
  }

  @override
  Future<Submission> submit(
    String token,
    String assignmentId, {
    String? text,
    required bool isDraft,
    required List<AssignmentUpload> files,
  }) async {
    final fields = <String, String>{'is_draft': isDraft.toString()};
    if (text != null) fields['submission_text'] = text;
    final response = await _apiClient.multipartPost(
      '/api/v1/assignments/$assignmentId/submissions',
      headers: {'Authorization': 'Bearer $token'},
      fields: fields,
      files: files.map(_multipartFile).toList(),
    );
    return _submission(response);
  }

  @override
  Future<List<Submission>> listMySubmissions(String token) async {
    final response = await _apiClient.get(
      '/api/v1/student/submissions',
      headers: _headers(token),
    );
    return _submissionList(response);
  }

  @override
  Future<Submission> getMySubmission(String token, String submissionId) async {
    final response = await _apiClient.get(
      '/api/v1/student/submissions/$submissionId',
      headers: _headers(token),
    );
    return _submission(response);
  }

  @override
  Future<Uint8List> downloadFile(String token, AssignmentFile file) async =>
      _apiClient.getBytes(
        file.downloadUrl,
        headers: {'Authorization': 'Bearer $token'},
      );

  http.MultipartFile _multipartFile(AssignmentUpload file) {
    final extension = file.name.split('.').last.toLowerCase();
    final mime = switch (extension) {
      'pdf' => MediaType('application', 'pdf'),
      'jpg' || 'jpeg' => MediaType('image', 'jpeg'),
      'png' => MediaType('image', 'png'),
      'doc' => MediaType('application', 'msword'),
      'docx' => MediaType(
        'application',
        'vnd.openxmlformats-officedocument.wordprocessingml.document',
      ),
      _ => MediaType('application', 'octet-stream'),
    };
    return http.MultipartFile.fromBytes(
      'files',
      file.bytes,
      filename: file.name,
      contentType: mime,
    );
  }
}
