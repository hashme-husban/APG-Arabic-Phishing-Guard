import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:notification_listener_service/notification_listener_service.dart'
    as nls;
import '../config/app_config.dart';
import '../models/analysis_result.dart';
import '../models/notification_inbox_item.dart';
import 'apg_local_notification_service.dart';
import 'apg_api_service.dart';

class NotificationInboxService {
  final void Function(NotificationInboxItem item) onNewItem;

  NotificationInboxService({required this.onNewItem});

  StreamSubscription<dynamic>? _subscription;
  final Set<String> _recentKeys = <String>{};

  Future<bool> hasPermission() async {
    if (!Platform.isAndroid) return false;
    try {
      return await nls.NotificationListenerService.isPermissionGranted();
    } catch (error) {
      _log('Permission check failed: $error');
      return false;
    }
  }

  Future<bool> requestPermission() async {
    if (!Platform.isAndroid) return false;
    try {
      return await nls.NotificationListenerService.requestPermission();
    } catch (error) {
      _log('Permission request failed: $error');
      return false;
    }
  }

  Future<void> start({
    required bool autoAnalyzeNotifications,
    required Set<String> monitoredPackages,
  }) async {
    if (!Platform.isAndroid) {
      _log('start skipped reason=not_android');
      return;
    }

    await stop();

    final granted = await hasPermission();
    _log(
      'start permissionGranted=$granted autoAnalyze=$autoAnalyzeNotifications monitoredCount=${monitoredPackages.length}',
    );
    if (!granted) {
      _log('start skipped reason=notification_listener_permission_denied');
      return;
    }

    try {
      await ApgLocalNotificationService.configureMonitoredPackages(
        monitoredPackages,
      );
      _subscription = nls.NotificationListenerService.notificationsStream
          .listen(
            (dynamic event) async {
              await _handleEvent(
                event,
                autoAnalyzeNotifications: autoAnalyzeNotifications,
                monitoredPackages: monitoredPackages,
              );
            },
            onError: (Object error, StackTrace stackTrace) {
              _log('Notification stream error: $error');
            },
            cancelOnError: false,
          );
    } catch (error) {
      _log('Starting listener failed: $error');
      await stop();
    }
  }

  Future<void> _handleEvent(
    dynamic event, {
    required bool autoAnalyzeNotifications,
    required Set<String> monitoredPackages,
  }) async {
    try {
      if (event == null) {
        _log('event skipped reason=null_event');
        return;
      }
      if ((event.hasRemoved ?? false) == true) {
        _log('event skipped reason=removed_event');
        return;
      }

      final packageName = '${event.packageName ?? ''}'.trim();
      final title = '${event.title ?? ''}'.trim();
      final content = '${event.content ?? ''}'.trim();
      final notificationId = event.id is int
          ? event.id as int
          : int.tryParse('${event.id}');

      if (packageName.isEmpty) {
        _log('event skipped reason=empty_package');
        return;
      }
      if (!AppConfig.shouldMonitor(packageName, monitoredPackages)) {
        _log('event skipped reason=unmonitored package=$packageName');
        return;
      }
      if (title.isEmpty && content.isEmpty) {
        _log(
          'event skipped reason=empty_text package=$packageName id=$notificationId',
        );
        return;
      }
      _log(
        'captured package=$packageName id=$notificationId titleLen=${title.length} contentLen=${content.length}',
      );

      final dedupeKey = '$packageName|$notificationId|$title|$content';
      if (_recentKeys.contains(dedupeKey)) {
        _log(
          'event skipped reason=recent_capture_duplicate key=${dedupeKey.hashCode}',
        );
        return;
      }

      _recentKeys.add(dedupeKey);
      if (_recentKeys.length > 250) {
        _recentKeys.remove(_recentKeys.first);
      }

      final rawCombinedText = [
        title,
        content,
      ].where((e) => e.isNotEmpty).join('\n');
      _log(
        'combinedText length=${rawCombinedText.length} package=$packageName',
      );

      AnalysisResult? analysisResult;
      final draftItem = NotificationInboxItem.fromNotification(
        id: DateTime.now().microsecondsSinceEpoch.toString(),
        notificationId: notificationId,
        packageName: packageName,
        title: title,
        content: content,
        receivedAt: DateTime.now(),
        result: null,
      );

      _log('sourceApp=${draftItem.sourceAppName}');
      _log('sender=${draftItem.sender}');
      _log('channel=${draftItem.channel}');

      if (autoAnalyzeNotifications) {
        try {
          final senderForAnalysis = draftItem.sender == 'غير معروف'
              ? ''
              : draftItem.sender;
          final isKnownContact =
              await ApgLocalNotificationService.isKnownContact(
                senderForAnalysis,
              );
          analysisResult = await const ApgApiService().analyze(
            sender: senderForAnalysis,
            rawText: rawCombinedText,
            url: draftItem.detectedUrl,
            channel: draftItem.analysisChannel,
            packageName: packageName,
            sourceApp: draftItem.sourceAppName,
            isKnownContact: isKnownContact,
            senderTrust: isKnownContact == true
                ? 'known'
                : isKnownContact == false
                ? 'unknown'
                : 'unknown',
          );
          _log(
            'analysisResult finalLabel=${analysisResult.finalLabel} '
            'finalScore=${analysisResult.finalScore} qualifies=${_qualifiesForThreatNotification(analysisResult.finalLabel)}',
          );
        } catch (error) {
          _log('Auto analysis failed: $error');
          analysisResult = null;
        }
      } else {
        _log('analysis skipped reason=auto_analyze_disabled');
      }

      final inboxItem = NotificationInboxItem.fromNotification(
        id: draftItem.id,
        notificationId: notificationId,
        packageName: packageName,
        title: title,
        content: content,
        receivedAt: DateTime.now(),
        result: analysisResult,
      );

      onNewItem(inboxItem);
      _log(
        'showForNotification dispatch hasResult=${inboxItem.result != null} '
        'label=${inboxItem.result?.finalLabel} score=${inboxItem.result?.finalScore}',
      );
      await ApgLocalNotificationService.showForNotification(inboxItem);
    } catch (error) {
      _log('Notification event ignored after error: $error');
    }
  }

  Future<void> stop() async {
    try {
      await _subscription?.cancel();
    } catch (error) {
      _log('Stop listener failed: $error');
    }
    _subscription = null;
  }

  Future<void> dispose() async {
    await stop();
  }

  static void _log(String message) {
    debugPrint('APG_MONITOR_DEBUG $message');
  }

  static bool _qualifiesForThreatNotification(String label) {
    switch (label.trim().toLowerCase()) {
      case 'safe':
      case 'legit':
      case 'benign':
      case 'low_risk':
      case 'low-risk':
        return false;
      default:
        return true;
    }
  }
}
