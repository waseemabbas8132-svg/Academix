import 'package:academix/features/authentication/domain/entities/user.dart';

abstract class AuthRepository {
  Future<User> login({required String email, required String password});
  Future<User> getCurrentUser({required String token});
}
