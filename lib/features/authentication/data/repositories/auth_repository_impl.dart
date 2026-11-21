import 'package:academix/features/authentication/data/datasources/auth_remote_data_source.dart';
import 'package:academix/features/authentication/domain/entities/user.dart';
import 'package:academix/features/authentication/domain/repositories/auth_repository.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl(this.remoteDataSource);

  final AuthRemoteDataSource remoteDataSource;

  @override
  Future<User> login({required String email, required String password}) {
    return remoteDataSource.login(email: email, password: password);
  }

  @override
  Future<User> getCurrentUser({required String token}) {
    return remoteDataSource.getCurrentUser(token: token);
  }
}
