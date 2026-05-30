import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/notification_inbox_item.dart';

class ApgLaunchPayload {
  final String? notificationId;
  final String? analysisId;

  const ApgLaunchPayload({this.notificationId, this.analysisId});

  bool get hasTarget =>
      (notificationId?.trim().isNotEmpty ?? false) ||
      (analysisId?.trim().isNotEmpty ?? false);

  factory ApgLaunchPayload.fromMap(Map<dynamic, dynamic> map) {
    return ApgLaunchPayload(
      notificationId: map['notificationId']?.toString(),
      analysisId: map['analysisId']?.toString(),
    );
  }
}

enum _ThreatNotificationLevel { safe, suspicious, dangerous }

class ApgLocalNotificationService {
  ApgLocalNotificationService._();

  static const MethodChannel _channel = MethodChannel(
    'apg/native_notifications',
  );
  static const String _threatChannelId = 'apg_threat_alerts_v2';
  static const Duration _notificationCooldown = Duration(seconds: 90);
  static final Map<String, DateTime> _recentThreatNotifications =
      <String, DateTime>{};

  static Future<void> configureMonitoredPackages(Set<String> packages) async {
    if (!Platform.isAndroid) return;
    try {
      await _channel.invokeMethod<void>('configureMonitoredPackages', {
        'packages': packages.toList(),
      });
    } catch (error) {
      _log('configureMonitoredPackages failed: $error');
    }
  }

  static Future<void> requestPostNotificationsPermission() async {
    if (!Platform.isAndroid) return;
    try {
      _log('requestPostNotificationsPermission start');
      await _channel.invokeMethod<void>('requestPostNotifications');
      _log(
        'requestPostNotificationsPermission afterRequest granted=${await hasPostNotificationsPermission()}',
      );
    } catch (error) {
      _log('requestPostNotifications failed: $error');
    }
  }

  static Future<bool> hasPostNotificationsPermission() async {
    if (!Platform.isAndroid) return false;
    try {
      final granted = await _channel.invokeMethod<bool>('hasPostNotifications');
      _log('hasPostNotificationsPermission granted=${granted == true}');
      return granted == true;
    } catch (error) {
      _log('hasPostNotificationsPermission failed: $error');
      return false;
    }
  }

  static Future<void> showDebugTestNotification() async {
    if (!Platform.isAndroid) return;
    _log('showDebugTestNotification invoking native bridge');
    try {
      await _channel.invokeMethod<void>('showDebugTestAlert');
      _log('showDebugTestNotification bridge returned');
    } catch (error) {
      _log('showDebugTestNotification failed: $error');
    }
  }

  static Future<void> requestContactsPermission() async {
    if (!Platform.isAndroid) return;
    try {
      await _channel.invokeMethod<void>('requestReadContacts');
    } catch (error) {
      _log('requestReadContacts failed: $error');
    }
  }

  // Floating alerts are intentionally disabled. External alerts use Android
  // system notifications only.
  static Future<void> setFloatingAlertsEnabled(bool enabled) async {}
  static Future<bool> hasOverlayPermission() async => false;
  static Future<void> openOverlayPermissionSettings() async {}

  static Future<bool?> isKnownContact(String sender) async {
    if (!Platform.isAndroid || sender.trim().isEmpty) return null;
    try {
      final raw = await _channel.invokeMethod<dynamic>('isKnownContact', {
        'sender': sender.trim(),
      });
      if (raw is bool) return raw;
    } catch (error) {
      _log('isKnownContact failed: $error');
    }
    return null;
  }

  static Future<ApgLaunchPayload?> getLaunchPayload() async {
    if (!Platform.isAndroid) return null;
    try {
      final raw = await _channel.invokeMethod<dynamic>('getLaunchPayload');
      if (raw is Map && raw.isNotEmpty) return ApgLaunchPayload.fromMap(raw);
    } catch (error) {
      _log('getLaunchPayload failed: $error');
    }
    return null;
  }

  static Future<void> clearLaunchPayload() async {
    if (!Platform.isAndroid) return;
    try {
      await _channel.invokeMethod<void>('clearLaunchPayload');
    } catch (error) {
      _log('clearLaunchPayload failed: $error');
    }
  }

  static Future<void> showForNotification(NotificationInboxItem item) async {
    if (!Platform.isAndroid) return;
    if (item.packageName.trim().isEmpty) {
      _log('showForNotification skipped reason=empty_package');
      return;
    }

    final result = item.result;
    if (result == null) {
      _log('showForNotification skipped reason=no_analysis item=${item.id}');
      return;
    }

    _log(
      'showForNotification decision item=${item.id} package=${item.packageName} '
      'finalLabel=${result.finalLabel} finalScore=${result.finalScore}',
    );

    final level = _levelForLabel(result.finalLabel);
    if (level == _ThreatNotificationLevel.safe) {
      _log(
        'showForNotification skipped reason=safe label=${result.finalLabel}',
      );
      return;
    }

    final fingerprint = _fingerprintFor(item);
    final now = DateTime.now();
    _pruneRecentThreatNotifications(now);
    final lastShownAt = _recentThreatNotifications[fingerprint];
    if (lastShownAt != null &&
        now.difference(lastShownAt) < _notificationCooldown) {
      final remaining = _notificationCooldown - now.difference(lastShownAt);
      _log(
        'showForNotification skipped reason=duplicate fingerprint=${fingerprint.hashCode} remainingMs=${remaining.inMilliseconds}',
      );
      return;
    }
    _recentThreatNotifications[fingerprint] = now;

    final riskScore = result.finalScore;
    final sourceNotificationId = item.notificationId == null
        ? item.id
        : '${item.packageName}|${item.notificationId}';
    final analysisId = result.remoteId.trim().isNotEmpty
        ? result.remoteId.trim()
        : item.id;

    _log(
      'showForNotification calling native channel=$_threatChannelId score=$riskScore '
      'label=${result.finalLabel} fingerprint=${fingerprint.hashCode} analysisIdHash=${analysisId.hashCode}',
    );

    try {
      await _channel.invokeMethod<void>('showLocalAlert', {
        'channelId': _threatChannelId,
        'riskScore': riskScore,
        'title': _titleForLevel(level),
        'body': _bodyForLevel(level, riskScore, result.reasons),
        'notificationId': sourceNotificationId,
        'analysisId': analysisId,
        'fingerprint': fingerprint,
      });
    } catch (error) {
      _log('showForNotification failed: $error');
    }
  }

  static _ThreatNotificationLevel _levelForLabel(String label) {
    switch (label.trim().toLowerCase()) {
      case 'safe':
      case 'legit':
      case 'benign':
      case 'low_risk':
      case 'low-risk':
        return _ThreatNotificationLevel.safe;
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
      case 'high-risk':
      case 'malicious':
      case 'scam':
        return _ThreatNotificationLevel.dangerous;
      default:
        return _ThreatNotificationLevel.suspicious;
    }
  }

  static String _titleForLevel(_ThreatNotificationLevel level) {
    return switch (level) {
      _ThreatNotificationLevel.suspicious =>
        'APG: \u0631\u0633\u0627\u0644\u0629 \u062a\u062d\u062a\u0627\u062c \u062a\u062d\u0642\u0642\u064b\u0627',
      _ThreatNotificationLevel.dangerous =>
        'APG: \u062a\u062d\u0630\u064a\u0631 \u0645\u0646 \u0645\u062d\u0627\u0648\u0644\u0629 \u062a\u0635\u064a\u062f',
      _ThreatNotificationLevel.safe => 'APG',
    };
  }

  static String _bodyForLevel(
    _ThreatNotificationLevel level,
    int riskScore,
    List<String> reasons,
  ) {
    final fallback = switch (level) {
      _ThreatNotificationLevel.suspicious =>
        '\u062a\u062d\u0642\u0642 \u0642\u0628\u0644 \u0627\u0644\u062a\u0641\u0627\u0639\u0644.',
      _ThreatNotificationLevel.dangerous =>
        '\u0644\u0627 \u062a\u0636\u063a\u0637 \u0639\u0644\u0649 \u0627\u0644\u0631\u0627\u0628\u0637.',
      _ThreatNotificationLevel.safe => '',
    };
    final reason = _shortReason(reasons) ?? fallback;
    return '\u062f\u0631\u062c\u0629 \u0627\u0644\u062e\u0637\u0648\u0631\u0629 $riskScore/100 \u2014 $reason';
  }

  static String? _shortReason(List<String> reasons) {
    for (final raw in reasons) {
      final reason = _mapReason(raw).trim().replaceAll(RegExp(r'\s+'), ' ');
      if (reason.isEmpty) continue;
      if (reason.length <= 72) return reason;
      return '${reason.substring(0, 71)}...';
    }
    return null;
  }

  static String _mapReason(String value) {
    switch (value.trim()) {
      case 'The message contains urgent pressure language.':
        return '\u0627\u0644\u0631\u0633\u0627\u0644\u0629 \u062a\u0633\u062a\u062e\u062f\u0645 \u0644\u063a\u0629 \u0636\u063a\u0637 \u0648\u0627\u0633\u062a\u0639\u062c\u0627\u0644.';
      case 'The message asks for sensitive credentials or OTP.':
        return '\u0627\u0644\u0631\u0633\u0627\u0644\u0629 \u062a\u0637\u0644\u0628 \u0628\u064a\u0627\u0646\u0627\u062a \u062d\u0633\u0627\u0633\u0629 \u0623\u0648 OTP.';
      case 'The URL appears deceptive or unusual.':
        return '\u0627\u0644\u0631\u0627\u0628\u0637 \u064a\u0628\u062f\u0648 \u0645\u062e\u0627\u062f\u0639\u064b\u0627 \u0623\u0648 \u063a\u064a\u0631 \u0645\u0639\u062a\u0627\u062f.';
      case 'The URL domain does not match the claimed brand.':
        return '\u0646\u0637\u0627\u0642 \u0627\u0644\u0631\u0627\u0628\u0637 \u0644\u0627 \u064a\u0637\u0627\u0628\u0642 \u0627\u0644\u062c\u0647\u0629 \u0627\u0644\u0645\u062f\u0639\u0627\u0629.';
      case 'Multiple layers indicate phishing risk.':
        return '\u0639\u062f\u0629 \u0645\u0624\u0634\u0631\u0627\u062a \u062a\u0634\u064a\u0631 \u0625\u0644\u0649 \u062e\u0637\u0631 \u062a\u0635\u064a\u062f.';
      default:
        return value;
    }
  }

  static String _fingerprintFor(NotificationInboxItem item) {
    final result = item.result!;
    final resultId = result.remoteId.trim();
    if (resultId.isNotEmpty) return 'id:${resultId.toLowerCase()}';

    final normalizedMessage =
        [
              item.rawCombinedText,
              item.detectedUrl,
              result.maskedText,
              result.detectedUrl,
            ]
            .where((value) => value.trim().isNotEmpty)
            .join(' ')
            .trim()
            .toLowerCase()
            .replaceAll(RegExp(r'\s+'), ' ');
    final source =
        '$normalizedMessage|${result.finalScore}|${result.finalLabel.trim().toLowerCase()}';
    return 'hash:${_stableFnv1a32(source)}';
  }

  static String _stableFnv1a32(String value) {
    var hash = 0x811c9dc5;
    for (final codeUnit in value.codeUnits) {
      hash ^= codeUnit;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }

  static void _pruneRecentThreatNotifications(DateTime now) {
    _recentThreatNotifications.removeWhere(
      (_, shownAt) => now.difference(shownAt) > _notificationCooldown,
    );
  }

  static void _log(String message) {
    debugPrint('APG_NOTIFY_DEBUG $message');
  }
}
