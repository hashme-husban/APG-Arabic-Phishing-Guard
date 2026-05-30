import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../models/notification_inbox_item.dart';
import '../services/apg_local_notification_service.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/page_intro_header.dart';
import '../widgets/apg_ui.dart';
import 'result_details_screen.dart';
import 'monitored_apps_screen.dart';
import '../widgets/motion.dart';

class MonitoringScreen extends StatefulWidget {
  final List<NotificationInboxItem> notifications;
  final List<AnalysisHistoryItem> history;
  final bool notificationAccessGranted;
  final bool autoAnalyzeNotifications;
  final Future<void> Function() onRequestNotificationAccess;
  final Future<void> Function(bool) onToggleAutoAnalyzeNotifications;
  final VoidCallback onOpenSettings;
  final Set<String> monitoredPackages;
  final Future<void> Function(String packageName, bool enabled)
  onToggleMonitoredPackage;
  final Future<void> Function() onResetMonitoredPackages;

  const MonitoringScreen({
    super.key,
    required this.notifications,
    required this.history,
    required this.notificationAccessGranted,
    required this.autoAnalyzeNotifications,
    required this.onRequestNotificationAccess,
    required this.onToggleAutoAnalyzeNotifications,
    required this.onOpenSettings,
    required this.monitoredPackages,
    required this.onToggleMonitoredPackage,
    required this.onResetMonitoredPackages,
  });

  @override
  State<MonitoringScreen> createState() => _MonitoringScreenState();
}

class _MonitoringScreenState extends State<MonitoringScreen> {
  String _filter = 'all';
  bool _isSendingTestNotification = false;
  bool _isTogglingAutoAnalyze = false;

  List<NotificationInboxItem> get _analyzed =>
      widget.notifications.where((item) => item.result != null).toList();

  String _appName(NotificationInboxItem item) => item.sourceAppName;

  List<NotificationInboxItem> get _filtered {
    if (_filter == 'all') return _analyzed;
    return _analyzed.where((item) {
      final name = _appName(item).toLowerCase();
      if (_filter == 'sms') {
        return name.contains('sms') ||
            item.packageName.contains('messaging') ||
            item.packageName.contains('mms');
      }
      if (_filter == 'whatsapp') return name.contains('whatsapp');
      if (_filter == 'gmail') return name.contains('gmail');
      return !name.contains('whatsapp') &&
          !name.contains('gmail') &&
          !name.contains('sms');
    }).toList();
  }

  int get _safeCount => widget.history.where((item) {
    final label = item.result.finalLabel.toLowerCase();
    return label == 'safe' || label == 'legit' || label == 'benign';
  }).length;

  int get _suspiciousCount => widget.history.where(_isSuspicious).length;

  int get _dangerousCount => widget.history.where(_isDangerous).length;

  bool _isDangerous(AnalysisHistoryItem item) {
    final label = item.result.finalLabel.toLowerCase();
    return label == 'phishing' ||
        label == 'dangerous' ||
        label == 'high_risk' ||
        label == 'malicious';
  }

  bool _isSuspicious(AnalysisHistoryItem item) =>
      item.result.finalLabel.toLowerCase() == 'suspicious';

  List<AnalysisHistoryItem> get _recentAlerts => widget.history
      .where((item) => _isDangerous(item) || _isSuspicious(item))
      .toList();

  DateTime? get _lastCheckTime {
    final times = <DateTime>[
      ...widget.history.map((item) => item.createdAt),
      ..._analyzed.map((item) => item.receivedAt),
    ]..sort((a, b) => b.compareTo(a));
    return times.isEmpty ? null : times.first;
  }

  Color get _protectionColor {
    if (!widget.notificationAccessGranted) return AppTokens.warning;
    if (_recentAlerts.any(_isDangerous)) return AppTokens.danger;
    if (_recentAlerts.isNotEmpty) return AppTokens.warning;
    return AppTokens.success;
  }

  void _snack(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _sendTestNotification() async {
    if (_isSendingTestNotification) return;
    setState(() => _isSendingTestNotification = true);
    try {
      debugPrint('APG_NOTIFY_DEBUG ui_test_button_tapped');
      var granted =
          await ApgLocalNotificationService.hasPostNotificationsPermission();
      debugPrint('APG_NOTIFY_DEBUG ui_permission_before=$granted');
      if (!granted) {
        await ApgLocalNotificationService.requestPostNotificationsPermission();
        await Future<void>.delayed(const Duration(milliseconds: 700));
        granted =
            await ApgLocalNotificationService.hasPostNotificationsPermission();
        debugPrint('APG_NOTIFY_DEBUG ui_permission_after_request=$granted');
      }
      if (!granted) {
        _snack('فعّل إشعارات APG من إعدادات النظام.');
        return;
      }
      await ApgLocalNotificationService.showDebugTestNotification();
      _snack('تم إرسال اختبار إشعار APG.');
    } catch (error) {
      debugPrint('APG_NOTIFY_DEBUG ui_test_button_error=$error');
      _snack('تعذر إرسال اختبار الإشعار.');
    } finally {
      if (mounted) setState(() => _isSendingTestNotification = false);
    }
  }

  Future<void> _toggleAutoAnalyze() async {
    if (_isTogglingAutoAnalyze) return;
    if (!widget.notificationAccessGranted) {
      _snack('فعّل صلاحية الإشعارات أولاً');
      await widget.onRequestNotificationAccess();
      return;
    }
    setState(() => _isTogglingAutoAnalyze = true);
    try {
      final next = !widget.autoAnalyzeNotifications;
      debugPrint('APG_MONITOR_DEBUG ui_toggle_auto_analyze next=$next');
      await widget.onToggleAutoAnalyzeNotifications(next);
      if (!mounted) return;
      _snack(next ? 'التحليل التلقائي مفعّل' : 'التحليل التلقائي متوقف');
    } catch (error) {
      debugPrint('APG_MONITOR_DEBUG ui_toggle_auto_analyze_error=$error');
      if (mounted) _snack('تعذر تحديث التحليل التلقائي.');
    } finally {
      if (mounted) setState(() => _isTogglingAutoAnalyze = false);
    }
  }

  Widget _statusCard(BuildContext context) {
    final active = widget.notificationAccessGranted;
    final color = _protectionColor;
    final l10n = context.l10n;
    final lastCheck = _lastCheckTime == null
        ? l10n.noCheckRecordedYet
        : l10n.lastCheckLabel(
            TextMapper.formatDateTime(context, _lastCheckTime!),
          );
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      border: Border.all(color: color.withValues(alpha: 0.24)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(
                  active
                      ? Icons.shield_rounded
                      : Icons.notifications_off_rounded,
                  color: color,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      active
                          ? l10n.readyForProtection
                          : l10n.awaitingPermission,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: color,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      active
                          ? l10n.autoMonitoringActive
                          : l10n.enableAutoMonitorHint,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTokens.mutedText(context),
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      lastCheck,
                      textAlign: TextAlign.right,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                        height: 1.35,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusBadge(
                label: active ? l10n.runningInBackground : l10n.setupRequired,
                color: color,
                icon: active ? Icons.check_circle_rounded : Icons.lock_rounded,
              ),
              StatusBadge(
                label: widget.autoAnalyzeNotifications
                    ? l10n.autoAnalyzeOn
                    : l10n.autoAnalyzeOff,
                color: widget.autoAnalyzeNotifications
                    ? AppTokens.brandCyan
                    : AppTokens.neutral,
                icon: Icons.auto_awesome_rounded,
              ),
            ],
          ),
          const SizedBox(height: 14),
          PrimaryButton(
            label: !active
                ? 'فعّل صلاحية الإشعارات أولاً'
                : _isTogglingAutoAnalyze
                ? 'جارٍ التحديث...'
                : widget.autoAnalyzeNotifications
                ? 'إيقاف التحليل التلقائي'
                : 'تفعيل التحليل التلقائي',
            icon: !active
                ? Icons.lock_open_rounded
                : widget.autoAnalyzeNotifications
                ? Icons.pause_rounded
                : Icons.play_arrow_rounded,
            onPressed: _isTogglingAutoAnalyze ? null : _toggleAutoAnalyze,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: PrimaryButton(
                  label: active
                      ? l10n.managePermission
                      : l10n.activatePermission,
                  icon: Icons.settings_rounded,
                  onPressed: () async {
                    await widget.onRequestNotificationAccess();
                    if (mounted) _snack(l10n.monitoringStatusUpdated);
                  },
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: SecondaryButton(
                  label: l10n.manageApps,
                  icon: Icons.apps_rounded,
                  onPressed: _openMonitoredApps,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SecondaryButton(
            label: _isSendingTestNotification
                ? 'جارٍ إرسال الاختبار...'
                : 'اختبار إشعار APG',
            icon: Icons.notification_add_rounded,
            onPressed: _isSendingTestNotification
                ? null
                : _sendTestNotification,
          ),
        ],
      ),
    );
  }

  void _openMonitoredApps() {
    Navigator.of(context).push(
      apgSlideFadeRoute(
        MonitoredAppsScreen(
          monitoredPackages: widget.monitoredPackages,
          onTogglePackage: widget.onToggleMonitoredPackage,
          onResetPackages: widget.onResetMonitoredPackages,
          notificationAccessGranted: widget.notificationAccessGranted,
        ),
      ),
    );
  }

  Widget _valueCard(BuildContext context) {
    final l10n = context.l10n;
    final points = [
      l10n.monitoringHowPoint1,
      l10n.monitoringHowPoint2,
      l10n.monitoringHowPoint3,
    ];
    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: l10n.howMonitoringWorks,
            icon: Icons.security_rounded,
          ),
          const SizedBox(height: 12),
          ...points.map(
            (point) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.check_circle_rounded,
                    color: AppTokens.brandCyan,
                    size: 17,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      point,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTokens.mutedText(context),
                        height: 1.45,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _stats(BuildContext context) {
    final l10n = context.l10n;
    final stats = [
      (l10n.safeCountLabel, _safeCount, AppTokens.success),
      (l10n.needsVerification, _suspiciousCount, AppTokens.warning),
      (l10n.highRisk, _dangerousCount, AppTokens.danger),
    ];
    return AppSurfaceCard(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
      child: Row(
        children: stats
            .map(
              (s) => Expanded(
                child: Column(
                  children: [
                    Text(
                      '${s.$2}',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: s.$3,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      s.$1,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppTokens.mutedText(context),
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _filters() {
    final l10n = context.l10n;
    final filters = [
      ('all', l10n.all),
      ('sms', 'SMS'),
      ('whatsapp', 'WhatsApp'),
      ('gmail', 'Gmail'),
      ('other', l10n.filterOther),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: filters
            .map(
              (f) => Padding(
                padding: const EdgeInsetsDirectional.only(end: 8),
                child: ChoiceChip(
                  label: Text(f.$2),
                  selected: _filter == f.$1,
                  onSelected: (_) => setState(() => _filter = f.$1),
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _notificationCard(NotificationInboxItem item) {
    final result = item.result!;
    final color = TextMapper.riskColor(result.finalLabel);
    final historyItem = item.toHistoryItem();
    return AppSurfaceCard(
      padding: const EdgeInsets.all(14),
      border: Border.all(color: color.withValues(alpha: 0.20)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  Icons.notifications_active_rounded,
                  color: color,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _appName(item),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      TextMapper.formatDateTime(context, item.receivedAt),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              StatusBadge(
                label: TextMapper.label(context, result.finalLabel),
                color: color,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            item.previewText.isEmpty
                ? context.l10n.noTextAvailable
                : item.previewText,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              height: 1.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                context.l10n.riskScoreLabel(result.finalScore),
                style: TextStyle(color: color, fontWeight: FontWeight.w900),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: historyItem == null
                    ? null
                    : () {
                        if (kDebugMode) {
                          debugPrint(
                            'APG_SCORE_TRACE screen=monitoring itemId=${historyItem.id} '
                            'analysisId=${historyItem.result.remoteId} '
                            'score=${historyItem.result.finalScore}',
                          );
                        }
                        Navigator.of(context).push(
                          apgSlideFadeRoute(
                            ResultDetailsScreen(item: historyItem),
                          ),
                        );
                      },
                icon: const Icon(Icons.open_in_new_rounded, size: 17),
                label: Text(context.l10n.viewDetailsLabel),
              ),
            ],
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final items = _filtered;
    return AppBackground(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            20,
            16,
            20,
            AppTokens.bottomNavContentPadding,
          ),
          children: [
            PageIntroHeader(
              icon: Icons.notifications_active_rounded,
              title: context.l10n.monitoring,
              subtitle: context.l10n.monitoringSubtitle,
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              beginOffset: const Offset(0, 10),
              child: _statusCard(context),
            ),
            const SizedBox(height: 14),
            FadeSlideIn(
              delay: const Duration(milliseconds: 80),
              child: _stats(context),
            ),
            const SizedBox(height: 14),
            FadeSlideIn(
              delay: const Duration(milliseconds: 130),
              child: _valueCard(context),
            ),
            const SizedBox(height: 14),
            _filters(),
            const SizedBox(height: 12),
            if (items.isEmpty)
              EmptyState(
                title: widget.notificationAccessGranted
                    ? context.l10n.monitoringReadyTitle
                    : context.l10n.monitoringAwaitingPermissionBadge,
                subtitle: widget.notificationAccessGranted
                    ? context.l10n.notificationsWillAppear
                    : context.l10n.enableAutoMonitorHint,
                icon: Icons.notifications_none_rounded,
                action: PrimaryButton(
                  label: widget.notificationAccessGranted
                      ? context.l10n.manageApps
                      : context.l10n.activateMonitoring,
                  icon: Icons.notifications_active_rounded,
                  onPressed: () {
                    if (widget.notificationAccessGranted) {
                      _openMonitoredApps();
                    } else {
                      widget.onRequestNotificationAccess();
                    }
                  },
                ),
              )
            else
              ...items.asMap().entries.map(
                (entry) => StaggeredItem(
                  key: ValueKey(entry.value.id),
                  index: entry.key > 5 ? 5 : entry.key,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _notificationCard(entry.value),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
