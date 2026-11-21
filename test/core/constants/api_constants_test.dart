import 'package:academix/core/constants/api_constants.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses the host-loopback URL for Android emulator requests', () {
    final previousPlatform = debugDefaultTargetPlatformOverride;
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = previousPlatform;
    });

    expect(ApiConstants.baseUrl, 'http://10.0.2.2:8000');
  });

  test('uses the local host URL for non-Android clients', () {
    final previousPlatform = debugDefaultTargetPlatformOverride;
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    addTearDown(() {
      debugDefaultTargetPlatformOverride = previousPlatform;
    });

    expect(ApiConstants.baseUrl, 'http://127.0.0.1:8000');
  });
}
