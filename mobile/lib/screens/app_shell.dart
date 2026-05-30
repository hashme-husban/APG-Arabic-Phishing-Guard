import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config/app_config.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../models/notification_inbox_item.dart';
import '../services/apg_api_service.dart';
import '../services/apg_local_notification_service.dart';
import '../services/auth_service.dart';
import '../services/local_storage_service.dart';
import '../services/notification_inbox_service.dart';
import '../theme/app_tokens.dart';
import '../widgets/apg_logo.dart';
import '../widgets/motion.dart';
import 'analyze_screen.dart';
import 'history_screen.dart';
import 'home_screen.dart';
import 'monitoring_screen.dart';
import 'result_details_screen.dart';
import 'settings_screen.dart';

class AppShell extends StatefulWidget {
  final bool isDarkMode;
  final ValueChanged<bool> onToggleDarkMode;
  final Locale currentLocale;
  final ValueChanged<Locale> onChangeLocale;
  final String accentThemeKey;
  final ValueChanged<String> onChangeAccentTheme;
  final Future<void> Function() onLogout;

  const AppShell({
    super.key,
    required this.isDarkMode,
    required this.onToggleDarkMode,
    required this.currentLocale,
    required this.onChangeLocale,
    required this.accentThemeKey,
    required this.onChangeAccentTheme,
    required this.onLogout,
  });

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> with WidgetsBindingObserver {
  int _currentIndex = 0;
  int _previousIndex = 0;

  List<AnalysisHistoryItem> _history = [];
  List<NotificationInboxItem> _notifications = [];

  bool _saveHistoryEnabled = true;
  bool _autoAnalyzeNotifications = false;
  bool _notificationAccessGranted = false;
  bool _isCheckingServer = false;
  bool _isSyncingRemoteHistory = false;
  DateTime? _lastBackPressedAt;

  ApiConnectionSnapshot _apiConnection = ApiConnectionSnapshot(
    isConnected: false,
    activeBaseUrl: null,
    lastTriedBaseUrl: AppConfig.apiBaseUrl,
    candidateBaseUrls: AppConfig.apiBaseCandidates(),
  );

  late Set<String> _monitoredPackages;
  late final NotificationInboxService _notificationInboxService;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    _saveHistoryEnabled = LocalStorageService.instance.getSaveHistoryEnabled();
    _autoAnalyzeNotifications = LocalStorageService.instance
        .getAutoAnalyzeNotifications();
    _monitoredPackages = LocalStorageService.instance.getMonitoredPackages();

    _history = LocalStorageService.instance.loadHistory();
    _notifications = LocalStorageService.instance.loadNotifications();

    _notificationInboxService = NotificationInboxService(
      onNewItem: _handleIncomingNotification,
    );

    if (AppConfig.checkServerOnStartup) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _refreshApiConnection();
      });
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (LocalStorageService.instance.localDataWasRebuilt && mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(context.l10n.localDataUpdated)));
      }
      ApgLocalNotificationService.requestPostNotificationsPermission();
      _bootstrapNotificationListener(startListener: true);
      _handleLocalNotificationLaunch();
      _syncHistoryFromServer();
    });
  }

  Future<void> _handleLocalNotificationLaunch() async {
    final payload = await ApgLocalNotificationService.getLaunchPayload();
    if (!mounted || payload == null || !payload.hasTarget) return;

    setState(() {
      _previousIndex = _currentIndex;
      _currentIndex = 2;
    });

    await ApgLocalNotificationService.clearLaunchPayload();
    if (!mounted) return;

    NotificationInboxItem? target;
    for (final item in _notifications) {
      final notificationId = payload.notificationId?.trim();
      final analysisId = payload.analysisId?.trim();
      final matches =
          (notificationId != null &&
              notificationId.isNotEmpty &&
              (item.id == notificationId ||
                  item.notificationId?.toString() == notificationId ||
                  '${item.packageName}|${item.notificationId}' ==
                      notificationId)) ||
          (analysisId != null &&
              analysisId.isNotEmpty &&
              (item.id == analysisId || item.result?.remoteId == analysisId));
      if (matches) {
        target = item;
        break;
      }
    }

    final historyItem = target?.toHistoryItem();
    if (historyItem == null) return;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ResultDetailsScreen(item: historyItem),
        ),
      );
    });
  }

  Future<void> _bootstrapNotificationListener({
    bool startListener = true,
  }) async {
    try {
      final granted = await _notificationInboxService.hasPermission();

      if (!mounted) return;

      setState(() {
        _notificationAccessGranted = granted;
      });

      if (granted && startListener) {
        await _restartNotificationListener();
      }
    } catch (error) {
      debugPrint('[APG NOTIFICATION BOOTSTRAP ERROR] $error');
      if (!mounted) return;
      setState(() {
        _notificationAccessGranted = false;
      });
    }
  }

  Future<void> _refreshApiConnection({bool showFeedback = false}) async {
    if (mounted) {
      setState(() {
        _isCheckingServer = true;
      });
    }

    ApiConnectionSnapshot connection;
    try {
      connection = await const ApgApiService().checkConnection(
        forceRefresh: true,
      );
    } catch (error) {
      debugPrint('[APG SERVER CHECK ERROR] $error');
      connection = ApiConnectionSnapshot(
        isConnected: false,
        activeBaseUrl: null,
        lastTriedBaseUrl: AppConfig.apiBaseUrl,
        candidateBaseUrls: AppConfig.apiBaseCandidates(),
      );
    }

    if (!mounted) return;

    setState(() {
      _apiConnection = connection;
      _isCheckingServer = false;
    });

    if (showFeedback) {
      final l10n = context.l10n;
      final message = connection.isConnected
          ? l10n.serverConnectionOnline(_serverAddress)
          : l10n.serverConnectionOffline(_serverAddress);
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    }
  }

  String get _serverAddress =>
      _apiConnection.activeBaseUrl ??
      AppConfig.normalizeBaseUrl(AppConfig.apiBaseUrl);

  Future<void> _restartNotificationListener() async {
    try {
      await ApgLocalNotificationService.configureMonitoredPackages(
        _monitoredPackages,
      );
      await _notificationInboxService.start(
        autoAnalyzeNotifications: _autoAnalyzeNotifications,
        monitoredPackages: _monitoredPackages,
      );
    } catch (error) {
      debugPrint('[APG NOTIFICATION LISTENER ERROR] $error');
    }
  }

  void _handleIncomingNotification(NotificationInboxItem item) {
    if (!mounted) return;
    setState(() {
      _notifications.insert(0, item);
    });

    LocalStorageService.instance.saveNotificationItem(item);

    final historyItem = item.toHistoryItem();
    // Save to history but do NOT trigger an immediate server sync —
    // the backend needs time to index the analysis before a sync would see it.
    if (historyItem != null && _saveHistoryEnabled) {
      _saveAnalysis(historyItem, triggerSync: false);
    }
  }

  void _goToTab(int index) {
    if (index == _currentIndex) return;
    HapticFeedback.selectionClick();
    setState(() {
      _previousIndex = _currentIndex;
      _currentIndex = index;
    });
    if (index == 0 || index == 3) {
      _syncHistoryFromServer();
    }
    if (index == 4 && !_isCheckingServer) {
      _refreshApiConnection();
    }
  }

  Future<void> _syncHistoryFromServer({bool showFeedback = false}) async {
    final token = LocalStorageService.instance.getSessionToken();
    if (token == null ||
        token.isEmpty ||
        token.startsWith('demo-') ||
        _isSyncingRemoteHistory ||
        !mounted) {
      return;
    }
    setState(() => _isSyncingRemoteHistory = true);
    try {
      await const AuthService().currentSession(token);
      final api = const ApgApiService();
      final connection = await api.checkConnection();
      if (!connection.isConnected) return;
      final remote = await api.fetchHistory(limit: 50);
      if (!mounted) return;
      final localById = {
        for (final item in _history) item.id: item,
        for (final item in _history)
          if (item.result.remoteId.trim().isNotEmpty)
            item.result.remoteId: item,
      };
      final filtered = remote
          .where(
            (item) =>
                !LocalStorageService.instance.isHistoryItemDeleted(item.id) &&
                !LocalStorageService.instance.isHistoryItemDeleted(
                  item.result.remoteId,
                ),
          )
          .map(
            (item) => _mergeHistoryItem(
              localById[item.id] ?? localById[item.result.remoteId],
              item,
            ),
          )
          .toList();

      // Preserve any local-only items that are not yet on the server
      // (e.g. notification analysis results saved just before this sync).
      final remoteIds = {
        for (final item in filtered) item.id,
        for (final item in filtered)
          if (item.result.remoteId.trim().isNotEmpty) item.result.remoteId,
      };
      final localOnly = _history
          .where(
            (item) =>
                !remoteIds.contains(item.id) &&
                !remoteIds.contains(item.result.remoteId) &&
                !LocalStorageService.instance.isHistoryItemDeleted(item.id),
          )
          .toList();
      final merged = [...filtered, ...localOnly]
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

      setState(() {
        _history = merged;
      });
      await LocalStorageService.instance.clearHistory();
      for (final item in merged) {
        await LocalStorageService.instance.saveHistoryItem(item);
      }
      if (showFeedback && mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(content: Text(context.l10n.historyUpdatedFromServer)),
          );
      }
    } on SessionExpiredException catch (error) {
      await _handleSessionExpired(error.message);
    } catch (error) {
      debugPrint('[APG HISTORY SYNC ERROR] $error');
    } finally {
      if (mounted) setState(() => _isSyncingRemoteHistory = false);
    }
  }

  void _saveAnalysis(AnalysisHistoryItem item, {bool triggerSync = true}) {
    if (!_saveHistoryEnabled) return;

    setState(() {
      _history.removeWhere((old) => old.id == item.id);
      _history.insert(0, item);
    });

    LocalStorageService.instance.saveHistoryItem(item);

    if (triggerSync && item.sourceTrust == 'server') {
      Future<void>.delayed(const Duration(milliseconds: 450), () {
        if (mounted) _syncHistoryFromServer();
      });
    }
  }

  // Called from AnalyzeScreen — save result and navigate to details (no overlay).
  void _handleAnalysisSaved(AnalysisHistoryItem item) {
    _saveAnalysis(item);
  }

  AnalysisHistoryItem _mergeHistoryItem(
    AnalysisHistoryItem? local,
    AnalysisHistoryItem remote,
  ) {
    if (local == null) return remote;
    return AnalysisHistoryItem(
      id: remote.id,
      sender: remote.sender,
      rawText: remote.rawText,
      url: remote.url,
      result: remote.result.copyWith(
        claimedEntity: remote.result.claimedEntity.trim().isNotEmpty
            ? remote.result.claimedEntity
            : local.claimedEntityName,
        senderEntity: remote.result.senderEntity.trim().isNotEmpty
            ? remote.result.senderEntity
            : local.senderEntityName,
        domainEntity: remote.result.domainEntity.trim().isNotEmpty
            ? remote.result.domainEntity
            : local.domainEntityName,
        entityConflict: remote.result.entityConflict || local.entityConflict,
        messageIntent: remote.result.messageIntent ?? local.messageIntent,
        intentConfidence:
            remote.result.intentConfidence ?? local.intentConfidence,
        modality: remote.result.modality ?? local.modality,
        matchedSignals: remote.result.matchedSignals.isNotEmpty
            ? remote.result.matchedSignals
            : local.matchedSignals,
      ),
      createdAt: remote.createdAt,
      channel: remote.channel,
      claimedEntityInput: remote.claimedEntityInput,
      claimedEntityName: remote.claimedEntityName.isNotEmpty
          ? remote.claimedEntityName
          : local.claimedEntityName,
      senderEntityName: remote.senderEntityName.isNotEmpty
          ? remote.senderEntityName
          : local.senderEntityName,
      domainEntityName: remote.domainEntityName.isNotEmpty
          ? remote.domainEntityName
          : local.domainEntityName,
      entityConflict: remote.entityConflict || local.entityConflict,
      messageIntent: remote.messageIntent ?? local.messageIntent,
      intentConfidence: remote.intentConfidence ?? local.intentConfidence,
      modality: remote.modality ?? local.modality,
      matchedSignals: remote.matchedSignals.isNotEmpty
          ? remote.matchedSignals
          : local.matchedSignals,
      selectedIndicators: remote.selectedIndicators,
      sourceTrust: remote.sourceTrust,
      linkOpened: remote.linkOpened,
      notes: remote.notes,
    );
  }

  void _removeAnalysis(String id) {
    AnalysisHistoryItem? removed;
    for (final item in _history) {
      if (item.id == id || item.result.remoteId == id) {
        removed = item;
        break;
      }
    }
    setState(() {
      _history.removeWhere(
        (item) => item.id == id || item.result.remoteId == id,
      );
    });

    if (removed == null) {
      LocalStorageService.instance.deleteHistoryItem(id);
      return;
    }

    LocalStorageService.instance.markHistoryItemDeleted(removed);
    final serverId = removed.result.remoteId.trim().isNotEmpty
        ? removed.result.remoteId.trim()
        : removed.id.trim();
    const ApgApiService().deleteHistoryItem(serverId);
  }

  Future<void> _clearAllHistory() async {
    final itemsToDelete = List<AnalysisHistoryItem>.from(_history);
    setState(() {
      _history = [];
    });

    for (final item in itemsToDelete) {
      await LocalStorageService.instance.markHistoryItemDeleted(item);
    }
    await LocalStorageService.instance.clearHistory();
    for (final item in itemsToDelete) {
      final serverId = item.result.remoteId.trim().isNotEmpty
          ? item.result.remoteId.trim()
          : item.id.trim();
      const ApgApiService().deleteHistoryItem(serverId);
    }
  }

  Future<void> _clearAllNotifications() async {
    setState(() {
      _notifications = [];
    });

    await LocalStorageService.instance.clearNotifications();
  }

  Future<void> _logout() async {
    await _notificationInboxService.stop();
    if (mounted) {
      setState(() {
        _history = [];
        _notifications = [];
      });
    }
    await const AuthService().logout();
    await widget.onLogout();
  }

  Future<void> _handleSessionExpired(String message) async {
    await _notificationInboxService.stop();
    if (!mounted) return;
    setState(() {
      _history = [];
      _notifications = [];
    });
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
    await widget.onLogout();
  }

  void _setSaveHistoryEnabled(bool value) {
    setState(() {
      _saveHistoryEnabled = value;
    });

    LocalStorageService.instance.setSaveHistoryEnabled(value);
  }

  Future<void> _setAutoAnalyzeNotifications(bool value) async {
    debugPrint('APG_MONITOR_DEBUG set_auto_analyze value=$value');
    setState(() {
      _autoAnalyzeNotifications = value;
    });

    await LocalStorageService.instance.setAutoAnalyzeNotifications(value);
    if (!mounted) return;

    if (_notificationAccessGranted) {
      await _restartNotificationListener();
    }
  }

  Future<void> _setMonitoredPackageEnabled(
    String packageName,
    bool enabled,
  ) async {
    final next = {..._monitoredPackages};

    if (enabled) {
      next.add(packageName);
    } else {
      next.remove(packageName);
    }

    setState(() {
      _monitoredPackages = next;
    });

    await LocalStorageService.instance.setMonitoredPackages(next);
    if (!mounted) return;

    if (_notificationAccessGranted) {
      await _restartNotificationListener();
    }
  }

  Future<void> _resetMonitoredPackages() async {
    final defaults = AppConfig.defaultMonitoredPackages();

    setState(() {
      _monitoredPackages = defaults;
    });

    await LocalStorageService.instance.setMonitoredPackages(defaults);
    if (!mounted) return;

    if (_notificationAccessGranted) {
      await _restartNotificationListener();
    }
  }

  Future<void> _requestNotificationAccess() async {
    try {
      await ApgLocalNotificationService.requestPostNotificationsPermission();
      await _notificationInboxService.requestPermission();
      await Future.delayed(const Duration(milliseconds: 500));

      final granted = await _notificationInboxService.hasPermission();

      if (!mounted) return;

      setState(() {
        _notificationAccessGranted = granted;
      });

      if (granted) {
        await _restartNotificationListener();
      }
    } catch (error) {
      debugPrint('[APG NOTIFICATION PERMISSION ERROR] $error');
      if (!mounted) return;
      setState(() {
        _notificationAccessGranted = false;
      });
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(content: Text(context.l10n.notificationPermUnavailable)),
        );
    }
  }

  String _titleForIndex(BuildContext context, int index) {
    final l10n = context.l10n;
    switch (index) {
      case 0:
        return l10n.home;
      case 1:
        return l10n.analyze;
      case 2:
        return l10n.monitoring;
      case 3:
        return l10n.history;
      case 4:
        return l10n.settings;
      default:
        return l10n.appTitle;
    }
  }

  Future<void> _handleBackPressed() async {
    final navigator = Navigator.of(context);
    if (navigator.canPop()) {
      navigator.pop();
      return;
    }

    if (_currentIndex != 0) {
      _goToTab(0);
      return;
    }

    final now = DateTime.now();
    final shouldExit =
        _lastBackPressedAt != null &&
        now.difference(_lastBackPressedAt!) < const Duration(seconds: 2);
    if (shouldExit) {
      SystemNavigator.pop();
      return;
    }

    _lastBackPressedAt = now;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(context.l10n.pressBackToExit),
          duration: const Duration(seconds: 2),
        ),
      );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _notificationInboxService.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _handleLocalNotificationLaunch();
      _bootstrapNotificationListener(startListener: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    final screens = [
      HomeScreen(
        history: _history,
        onStartAnalyze: () => _goToTab(1),
        onOpenHistory: () => _goToTab(3),
        onDeleteHistoryItem: _removeAnalysis,
        notificationAccessGranted: _notificationAccessGranted,
        monitoredAppsCount: _monitoredPackages.length,
      ),
      AnalyzeScreen(onAnalysisSaved: _handleAnalysisSaved),
      MonitoringScreen(
        notifications: _notifications,
        history: _history,
        notificationAccessGranted: _notificationAccessGranted,
        autoAnalyzeNotifications: _autoAnalyzeNotifications,
        onRequestNotificationAccess: _requestNotificationAccess,
        onToggleAutoAnalyzeNotifications: _setAutoAnalyzeNotifications,
        onOpenSettings: () => _goToTab(4),
        monitoredPackages: _monitoredPackages,
        onToggleMonitoredPackage: _setMonitoredPackageEnabled,
        onResetMonitoredPackages: _resetMonitoredPackages,
      ),
      HistoryScreen(
        items: _history,
        onDeleteHistoryItem: _removeAnalysis,
        onStartAnalyze: () => _goToTab(1),
        onRefresh: () => _syncHistoryFromServer(showFeedback: true),
        isRefreshing: _isSyncingRemoteHistory,
      ),
      SettingsScreen(
        isDarkMode: widget.isDarkMode,
        onToggleDarkMode: widget.onToggleDarkMode,
        currentLocale: widget.currentLocale,
        onChangeLocale: widget.onChangeLocale,
        accentThemeKey: widget.accentThemeKey,
        onChangeAccentTheme: widget.onChangeAccentTheme,
        saveHistoryEnabled: _saveHistoryEnabled,
        onToggleSaveHistory: _setSaveHistoryEnabled,
        autoAnalyzeNotifications: _autoAnalyzeNotifications,
        onToggleAutoAnalyzeNotifications: _setAutoAnalyzeNotifications,
        historyCount: _history.length,
        onClearAllHistory: _clearAllHistory,
        notificationAccessGranted: _notificationAccessGranted,
        onRequestNotificationAccess: _requestNotificationAccess,
        notificationCount: _notifications.length,
        onClearAllNotifications: _clearAllNotifications,
        monitoredPackages: _monitoredPackages,
        onToggleMonitoredPackage: _setMonitoredPackageEnabled,
        onResetMonitoredPackages: _resetMonitoredPackages,
        serverConnected: _apiConnection.isConnected,
        isCheckingServer: _isCheckingServer,
        serverAddress: _serverAddress,
        onRefreshServerConnection: () =>
            _refreshApiConnection(showFeedback: true),
        onLogout: _logout,
      ),
    ];

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        _handleBackPressed();
      },
      child: Scaffold(
        extendBody: false,
        appBar: AppBar(
          toolbarHeight: 54,
          titleSpacing: 12,
          title: AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            child: _TopTitle(
              key: ValueKey(_currentIndex),
              title: _currentIndex == 0
                  ? 'APG'
                  : _titleForIndex(context, _currentIndex),
              compact: _currentIndex != 0,
            ),
          ),
          actions: const [],
        ),
        body: _MotionIndexedStack(
          index: _currentIndex,
          previousIndex: _previousIndex,
          children: screens,
        ),
        bottomNavigationBar: _CyberBottomNav(
          currentIndex: _currentIndex,
          onTap: _goToTab,
          items: [
            _CyberNavItem(
              icon: Icons.dashboard_outlined,
              activeIcon: Icons.dashboard_rounded,
              label: l10n.home,
            ),
            _CyberNavItem(
              icon: Icons.search_outlined,
              activeIcon: Icons.search_rounded,
              label: l10n.analyze,
            ),
            _CyberNavItem(
              icon: Icons.notifications_none_rounded,
              activeIcon: Icons.notifications_active_rounded,
              label: l10n.monitoring,
            ),
            _CyberNavItem(
              icon: Icons.history_outlined,
              activeIcon: Icons.history_rounded,
              label: l10n.history,
            ),
            _CyberNavItem(
              icon: Icons.settings_outlined,
              activeIcon: Icons.settings_rounded,
              label: l10n.settings,
            ),
          ],
        ),
      ),
    );
  }
}

class _TopTitle extends StatelessWidget {
  final String title;
  final bool compact;

  const _TopTitle({super.key, required this.title, required this.compact});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        APGLogo(
          size: 46,
          glowOpacity: 0.14,
          paddingFraction: 0.02,
          showContainer: false,
        ),
        const SizedBox(width: 11),
        Text(
          title,
          style: Theme.of(context).appBarTheme.titleTextStyle?.copyWith(
            fontWeight: FontWeight.w900,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

class _CyberNavItem {
  final IconData icon;
  final IconData activeIcon;
  final String label;

  const _CyberNavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });
}

class _MotionIndexedStack extends StatefulWidget {
  final int index;
  final int previousIndex;
  final List<Widget> children;

  const _MotionIndexedStack({
    required this.index,
    required this.previousIndex,
    required this.children,
  });

  @override
  State<_MotionIndexedStack> createState() => _MotionIndexedStackState();
}

class _MotionIndexedStackState extends State<_MotionIndexedStack>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late Animation<double> _fade;
  late Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    );
    _configureAnimation();
    _controller.value = 1;
  }

  void _configureAnimation() {
    final movingForward = widget.index > widget.previousIndex;
    final beginDx = movingForward ? -0.070 : 0.070;
    _fade = CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic);
    _slide = Tween<Offset>(
      begin: Offset(beginDx, 0),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));
  }

  @override
  void didUpdateWidget(covariant _MotionIndexedStack oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.index != widget.index) {
      _configureAnimation();
      _controller.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fade,
      child: SlideTransition(
        position: _slide,
        child: IndexedStack(
          index: widget.index,
          children: List.generate(widget.children.length, (i) {
            return TickerMode(
              enabled: i == widget.index,
              child: widget.children[i],
            );
          }),
        ),
      ),
    );
  }
}

class _CyberBottomNav extends StatefulWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  final List<_CyberNavItem> items;

  const _CyberBottomNav({
    required this.currentIndex,
    required this.onTap,
    required this.items,
  });

  @override
  State<_CyberBottomNav> createState() => _CyberBottomNavState();
}

class _CyberBottomNavState extends State<_CyberBottomNav> {
  int? _poppedIndex;

  void _handleTap(int index) {
    setState(() => _poppedIndex = index);
    Future<void>.delayed(const Duration(milliseconds: 210), () {
      if (mounted && _poppedIndex == index) setState(() => _poppedIndex = null);
    });
    widget.onTap(index);
  }

  @override
  Widget build(BuildContext context) {
    final isDark = AppTokens.isDark(context);
    final background = isDark
        ? const Color(0xF2051724)
        : Colors.white.withValues(alpha: 0.98);
    final inactiveColor = isDark
        ? const Color(0xFFB6C4D6)
        : const Color(0xFF667085);
    final media = MediaQuery.of(context);

    return MediaQuery(
      data: media.copyWith(textScaler: const TextScaler.linear(1.0)),
      child: SafeArea(
        top: false,
        bottom: true,
        minimum: const EdgeInsets.fromLTRB(14, 0, 14, 10),
        child: Container(
          height: 70,
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: isDark
                  ? AppTokens.outlineDark.withValues(alpha: 0.78)
                  : AppTokens.outlineLight,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: isDark ? 0.30 : 0.09),
                blurRadius: 24,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final itemWidth = constraints.maxWidth / widget.items.length;
              final indicatorLeft =
                  (widget.items.length - 1 - widget.currentIndex) * itemWidth +
                  3;
              return Stack(
                children: [
                  AnimatedPositioned(
                    duration: const Duration(milliseconds: 310),
                    curve: Curves.easeOutCubic,
                    top: 6,
                    bottom: 6,
                    left: indicatorLeft,
                    width: itemWidth - 6,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            AppTokens.brand.withValues(alpha: 0.92),
                            AppTokens.brandAlt.withValues(alpha: 0.86),
                          ],
                          begin: Alignment.topRight,
                          end: Alignment.bottomLeft,
                        ),
                        borderRadius: BorderRadius.circular(
                          widget.currentIndex == 0 ||
                                  widget.currentIndex == widget.items.length - 1
                              ? 21
                              : 18,
                        ),
                        border: Border.all(
                          color: Colors.white.withValues(alpha: 0.14),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: AppTokens.brand.withValues(alpha: 0.22),
                            blurRadius: 22,
                            offset: const Offset(0, 9),
                          ),
                        ],
                      ),
                    ),
                  ),
                  Directionality(
                    textDirection: TextDirection.rtl,
                    child: Row(
                      children: List.generate(widget.items.length, (index) {
                        final item = widget.items[index];
                        final selected = index == widget.currentIndex;
                        final popped = _poppedIndex == index || selected;
                        return Expanded(
                          child: PressableScale(
                            onTap: () => _handleTap(index),
                            pressedScale: 0.96,
                            child: AnimatedScale(
                              duration: const Duration(milliseconds: 210),
                              curve: Curves.easeOutBack,
                              scale: popped ? 1.08 : 1,
                              child: Padding(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 3,
                                  vertical: 6,
                                ),
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 240),
                                  curve: Curves.easeOutCubic,
                                  height: 56,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 2,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(18),
                                  ),
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      AnimatedSwitcher(
                                        duration: const Duration(
                                          milliseconds: 180,
                                        ),
                                        switchInCurve: Curves.easeOutBack,
                                        transitionBuilder: (child, animation) =>
                                            ScaleTransition(
                                              scale: Tween<double>(
                                                begin: 0.86,
                                                end: 1,
                                              ).animate(animation),
                                              child: FadeTransition(
                                                opacity: animation,
                                                child: child,
                                              ),
                                            ),
                                        child: Icon(
                                          selected
                                              ? item.activeIcon
                                              : item.icon,
                                          key: ValueKey(
                                            '${item.label}-$selected',
                                          ),
                                          size: selected ? 22 : 20,
                                          color: selected
                                              ? Colors.white
                                              : inactiveColor,
                                        ),
                                      ),
                                      const SizedBox(height: 3),
                                      Flexible(
                                        child: AnimatedDefaultTextStyle(
                                          duration: const Duration(
                                            milliseconds: 220,
                                          ),
                                          curve: Curves.easeOutCubic,
                                          style: TextStyle(
                                            fontSize: 9.8,
                                            height: 1.0,
                                            fontWeight: selected
                                                ? FontWeight.w900
                                                : FontWeight.w700,
                                            color: selected
                                                ? Colors.white
                                                : inactiveColor,
                                          ),
                                          child: Text(
                                            item.label,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            textAlign: TextAlign.center,
                                            softWrap: false,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                        );
                      }),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
