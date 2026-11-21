import 'package:academix/features/authentication/presentation/providers/auth_provider.dart';
import 'package:provider/provider.dart';

class AppProviders {
  const AppProviders._();

  static final AuthProvider authProvider = AuthProvider();

  static List<ChangeNotifierProvider<AuthProvider>> get providers => [
        ChangeNotifierProvider<AuthProvider>.value(value: authProvider),
      ];
}
