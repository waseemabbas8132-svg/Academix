import 'dart:convert';

import 'package:academix/app/router/route_names.dart';
import 'package:academix/core/network/api_client.dart';
import 'package:academix/core/network/api_exceptions.dart';
import 'package:academix/core/storage/secure_storage_service.dart';
import 'package:academix/features/authentication/data/datasources/auth_remote_data_source.dart';
import 'package:academix/features/authentication/data/repositories/auth_repository_impl.dart';
import 'package:academix/features/authentication/domain/entities/user.dart';
import 'package:academix/features/authentication/domain/usecases/login_usecase.dart';
import 'package:academix/shared/enums/user_role.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider() : _loginUseCase = LoginUseCase(
          AuthRepositoryImpl(
            AuthRemoteDataSourceImpl(ApiClient()),
          ),
        );

  static const String tokenKey = 'auth_token';
  static const String userKey = 'auth_user';

  final LoginUseCase _loginUseCase;
  bool _isLoading = false;
  String? _errorMessage;
  User? _currentUser;
  String? _token;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  User? get currentUser => _currentUser;
  String? get token => _token;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty && _currentUser != null;

  Future<void> restoreSession() async {
    _errorMessage = null;
    final storedToken = await SecureStorageService().read(key: tokenKey);
    if (storedToken == null || storedToken.isEmpty) {
      await clearSession();
      return;
    }

    try {
      final user = await _loginUseCase.getCurrentUser(token: storedToken);
      _token = storedToken;
      _currentUser = user;
      notifyListeners();
    } catch (_) {
      await clearSession();
    }
  }

  Future<bool> login({
    required BuildContext context,
    required String email,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final user = await _loginUseCase.call(email: email, password: password);
      if (user.token == null || user.token!.isEmpty) {
        throw const ApiException(message: 'Authentication did not return a token.');
      }

      _currentUser = user;
      _token = user.token;
      await _persistSession(user, user.token!);
      _isLoading = false;
      notifyListeners();

      if (!context.mounted) return true;

      switch (user.role) {
        case UserRole.teacher:
          context.go(RouteNames.teacherDashboard);
          break;
        case UserRole.student:
          context.go(RouteNames.studentDashboard);
          break;
        case UserRole.admin:
          context.go(RouteNames.dashboard);
          break;
      }

      return true;
    } on UnauthorizedException {
      _errorMessage = 'Invalid email or password.';
    } on ForbiddenException {
      _errorMessage = 'You do not have permission to access this account.';
    } on NetworkException {
      _errorMessage = 'Network error. Please check your connection and try again.';
    } on ServerException {
      _errorMessage = 'Server is unavailable. Please try again later.';
    } catch (_) {
      _errorMessage = 'Unable to sign in. Please try again.';
    } finally {
      _isLoading = false;
      notifyListeners();
    }

    return false;
  }

  Future<void> logout({required BuildContext context}) async {
    await clearSession();
    if (context.mounted) {
      context.go(RouteNames.login);
    }
  }

  Future<void> clearSession() async {
    _currentUser = null;
    _token = null;
    _errorMessage = null;
    await SecureStorageService().delete(key: tokenKey);
    await SecureStorageService().delete(key: userKey);
    notifyListeners();
  }

  Future<void> _persistSession(User user, String token) async {
    await SecureStorageService().write(key: tokenKey, value: token);
    await SecureStorageService().write(key: userKey, value: jsonEncode(user.toJson()));
  }
}
