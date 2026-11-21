import 'package:academix/features/authentication/domain/entities/user.dart';
import 'package:academix/features/authentication/domain/repositories/auth_repository.dart';

class LoginUseCase {
  const LoginUseCase(this.repository);

  final AuthRepository repository;

  Future<User> call({required String email, required String password}) {
    return repository.login(email: email, password: password);
  }

  Future<User> getCurrentUser({required String token}) {
    return repository.getCurrentUser(token: token);
  }
}
