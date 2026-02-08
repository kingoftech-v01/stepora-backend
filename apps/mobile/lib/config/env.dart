import 'package:flutter/foundation.dart' show kIsWeb;

class Env {
  // On web: use localhost directly
  // On Android emulator: 10.0.2.2 maps to host machine's localhost
  // On iOS simulator: localhost works directly
  static String get apiBaseUrl {
    const override = String.fromEnvironment('API_BASE_URL');
    if (override.isNotEmpty) return override;
    return kIsWeb
        ? 'http://localhost:8000/api'
        : 'http://10.0.2.2:8000/api';
  }

  static String get wsBaseUrl {
    const override = String.fromEnvironment('WS_BASE_URL');
    if (override.isNotEmpty) return override;
    return kIsWeb
        ? 'ws://localhost:8000/ws'
        : 'ws://10.0.2.2:8000/ws';
  }
}
