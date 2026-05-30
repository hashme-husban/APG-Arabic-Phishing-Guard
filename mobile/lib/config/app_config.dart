import 'package:flutter/foundation.dart';

class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'APG_API_BASE_URL',
    defaultValue: 'http://YOUR_SERVER_IP/api',
  );

  // Runtime stability switches.
  // These prevent startup freezes/crashes caused by network checks or Android
  // notification-listener plugins running too early during app launch.
  static const bool checkServerOnStartup = false;
  static const bool startNotificationListenerOnStartup = false;

  // Keep offline fallback disabled for production APK builds.
  static const bool enableOfflineDemoFallback = false;

  static String normalizeBaseUrl(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return '';

    final withScheme = trimmed.contains('://') ? trimmed : 'http://$trimmed';
    return withScheme.endsWith('/')
        ? withScheme.substring(0, withScheme.length - 1)
        : withScheme;
  }

  static List<String> apiBaseCandidates([String? _]) {
    final seen = <String>{};
    final ordered = <String>[normalizeBaseUrl(apiBaseUrl)];

    return ordered
        .where((value) => value.isNotEmpty && seen.add(value))
        .toList();
  }

  static Uri endpoint(String path) {
    final cleanBase = normalizeBaseUrl(apiBaseUrl);
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanBase$cleanPath');
  }

  static void logStartupConfig() {
    if (kDebugMode) {
      debugPrint('[APG CONFIG] API base URL: ${normalizeBaseUrl(apiBaseUrl)}');
    }
  }

  static const Map<String, String> supportedApps = {
    'com.whatsapp': 'WhatsApp',
    'org.telegram.messenger': 'Telegram',
    'com.google.android.gm': 'Gmail',
    'com.google.android.apps.messaging': 'Google Messages',
    'com.android.mms': 'SMS',
    'com.samsung.android.messaging': 'Samsung Messages',
    'com.facebook.orca': 'Messenger',
    'com.instagram.android': 'Instagram',
  };

  static Set<String> defaultMonitoredPackages() {
    return supportedApps.keys.toSet();
  }

  static bool shouldMonitor(String packageName, Set<String> monitoredPackages) {
    return monitoredPackages.contains(packageName);
  }

  static String channelForPackage(String packageName) {
    switch (packageName) {
      case 'com.whatsapp':
        return 'واتساب';
      case 'org.telegram.messenger':
        return 'تيليجرام';
      case 'com.google.android.gm':
        return 'Email';
      case 'com.google.android.apps.messaging':
      case 'com.samsung.android.messaging':
      case 'com.android.mms':
        return 'SMS';
      default:
        return 'إشعار تطبيق';
    }
  }

  static String displayNameForPackage(String packageName) {
    return supportedApps[packageName] ?? 'تطبيق';
  }
}
