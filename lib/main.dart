import 'package:academix/app/academix_app.dart';
import 'package:academix/app/app_initializer.dart';
import 'package:flutter/material.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppInitializer.initialize();
  runApp(const AcademixApp());
}
