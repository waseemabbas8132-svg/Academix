import 'dart:convert';

import 'package:academix/core/constants/api_constants.dart';
import 'package:academix/core/network/api_client.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/features/authentication/data/models/login_request.dart';
import 'package:academix/features/authentication/domain/entities/user.dart';
import 'package:academix/core/network/api_interceptors.dart';
import 'package:academix/shared/enums/user_role.dart';

abstract class AuthRemoteDataSource {
  Future<User> login({required String email, required String password});
  Future<User> getCurrentUser({required String token});
}

class AuthRemoteDataSourceImpl implements AuthRemoteDataSource {
  const AuthRemoteDataSourceImpl(this.apiClient);

  final ApiClient apiClient;

  @override
  Future<User> login({required String email, required String password}) async {
    try {
      final response = await apiClient.post(
        ApiConstants.loginEndpoint,
        body: LoginRequest(email: email, password: password).toJson(),
      );

      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      final token = payload['token']?.toString();
      final userData = payload['user'] as Map<String, dynamic>? ?? {};
      final rawRole = userData['role']?.toString() ?? 'student';
      final role = UserRole.values.firstWhere(
        (userRole) => userRole.name == rawRole,
        orElse: () => UserRole.student,
      );

      return User(
        id: userData['id']?.toString() ?? 'demo-user',
        name: userData['name']?.toString() ?? 'Academix User',
        email: userData['email']?.toString() ?? email,
        role: role,
        token: token,
      );
    } on ApiException {
      rethrow;
    }
  }

  @override
  Future<User> getCurrentUser({required String token}) async {
    try {
      final response = await apiClient.get(
        ApiConstants.meEndpoint,
        headers: ApiInterceptors.defaultHeaders(token: token),
      );

      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      final role = UserRole.values.firstWhere(
        (userRole) => userRole.name == payload['role']?.toString(),
        orElse: () => UserRole.student,
      );

      return User(
        id: payload['id']?.toString() ?? 'unknown-user',
        name: payload['name']?.toString() ?? 'Academix User',
        email: payload['email']?.toString() ?? '',
        role: role,
        token: token,
      );
    } on ApiException {
      rethrow;
    }
  }
}
