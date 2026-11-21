import 'package:flutter/foundation.dart';

class ApiConstants {
  const ApiConstants._();

  static String get baseUrl =>
      defaultTargetPlatform == TargetPlatform.android && !kIsWeb
          ? 'http://10.0.2.2:8000'
          : 'http://127.0.0.1:8000';

  static const String loginEndpoint = '/api/v1/auth/login';
  static const String meEndpoint = '/api/v1/auth/me';
  static const String teacherDashboardEndpoint = '/api/v1/teacher/dashboard';
  static const String studentDashboardEndpoint = '/api/v1/student/dashboard';
  static const String dashboardEndpoint = '/dashboard';
  static const String submissionsEndpoint = '/submissions';
}
