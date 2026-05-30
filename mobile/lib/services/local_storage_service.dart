import 'package:hive_ce_flutter/hive_ce_flutter.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../config/app_config.dart';
import '../models/analysis_history_item.dart';
import '../models/notification_inbox_item.dart';
import 'dart:math';

class LocalStorageService {
  LocalStorageService._();
  static final LocalStorageService instance = LocalStorageService._();

  static const String _settingsBoxName = 'apg_settings';
  static const String _historyBoxPrefix = 'apg_history';
  static const String _notificationsBoxPrefix = 'apg_notifications';
  static const String _feedbackBoxName = 'apg_feedback';

  Box? _settingsBox;
  Box? _historyBox;
  Box? _notificationsBox;
  Box? _feedbackBox;
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();
  String? _secureToken;
  int? _activeUserId;
  bool _localDataWasRebuilt = false;

  bool get localDataWasRebuilt => _localDataWasRebuilt;

  bool get _ready =>
      _settingsBox != null && _historyBox != null && _notificationsBox != null;

  Future<void> init() async {
    await Hive.initFlutter();
    _localDataWasRebuilt = false;
    _settingsBox = await _openBoxWithRecovery(_settingsBoxName);
    _feedbackBox = await _openBoxWithRecovery(_feedbackBoxName);
    try {
      _secureToken = await _secureStorage.read(key: 'session_token');
    } catch (_) {
      _secureToken = null;
    }
    await _activateScopedBoxes(getSessionUserId());
  }

  Future<Box> _openBoxWithRecovery(String boxName) async {
    try {
      return await Hive.openBox(boxName);
    } catch (_) {
      _localDataWasRebuilt = true;
      try {
        await Hive.deleteBoxFromDisk(boxName);
      } catch (_) {}
      return Hive.openBox(boxName);
    }
  }

  T _safeGet<T>(Box? box, String key, T defaultValue) {
    try {
      final value = box?.get(key, defaultValue: defaultValue);
      return value is T ? value : defaultValue;
    } catch (_) {
      return defaultValue;
    }
  }

  Future<void> _safePut(Box? box, String key, Object? value) async {
    try {
      await box?.put(key, value);
    } catch (_) {}
  }

  String _scopedBoxName(String prefix, int userId) => '${prefix}_$userId';

  String? get _deletedHistoryIdsKey {
    final userId = _activeUserId ?? getSessionUserId();
    return userId == null ? null : 'deleted_history_ids_$userId';
  }

  Future<void> _activateScopedBoxes(int? userId) async {
    if (_activeUserId == userId &&
        ((userId == null && _historyBox == null && _notificationsBox == null) ||
            (userId != null &&
                _historyBox != null &&
                _notificationsBox != null))) {
      return;
    }

    _historyBox = null;
    _notificationsBox = null;
    _activeUserId = userId;

    if (userId == null) return;

    _historyBox = await _openBoxWithRecovery(
      _scopedBoxName(_historyBoxPrefix, userId),
    );
    _notificationsBox = await _openBoxWithRecovery(
      _scopedBoxName(_notificationsBoxPrefix, userId),
    );
  }

  String getOrCreateDeviceId() {
    var value = _safeGet<String>(_settingsBox, 'device_id', '').trim();
    if (value.isEmpty) {
      value = _createDeviceId();
      _settingsBox?.put('device_id', value);
    }
    return value;
  }

  int? getSessionUserId() {
    final value = _safeGet<int>(_settingsBox, 'session_user_id', 0);
    return value == 0 ? null : value;
  }

  bool getDarkMode() {
    return _safeGet<bool>(_settingsBox, 'dark_mode', false);
  }

  Future<void> setDarkMode(bool value) async {
    await _safePut(_settingsBox, 'dark_mode', value);
  }

  bool getSaveHistoryEnabled() {
    return _safeGet<bool>(_settingsBox, 'save_history', true);
  }

  Future<void> setSaveHistoryEnabled(bool value) async {
    await _safePut(_settingsBox, 'save_history', value);
  }

  String getLanguageCode() {
    final value = _safeGet<String>(
      _settingsBox,
      'language_code',
      'ar',
    ).toLowerCase();
    return value == 'en' ? 'en' : 'ar';
  }

  Future<void> setLanguageCode(String value) async {
    await _safePut(
      _settingsBox,
      'language_code',
      value.toLowerCase() == 'en' ? 'en' : 'ar',
    );
  }

  String getAccentThemeKey() {
    final value = _safeGet<String>(
      _settingsBox,
      'accent_theme_key',
      'blue',
    ).toLowerCase();
    const allowed = {'purple', 'blue', 'cyan', 'green', 'orange', 'pink'};
    return allowed.contains(value) ? value : 'blue';
  }

  Future<void> setAccentThemeKey(String value) async {
    final normalized = value.toLowerCase().trim();
    const allowed = {'purple', 'blue', 'cyan', 'green', 'orange', 'pink'};
    await _safePut(
      _settingsBox,
      'accent_theme_key',
      allowed.contains(normalized) ? normalized : 'blue',
    );
  }

  int getLastTipIndex() {
    return _safeGet<int>(_settingsBox, 'last_tip_index', -1);
  }

  Future<void> setLastTipIndex(int value) async {
    await _safePut(_settingsBox, 'last_tip_index', value);
  }

  bool getAutoAnalyzeNotifications() {
    return _safeGet<bool>(_settingsBox, 'auto_notifications', false);
  }

  Future<void> setAutoAnalyzeNotifications(bool value) async {
    await _safePut(_settingsBox, 'auto_notifications', value);
  }

  bool getFloatingAlertsEnabled() {
    return _safeGet<bool>(_settingsBox, 'floating_alerts', false);
  }

  Future<void> setFloatingAlertsEnabled(bool value) async {
    await _safePut(_settingsBox, 'floating_alerts', value);
  }

  String? getSessionRole() {
    final value = _safeGet<String>(_settingsBox, 'session_role', '');
    final normalized = value.toLowerCase().trim();
    if (normalized == 'user' || normalized == 'admin') return normalized;
    return null;
  }

  String? getSessionToken() {
    final value =
        (_secureToken ?? _safeGet<String>(_settingsBox, 'session_token', ''))
            .trim();
    return value.isEmpty ? null : value;
  }

  String getSessionName() {
    return _safeGet<String>(_settingsBox, 'session_name', 'APG');
  }

  String getSessionEmail() {
    return _safeGet<String>(_settingsBox, 'session_email', '');
  }

  Future<void> setSession({
    required String role,
    required String token,
    String? name,
    String? email,
    int? userId,
  }) async {
    final normalized = role.toLowerCase().trim();
    if (normalized == 'user' || normalized == 'admin') {
      await _safePut(_settingsBox, 'session_role', normalized);
      _secureToken = token;
      await _safePut(_settingsBox, 'session_token', token);
      try {
        await _secureStorage.write(key: 'session_token', value: token);
      } catch (_) {}
      await _safePut(_settingsBox, 'session_name', name ?? 'APG');
      await _safePut(_settingsBox, 'session_email', email ?? '');
      if (userId != null) {
        await _safePut(_settingsBox, 'session_user_id', userId);
      } else {
        await _settingsBox?.delete('session_user_id');
      }
      await _activateScopedBoxes(userId);
    }
  }

  Future<void> setSessionRole(String? role) async {
    final normalized = role?.toLowerCase().trim();
    if (normalized == 'user' || normalized == 'admin') {
      await _safePut(_settingsBox, 'session_role', normalized);
      await _safePut(_settingsBox, 'session_token', 'legacy-$normalized-token');
      await _settingsBox?.delete('session_user_id');
      await _activateScopedBoxes(null);
    } else {
      await clearSessionRole();
    }
  }

  Future<void> clearSessionRole() async {
    try {
      await _settingsBox?.delete('session_role');
      _secureToken = null;
      await _settingsBox?.delete('session_token');
      try {
        await _secureStorage.delete(key: 'session_token');
      } catch (_) {}
      await _settingsBox?.delete('session_name');
      await _settingsBox?.delete('session_email');
      await _settingsBox?.delete('session_user_id');
      await _activateScopedBoxes(null);
    } catch (_) {}
  }

  bool getOnboardingSeen() {
    return _safeGet<bool>(_settingsBox, 'onboarding_seen', false);
  }

  Future<void> setOnboardingSeen(bool value) async {
    await _safePut(_settingsBox, 'onboarding_seen', value);
  }

  Set<String> getMonitoredPackages() {
    try {
      final raw = _settingsBox?.get(
        'monitored_packages',
        defaultValue: AppConfig.defaultMonitoredPackages().toList(),
      );

      if (raw is List) {
        return raw.map((e) => e.toString()).toSet();
      }
    } catch (_) {}

    return AppConfig.defaultMonitoredPackages();
  }

  Future<void> setMonitoredPackages(Set<String> packages) async {
    await _safePut(_settingsBox, 'monitored_packages', packages.toList());
  }

  List<AnalysisHistoryItem> loadHistory() {
    if (!_ready) return <AnalysisHistoryItem>[];

    final parsed = <AnalysisHistoryItem>[];
    try {
      for (final value in _historyBox!.values) {
        if (value is! Map) continue;
        try {
          final item = AnalysisHistoryItem.fromMap(
            Map<String, dynamic>.from(value),
          );
          if (!isHistoryItemDeleted(item.id) &&
              !isHistoryItemDeleted(item.result.remoteId)) {
            parsed.add(item);
          }
        } catch (_) {
          // Ignore old/corrupt cached records instead of crashing the app.
        }
      }
    } catch (_) {
      return <AnalysisHistoryItem>[];
    }

    parsed.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return parsed;
  }

  Future<void> saveHistoryItem(AnalysisHistoryItem item) async {
    try {
      if (isHistoryItemDeleted(item.id) ||
          isHistoryItemDeleted(item.result.remoteId)) {
        return;
      }
      await _historyBox?.put(item.id, item.toMap());
    } catch (_) {}
  }

  Future<void> deleteHistoryItem(String id) async {
    try {
      await _historyBox?.delete(id);
    } catch (_) {}
  }

  Set<String> getDeletedHistoryIds() {
    final key = _deletedHistoryIdsKey;
    if (key == null) return <String>{};
    try {
      final raw = _settingsBox?.get(key, defaultValue: <dynamic>[]);
      if (raw is List) {
        return raw
            .map((e) => e.toString())
            .where((e) => e.trim().isNotEmpty)
            .toSet();
      }
    } catch (_) {}
    return <String>{};
  }

  bool isHistoryItemDeleted(String id) {
    final value = id.trim();
    if (value.isEmpty) return false;
    return getDeletedHistoryIds().contains(value);
  }

  Future<void> markHistoryItemDeleted(AnalysisHistoryItem item) async {
    final ids = getDeletedHistoryIds();
    if (item.id.trim().isNotEmpty) ids.add(item.id.trim());
    if (item.result.remoteId.trim().isNotEmpty) {
      ids.add(item.result.remoteId.trim());
    }
    final key = _deletedHistoryIdsKey;
    if (key != null) await _safePut(_settingsBox, key, ids.toList());
    await deleteHistoryItem(item.id);
    if (item.result.remoteId.trim().isNotEmpty &&
        item.result.remoteId != item.id) {
      await deleteHistoryItem(item.result.remoteId);
    }
  }

  Future<void> clearHistory() async {
    try {
      await _historyBox?.clear();
    } catch (_) {}
  }

  List<NotificationInboxItem> loadNotifications() {
    if (!_ready) return <NotificationInboxItem>[];

    final parsed = <NotificationInboxItem>[];
    try {
      for (final value in _notificationsBox!.values) {
        if (value is! Map) continue;
        try {
          parsed.add(
            NotificationInboxItem.fromMap(Map<String, dynamic>.from(value)),
          );
        } catch (_) {
          // Ignore old/corrupt cached records instead of crashing the app.
        }
      }
    } catch (_) {
      return <NotificationInboxItem>[];
    }

    parsed.sort((a, b) => b.receivedAt.compareTo(a.receivedAt));
    return parsed;
  }

  Future<void> saveNotificationItem(NotificationInboxItem item) async {
    try {
      await _notificationsBox?.put(item.id, item.toMap());
    } catch (_) {}
  }

  Future<void> deleteNotificationItem(String id) async {
    try {
      await _notificationsBox?.delete(id);
    } catch (_) {}
  }

  Future<void> clearNotifications() async {
    try {
      await _notificationsBox?.clear();
    } catch (_) {}
  }

  Future<void> saveFeedbackReport(Map<String, dynamic> report) async {
    try {
      final id = (report['id'] ?? DateTime.now().microsecondsSinceEpoch)
          .toString();
      await _feedbackBox?.put(id, report);
    } catch (_) {}
  }

  List<Map<String, dynamic>> loadFeedbackReports() {
    final parsed = <Map<String, dynamic>>[];
    try {
      for (final value in _feedbackBox?.values ?? <dynamic>[]) {
        if (value is Map) parsed.add(Map<String, dynamic>.from(value));
      }
    } catch (_) {}
    return parsed;
  }

  List<Map<String, dynamic>> loadAnalysisFeedback() => loadFeedbackReports();
}

String _createDeviceId() {
  const chars = '0123456789abcdef';
  final random = Random.secure();
  final buffer = StringBuffer('apg-');
  for (var i = 0; i < 24; i++) {
    buffer.write(chars[random.nextInt(chars.length)]);
  }
  return buffer.toString();
}
