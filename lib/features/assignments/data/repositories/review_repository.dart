import 'dart:convert';
import 'dart:typed_data';

import 'package:academix/core/network/api_client.dart';

/// Application review APIs only. No operation here starts an AI job.
class ReviewRepository {
  ReviewRepository({ApiClient? client}) : client = client ?? ApiClient();
  final ApiClient client;
  Map<String, String> headers(String token) => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };
  Future<Map<String, dynamic>> get(
    String token,
    String path, {
    Map<String, dynamic>? query,
  }) async {
    final response = await client.get(
      '/api/v1$path',
      headers: headers(token),
      queryParameters: query,
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>?> released(String token, String id) async {
    final response = await client.get(
      '/api/v1/submissions/$id/released-review',
      headers: headers(token),
    );
    return jsonDecode(response.body) as Map<String, dynamic>?;
  }

  Future<Map<String, dynamic>> save(
    String token,
    String id,
    Map<String, dynamic> body,
  ) async {
    final response = await client.put(
      '/api/v1/submissions/$id/review',
      headers: headers(token),
      body: body,
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> action(
    String token,
    String id,
    String action,
    Map<String, dynamic> body,
  ) async {
    final response = await client.post(
      '/api/v1/submissions/$id/review/$action',
      headers: headers(token),
      body: body,
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Uint8List> page(String token, String fileId, int page) =>
      client.getBytes(
        '/api/v1/files/$fileId/preview/pages/$page',
        headers: headers(token),
      );
}
