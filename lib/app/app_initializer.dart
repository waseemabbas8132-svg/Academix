import 'package:academix/app/providers/app_providers.dart';
import 'package:academix/core/storage/secure_storage_service.dart';

class AppInitializer {
  const AppInitializer._();

  static Future<void> initialize() async {
    await SecureStorageService().init();
    await AppProviders.authProvider.restoreSession();
  }
}
