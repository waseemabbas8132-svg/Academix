import 'dart:convert';

import 'package:academix/core/network/api_client.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/features/assignments/data/models/ai_evaluation.dart';
import 'package:http/http.dart' as http;

abstract interface class AIEvaluationRepository {
  Future<AssignmentRubric> getRubric(String token, String assignmentId);
  Future<AssignmentRubric> saveRubric(
    String token,
    String assignmentId,
    Map<String, dynamic> values,
  );
  Future<EvaluationJob?> getLatest(String token, String submissionId);
  Future<EvaluationJob> request(
    String token,
    String submissionId, {
    bool force = false,
  });
  Future<EvaluationJob> retry(String token, String jobId);
  Future<AIEvaluation> saveReview(
    String token,
    String evaluationId, {
    required String feedback,
    required Map<String, double?> questionMarks,
    required Map<String, String> questionFeedback,
  });
  Future<AIEvaluation> approve(
    String token,
    String evaluationId, {
    required double marks,
    required String feedback,
    required Map<String, double> questionMarks,
    required Map<String, String> questionFeedback,
  });
  Future<void> publish(String token, String evaluationId);
  Future<bool> isGradePublished(
    String token,
    String submissionId, {
    required double approvedMarks,
    required String teacherFeedback,
  });
  Future<AIEvaluation> reject(
    String token,
    String evaluationId,
    String reason,
  );
}

class HttpAIEvaluationRepository implements AIEvaluationRepository {
  HttpAIEvaluationRepository({ApiClient? apiClient})
    : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Map<String, String> _headers(String token) => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Map<String, dynamic> _object(http.Response response) =>
      jsonDecode(response.body) as Map<String, dynamic>;

  @override
  Future<AssignmentRubric> getRubric(String token, String assignmentId) async {
    final response = await _apiClient.get(
      '/api/v1/assignments/$assignmentId/rubric',
      headers: _headers(token),
    );
    return AssignmentRubric.fromJson(_object(response));
  }

  @override
  Future<AssignmentRubric> saveRubric(
    String token,
    String assignmentId,
    Map<String, dynamic> values,
  ) async {
    final response = await _apiClient.put(
      '/api/v1/assignments/$assignmentId/rubric',
      headers: _headers(token),
      body: values,
    );
    return AssignmentRubric.fromJson(_object(response));
  }

  @override
  Future<EvaluationJob?> getLatest(String token, String submissionId) async {
    try {
      final response = await _apiClient.get(
        '/api/v1/submissions/$submissionId/evaluations',
        headers: _headers(token),
      );
      return EvaluationJob.fromJson(_object(response));
    } on NotFoundException {
      return null;
    }
  }

  @override
  Future<EvaluationJob> request(
    String token,
    String submissionId, {
    bool force = false,
  }) async {
    final response = await _apiClient.post(
      '/api/v1/submissions/$submissionId/evaluations',
      headers: _headers(token),
      body: const {},
      queryParameters: {'force': force},
    );
    return EvaluationJob.fromJson(_object(response));
  }

  @override
  Future<EvaluationJob> retry(String token, String jobId) async {
    final response = await _apiClient.post(
      '/api/v1/evaluation-jobs/$jobId/retry',
      headers: _headers(token),
      body: const {},
    );
    return EvaluationJob.fromJson(_object(response));
  }

  @override
  Future<AIEvaluation> saveReview(
    String token,
    String evaluationId, {
    required String feedback,
    required Map<String, double?> questionMarks,
    required Map<String, String> questionFeedback,
  }) async {
    final response = await _apiClient.put(
      '/api/v1/evaluations/$evaluationId/review',
      headers: _headers(token),
      body: {
        'teacher_feedback': feedback,
        'question_marks': questionMarks,
        'question_feedback': questionFeedback,
      },
    );
    return AIEvaluation.fromJson(_object(response));
  }

  @override
  Future<AIEvaluation> approve(
    String token,
    String evaluationId, {
    required double marks,
    required String feedback,
    required Map<String, double> questionMarks,
    required Map<String, String> questionFeedback,
  }) async {
    final response = await _apiClient.post(
      '/api/v1/evaluations/$evaluationId/approve',
      headers: _headers(token),
      body: {
        'marks_obtained': marks,
        'teacher_feedback': feedback,
        'question_marks': questionMarks,
        'question_feedback': questionFeedback,
      },
    );
    return AIEvaluation.fromJson(_object(response));
  }

  @override
  Future<void> publish(String token, String evaluationId) async {
    await _apiClient.post(
      '/api/v1/evaluations/$evaluationId/publish',
      headers: _headers(token),
      body: const {},
    );
  }

  @override
  Future<bool> isGradePublished(
    String token,
    String submissionId, {
    required double approvedMarks,
    required String teacherFeedback,
  }) async {
    final response = await _apiClient.get(
      '/api/v1/submissions/$submissionId',
      headers: _headers(token),
    );
    final submission = _object(response);
    final marks = submission['marks_obtained'];
    if (submission['status'] != 'graded' ||
        marks == null ||
        submission['teacher_feedback'] != teacherFeedback) {
      return false;
    }
    final publishedMarks = marks is num
        ? marks.toDouble()
        : double.parse(marks.toString());
    return (publishedMarks - approvedMarks).abs() < 0.005;
  }

  @override
  Future<AIEvaluation> reject(
    String token,
    String evaluationId,
    String reason,
  ) async {
    final response = await _apiClient.post(
      '/api/v1/evaluations/$evaluationId/reject',
      headers: _headers(token),
      body: {'reason': reason},
    );
    return AIEvaluation.fromJson(_object(response));
  }
}
