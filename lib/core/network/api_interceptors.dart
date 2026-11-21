import 'package:flutter/foundation.dart';

class ApiInterceptors {
  const ApiInterceptors._();

  static Map<String, String> defaultHeaders({String? token}) {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }

    return headers;
  }

  static void logRequest(String method, Uri uri, Map<String, String>? headers, Object? body) {
    if (kDebugMode) {
      debugPrint('[$method] $uri');
      debugPrint('Headers: $headers');
      if (body != null) {
        debugPrint('Body: $body');
      }
    }
  }
}
