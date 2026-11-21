import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:academix/core/constants/api_constants.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/network/api_interceptors.dart';
import 'package:http/http.dart' as http;

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<http.Response> get(
    String path, {
    Map<String, String>? headers,
    Map<String, dynamic>? queryParameters,
  }) async {
    final uri = _buildUri(path, queryParameters: queryParameters);
    ApiInterceptors.logRequest('GET', uri, headers, null);

    try {
      final response = await _client.get(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
      );
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<http.Response> post(
    String path, {
    Object? body,
    Map<String, String>? headers,
    Map<String, dynamic>? queryParameters,
  }) async {
    final uri = _buildUri(path, queryParameters: queryParameters);
    final encodedBody = body is String ? body : jsonEncode(body);
    ApiInterceptors.logRequest('POST', uri, headers, encodedBody);

    try {
      final response = await _client.post(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
        body: encodedBody,
      );
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<http.Response> put(
    String path, {
    Object? body,
    Map<String, String>? headers,
  }) async {
    final uri = _buildUri(path);
    final encodedBody = body is String ? body : jsonEncode(body);
    ApiInterceptors.logRequest('PUT', uri, headers, encodedBody);

    try {
      final response = await _client.put(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
        body: encodedBody,
      );
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<http.Response> patch(
    String path, {
    Object? body,
    Map<String, String>? headers,
  }) async {
    final uri = _buildUri(path);
    final encodedBody = body is String ? body : jsonEncode(body);
    ApiInterceptors.logRequest('PATCH', uri, headers, encodedBody);

    try {
      final response = await _client.patch(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
        body: encodedBody,
      );
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<http.Response> delete(
    String path, {
    Map<String, String>? headers,
  }) async {
    final uri = _buildUri(path);
    ApiInterceptors.logRequest('DELETE', uri, headers, null);

    try {
      final response = await _client.delete(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
      );
      return _handleResponse(response);
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<http.Response> multipartPost(
    String path, {
    required Map<String, String> fields,
    required List<http.MultipartFile> files,
    Map<String, String>? headers,
  }) async {
    final uri = _buildUri(path);
    final request = http.MultipartRequest('POST', uri)
      ..fields.addAll(fields)
      ..files.addAll(files);
    final requestHeaders = Map<String, String>.from(
      headers ?? ApiInterceptors.defaultHeaders(),
    )..remove('Content-Type');
    request.headers.addAll(requestHeaders);
    ApiInterceptors.logRequest(
      'POST',
      uri,
      request.headers,
      'multipart files: ${files.length}',
    );

    try {
      final streamedResponse = await _client.send(request);
      return _handleResponse(await http.Response.fromStream(streamedResponse));
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Future<Uint8List> getBytes(
    String path, {
    Map<String, String>? headers,
  }) async {
    final uri = _buildUri(path);
    ApiInterceptors.logRequest('GET', uri, headers, null);
    try {
      final response = await _client.get(
        uri,
        headers: headers ?? ApiInterceptors.defaultHeaders(),
      );
      return _handleResponse(response).bodyBytes;
    } on SocketException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    } on http.ClientException catch (_) {
      throw const NetworkException(
        message: 'Network unavailable. Please try again.',
      );
    }
  }

  Uri _buildUri(String path, {Map<String, dynamic>? queryParameters}) {
    final normalizedPath = path.startsWith('/') ? path : '/$path';
    final uri = Uri.parse('${ApiConstants.baseUrl}$normalizedPath');

    if (queryParameters == null || queryParameters.isEmpty) {
      return uri;
    }

    return uri.replace(
      queryParameters: queryParameters.map(
        (key, value) => MapEntry(key, value.toString()),
      ),
    );
  }

  http.Response _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response;
    }

    String? detail;
    try {
      final payload = jsonDecode(response.body);
      if (payload is Map && payload['detail'] is String) {
        final message = payload['detail'] as String;
        if (message.isNotEmpty && message.length <= 2048) detail = message;
      }
    } catch (_) {
      // Non-JSON errors keep the safe generic message.
    }
    switch (response.statusCode) {
      case 401:
        throw const UnauthorizedException(message: 'Authentication required.');
      case 403:
        throw const ForbiddenException(
          message: 'You do not have access to this resource.',
        );
      case 404:
        throw const NotFoundException(message: 'Resource not found.');
      case 409:
        throw ConflictException(
          message:
              detail ?? 'This resource cannot be changed in its current state.',
        );
      case 400:
      case 422:
        throw ValidationException(
          statusCode: response.statusCode,
          message: detail ?? 'Please check the information and try again.',
        );
      case 500:
      default:
        throw ServerException(
          message: 'Request failed with status ${response.statusCode}.',
        );
    }
  }
}
