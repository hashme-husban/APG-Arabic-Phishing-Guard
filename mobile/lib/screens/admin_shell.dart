import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../l10n/l10n_extensions.dart';
import '../services/admin_repository.dart';
import '../services/apg_api_service.dart';
import '../services/local_storage_service.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/apg_ui.dart';
import '../widgets/motion.dart';

class AdminShell extends StatefulWidget {
  final Future<void> Function() onLogout;
  final Locale currentLocale;
  final ValueChanged<Locale> onChangeLocale;

  const AdminShell({
    super.key,
    required this.onLogout,
    required this.currentLocale,
    required this.onChangeLocale,
  });

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  final _repository = const AdminRepository();
  int _index = 0;
  int _previousIndex = 0;
  bool _checkingServer = false;
  bool _syncingRules = false;
  bool _loadingData = true;
  String? _adminError;
  ApiConnectionSnapshot? _serverSnapshot;

  late AdminSystemSnapshot _system;
  late AdminOverviewData _overview;
  List<AdminMessage> _messages = <AdminMessage>[];
  List<AdminReport> _reports = <AdminReport>[];

  @override
  void initState() {
    super.initState();
    _system = _repository.offlineSystemSnapshot();
    _overview = AdminOverviewData.empty(system: _system);
    _loadAdminData();
  }

  void _setIndex(int value) {
    if (value == _index) return;
    setState(() {
      _previousIndex = _index;
      _index = value;
    });
  }

  Future<void> _loadAdminData({bool showFeedback = false}) async {
    if (mounted) {
      setState(() {
        _loadingData = !showFeedback && _messages.isEmpty && _reports.isEmpty;
        _adminError = null;
      });
    }
    try {
      final overview = await _repository.fetchOverview();
      final messages = await _repository.fetchMessages(filter: 'all');
      final reports = await _repository.fetchReports(status: 'all');
      if (!mounted) return;
      setState(() {
        _overview = overview;
        _system = overview.system;
        _messages = messages.isNotEmpty ? messages : overview.needsReview;
        _reports = reports;
        _loadingData = false;
      });
      if (showFeedback) _snack('تم تحديث بيانات لوحة الإدارة');
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingData = false;
        _adminError = 'تعذر تحميل بيانات لوحة الإدارة';
      });
    }
  }

  Future<void> _checkServer() async {
    setState(() => _checkingServer = true);
    final snapshot = await const ApgApiService().checkConnection(
      forceRefresh: true,
    );
    final system = await _repository.testConnection();
    if (!mounted) return;
    setState(() {
      _serverSnapshot = snapshot;
      _system = system;
      _checkingServer = false;
    });
    _snack(snapshot.isConnected ? 'الخادم متصل' : 'تعذر الاتصال بالخادم');
  }

  Future<void> _syncRules() async {
    setState(() => _syncingRules = true);
    await Future<void>.delayed(const Duration(milliseconds: 850));
    if (!mounted) return;
    setState(() => _syncingRules = false);
    _snack('تمت مزامنة القواعد');
  }

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('هل تريد تسجيل الخروج؟'),
          content: const Text(
            'سيتم إنهاء جلسة الأدمن والعودة إلى شاشة تسجيل الدخول.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('إلغاء'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text(
                'تسجيل الخروج',
                style: TextStyle(
                  color: AppTokens.danger,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ],
        ),
      ),
    );
    if (confirmed == true) {
      await widget.onLogout();
    }
  }

  void _openWeb() {
    _snack('رابط لوحة الويب غير مضبوط بعد');
  }

  void _snack(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  void _openMessage(AdminMessage message) {
    Navigator.of(context).push(
      apgSlideFadeRoute(
        AdminMessageDetailsScreen(
          message: message,
          onOpenWeb: _openWeb,
          onMessageAction: _snack,
        ),
      ),
    );
  }

  void _openReport(AdminReport report) {
    Navigator.of(context).push(
      apgSlideFadeRoute(
        AdminReportDetailsScreen(
          report: report,
          onChanged: (status) async {
            await _repository.updateReportStatus(report.id, status);
            setState(() => report.status = status);
            _snack('تم تحديث حالة البلاغ');
            await _loadAdminData(showFeedback: false);
          },
          onOpenWeb: _openWeb,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      AdminOverviewPage(
        system: _system,
        overview: _overview,
        serverSnapshot: _serverSnapshot,
        messages: _messages,
        reports: _reports,
        onOpenWeb: _openWeb,
        onOpenMessage: _openMessage,
        onGoReview: () => _setIndex(1),
      ),
      AdminReviewPage(
        messages: _messages,
        onOpenMessage: _openMessage,
        onAction: _snack,
      ),
      AdminReportsPage(
        reports: _reports,
        onOpenReport: _openReport,
        onChanged: (report, status) async {
          await _repository.updateReportStatus(report.id, status);
          setState(() => report.status = status);
          _snack('تم تحديث حالة البلاغ');
          await _loadAdminData(showFeedback: false);
        },
      ),
      AdminSystemPage(
        system: _system,
        serverSnapshot: _serverSnapshot,
        checking: _checkingServer,
        syncingRules: _syncingRules,
        onCheckServer: _checkServer,
        onSyncRules: _syncRules,
        onOpenWeb: _openWeb,
        onLogout: _confirmLogout,
      ),
    ];

    final titles = ['الملخص', 'المراجعة', 'البلاغات', 'النظام'];
    final subtitles = [
      'نظرة سريعة على أهم ما يحتاج انتباهًا.',
      'رسائل ونتائج تحتاج متابعة سريعة.',
      'بلاغات المستخدمين التي تحتاج مراجعة.',
      'صحة الخادم، القواعد، والحساب.',
    ];

    return Directionality(
      textDirection: context.isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: AppTokens.pageBackground(context),
        body: AppBackground(
          child: SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 8),
                  child: _AdminHeader(
                    title: titles[_index],
                    subtitle: subtitles[_index],
                    onOpenWeb: _openWeb,
                  ),
                ),
                Expanded(
                  child: _loadingData
                      ? const _AdminLoadingPage()
                      : _adminError != null
                      ? _AdminErrorPage(
                          message: _adminError!,
                          onRetry: () => _loadAdminData(showFeedback: true),
                        )
                      : RefreshIndicator(
                          onRefresh: () => _loadAdminData(showFeedback: true),
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 280),
                            switchInCurve: Curves.easeOutCubic,
                            switchOutCurve: Curves.easeInCubic,
                            transitionBuilder: (child, animation) {
                              final direction = _index >= _previousIndex
                                  ? 1.0
                                  : -1.0;
                              return FadeTransition(
                                opacity: animation,
                                child: SlideTransition(
                                  position: Tween<Offset>(
                                    begin: Offset(0.055 * direction, 0),
                                    end: Offset.zero,
                                  ).animate(animation),
                                  child: child,
                                ),
                              );
                            },
                            child: KeyedSubtree(
                              key: ValueKey(_index),
                              child: pages[_index],
                            ),
                          ),
                        ),
                ),
              ],
            ),
          ),
        ),
        bottomNavigationBar: _AdminBottomNav(
          index: _index,
          onChanged: _setIndex,
        ),
      ),
    );
  }
}

class _AdminHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  final VoidCallback onOpenWeb;
  const _AdminHeader({
    required this.title,
    required this.subtitle,
    required this.onOpenWeb,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            gradient: AppTokens.primaryButtonGradient(),
            borderRadius: BorderRadius.circular(18),
            boxShadow: [
              BoxShadow(
                color: AppTokens.brand.withValues(alpha: 0.20),
                blurRadius: 18,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: const Icon(
            Icons.admin_panel_settings_rounded,
            color: Colors.white,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 8,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  StatusBadge(
                    label: 'Admin',
                    color: AppTokens.brand,
                    icon: Icons.verified_rounded,
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTokens.mutedText(context),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
        PressableScale(
          onTap: onOpenWeb,
          child: Container(
            height: 40,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: AppTokens.brand.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(15),
              border: Border.all(
                color: AppTokens.brand.withValues(alpha: 0.18),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.open_in_new_rounded,
                  color: AppTokens.brand,
                  size: 18,
                ),
                const SizedBox(width: 6),
                Text(
                  'فتح الويب',
                  style: TextStyle(
                    color: AppTokens.brand,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _AdminBottomNav extends StatelessWidget {
  final int index;
  final ValueChanged<int> onChanged;
  const _AdminBottomNav({required this.index, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final items = [
      (Icons.dashboard_rounded, 'الملخص'),
      (Icons.fact_check_rounded, 'المراجعة'),
      (Icons.confirmation_number_rounded, 'البلاغات'),
      (Icons.dns_rounded, 'النظام'),
    ];
    return SafeArea(
      minimum: const EdgeInsets.fromLTRB(20, 0, 20, 14),
      child: Container(
        height: 72,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppTokens.surface(
            context,
          ).withValues(alpha: AppTokens.isDark(context) ? 0.92 : 0.98),
          borderRadius: BorderRadius.circular(28),
          border: Border.all(
            color: AppTokens.outline(context).withValues(alpha: 0.78),
          ),
          boxShadow: AppTokens.cardShadow(context),
        ),
        child: Row(
          children: [
            for (var i = 0; i < items.length; i++)
              Expanded(
                child: PressableScale(
                  onTap: () => onChanged(i),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 260),
                    curve: Curves.easeOutCubic,
                    height: 56,
                    decoration: BoxDecoration(
                      color: i == index
                          ? AppTokens.brand.withValues(alpha: 0.15)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(21),
                      border: i == index
                          ? Border.all(
                              color: AppTokens.brand.withValues(alpha: 0.22),
                            )
                          : null,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        AnimatedScale(
                          scale: i == index ? 1.08 : 1,
                          duration: const Duration(milliseconds: 210),
                          child: Icon(
                            items[i].$1,
                            color: i == index
                                ? AppTokens.brand
                                : AppTokens.mutedText(context),
                            size: 22,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          items[i].$2,
                          style: TextStyle(
                            color: i == index
                                ? AppTokens.brand
                                : AppTokens.mutedText(context),
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class AdminOverviewPage extends StatelessWidget {
  final AdminSystemSnapshot system;
  final AdminOverviewData overview;
  final ApiConnectionSnapshot? serverSnapshot;
  final List<AdminMessage> messages;
  final List<AdminReport> reports;
  final VoidCallback onOpenWeb;
  final ValueChanged<AdminMessage> onOpenMessage;
  final VoidCallback onGoReview;

  const AdminOverviewPage({
    super.key,
    required this.system,
    required this.overview,
    required this.serverSnapshot,
    required this.messages,
    required this.reports,
    required this.onOpenWeb,
    required this.onOpenMessage,
    required this.onGoReview,
  });

  @override
  Widget build(BuildContext context) {
    final today = overview.today;
    final serverOk = serverSnapshot?.isConnected ?? system.serverConnected;
    final databaseOk = system.databaseConnected;
    final newReports = overview.newReports;
    final reviewItems = <Object>[
      ...overview.needsReview.take(2),
      ...reports.where((r) => r.status == AdminReportStatus.newReport).take(1),
    ].take(3).toList();

    final alertText = !serverOk ? 'الخادم غير متصل' : overview.mainAlert;
    final alertColor = !serverOk
        ? AppTokens.danger
        : alertText.contains('خطورة') || alertText.contains('عالية')
        ? AppTokens.danger
        : newReports > 0
        ? AppTokens.warning
        : AppTokens.success;
    final alertIcon = !serverOk
        ? Icons.cloud_off_rounded
        : alertColor == AppTokens.danger
        ? Icons.warning_rounded
        : alertColor == AppTokens.warning
        ? Icons.feedback_rounded
        : Icons.verified_rounded;
    final alert = (alertText, alertColor, alertIcon);

    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        FadeSlideIn(
          child: AppCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SectionHeader(
                  title: 'حالة النظام',
                  subtitle: 'صحة الخدمات الأساسية الآن.',
                  icon: Icons.health_and_safety_rounded,
                  trailing: StatusBadge(
                    label: serverOk && databaseOk
                        ? 'النظام سليم'
                        : 'يحتاج انتباه',
                    color: serverOk && databaseOk
                        ? AppTokens.success
                        : AppTokens.warning,
                  ),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _AdminInfoTile(
                        label: 'الخادم',
                        value: serverOk ? 'متصل' : 'غير متصل',
                        color: serverOk ? AppTokens.success : AppTokens.danger,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _AdminInfoTile(
                        label: 'قاعدة البيانات',
                        value: databaseOk ? 'متصلة' : 'مشكلة',
                        color: databaseOk
                            ? AppTokens.success
                            : AppTokens.warning,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _AdminInfoTile(
                        label: 'زمن الاستجابة',
                        value: '${system.responseMs}ms',
                        color: AppTokens.brand,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _AdminInfoTile(
                        label: 'آخر تحديث',
                        value: system.lastSync,
                        color: AppTokens.neutral,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        FadeSlideIn(
          delay: const Duration(milliseconds: 70),
          child: AppCard(
            padding: const EdgeInsets.all(16),
            gradient: LinearGradient(
              colors: [
                alert.$2.withValues(alpha: 0.16),
                alert.$2.withValues(alpha: 0.045),
              ],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderColor: alert.$2.withValues(alpha: 0.20),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: alert.$2.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(alert.$3, color: alert.$2),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'أهم تنبيه الآن',
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        alert.$1,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: alert.$2,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _MiniMetric(
                title: 'التحليلات اليوم',
                value: '${today.totalAnalyses}',
                icon: Icons.analytics_rounded,
                color: AppTokens.brand,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _MiniMetric(
                title: 'خطر مرتفع',
                value: '${today.highRisk}',
                icon: Icons.dangerous_rounded,
                color: AppTokens.danger,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _MiniMetric(
                title: 'مشبوه',
                value: '${today.suspicious}',
                icon: Icons.warning_rounded,
                color: AppTokens.warning,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _MiniMetric(
                title: 'أجهزة نشطة',
                value: '${today.activeDevices}',
                icon: Icons.devices_rounded,
                color: AppTokens.success,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        AppCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                title: 'تحتاج مراجعة',
                subtitle: 'آخر الرسائل والبلاغات التي تستحق قرارًا سريعًا.',
                icon: Icons.fact_check_rounded,
              ),
              const SizedBox(height: 12),
              if (reviewItems.isEmpty)
                const _AdminEmptyState(
                  icon: Icons.verified_rounded,
                  title: 'لا توجد مشاكل حرجة حاليًا',
                  subtitle: 'سيظهر هنا أي تهديد أو بلاغ يحتاج تدخل الأدمن.',
                )
              else
                for (var i = 0; i < reviewItems.length; i++) ...[
                  StaggeredItem(
                    index: i,
                    child: _ReviewSummaryRow(
                      item: reviewItems[i],
                      onOpenMessage: onOpenMessage,
                      onGoReview: onGoReview,
                    ),
                  ),
                  if (i != reviewItems.length - 1)
                    Divider(
                      color: AppTokens.outline(context).withValues(alpha: 0.65),
                    ),
                ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        AppCard(
          padding: const EdgeInsets.all(16),
          onTap: onOpenWeb,
          child: Row(
            children: [
              Icon(Icons.open_in_new_rounded, color: AppTokens.brand),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'فتح لوحة الإدارة على الويب',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'للتقارير، التصدير، والفلاتر المتقدمة.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class AdminReviewPage extends StatefulWidget {
  final List<AdminMessage> messages;
  final ValueChanged<AdminMessage> onOpenMessage;
  final ValueChanged<String> onAction;
  const AdminReviewPage({
    super.key,
    required this.messages,
    required this.onOpenMessage,
    required this.onAction,
  });

  @override
  State<AdminReviewPage> createState() => _AdminReviewPageState();
}

class _AdminReviewPageState extends State<AdminReviewPage> {
  final _search = TextEditingController();
  String _filter = 'تحتاج مراجعة';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<AdminMessage> get _filtered {
    final q = _search.text.trim();
    return widget.messages.where((m) {
      final review = m.label == 'خطر مرتفع' || m.label == 'مشبوه';
      final matchesFilter =
          _filter == 'الكل' ||
          (_filter == 'تحتاج مراجعة' && review) ||
          m.label == _filter;
      final matchesSearch =
          q.isEmpty ||
          m.text.contains(q) ||
          m.source.contains(q) ||
          m.deviceHash.contains(q) ||
          m.sourceApp.contains(q);
      return matchesFilter && matchesSearch;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final filters = ['تحتاج مراجعة', 'خطر مرتفع', 'مشبوه', 'الكل'];
    final list = _filtered;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        _AdminSearchField(
          controller: _search,
          hint: 'ابحث في الرسائل أو الجهاز أو المصدر',
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: 12),
        _AdminChips(
          filters: filters,
          selected: _filter,
          onChanged: (v) => setState(() => _filter = v),
        ),
        const SizedBox(height: 12),
        Text(
          '${list.length} عنصر يحتاج مراجعة',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: AppTokens.mutedText(context),
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 12),
        if (list.isEmpty)
          const _AdminEmptyState(
            icon: Icons.fact_check_rounded,
            title: 'لا توجد عناصر تحتاج مراجعة',
            subtitle: 'سيظهر هنا أي تهديد أو رسالة مشبوهة تحتاج تدخل الأدمن.',
          )
        else
          for (var i = 0; i < list.length; i++) ...[
            StaggeredItem(
              index: i,
              child: _AdminReviewCard(
                message: list[i],
                onTap: () => widget.onOpenMessage(list[i]),
                onAction: widget.onAction,
              ),
            ),
            const SizedBox(height: 10),
          ],
      ],
    );
  }
}

class AdminReportsPage extends StatefulWidget {
  final List<AdminReport> reports;
  final ValueChanged<AdminReport> onOpenReport;
  final Future<void> Function(AdminReport report, AdminReportStatus status)
  onChanged;
  const AdminReportsPage({
    super.key,
    required this.reports,
    required this.onOpenReport,
    required this.onChanged,
  });

  @override
  State<AdminReportsPage> createState() => _AdminReportsPageState();
}

class _AdminReportsPageState extends State<AdminReportsPage> {
  String _filter = 'الكل';

  List<AdminReport> get _filtered => widget.reports
      .where((r) => _filter == 'الكل' || adminStatusLabel(r.status) == _filter)
      .toList();

  @override
  Widget build(BuildContext context) {
    final filters = ['الكل', 'جديد', 'قيد المراجعة', 'تم الحل', 'مرفوض'];
    final list = _filtered;
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        AppCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                title: 'بلاغات المستخدمين',
                subtitle:
                    'تعامل معها كتذاكر مختصرة. القرارات الكبيرة في الويب.',
                icon: Icons.confirmation_number_rounded,
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: _TinyCounter(
                      label: 'جديدة',
                      value:
                          '${widget.reports.where((r) => r.status == AdminReportStatus.newReport).length}',
                      color: AppTokens.brand,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _TinyCounter(
                      label: 'قيد المراجعة',
                      value:
                          '${widget.reports.where((r) => r.status == AdminReportStatus.inReview).length}',
                      color: AppTokens.warning,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _TinyCounter(
                      label: 'تم الحل',
                      value:
                          '${widget.reports.where((r) => r.status == AdminReportStatus.resolved).length}',
                      color: AppTokens.success,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _TinyCounter(
                      label: 'مرفوضة',
                      value:
                          '${widget.reports.where((r) => r.status == AdminReportStatus.rejected).length}',
                      color: AppTokens.neutral,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        _AdminChips(
          filters: filters,
          selected: _filter,
          onChanged: (v) => setState(() => _filter = v),
        ),
        const SizedBox(height: 14),
        if (list.isEmpty)
          const _AdminEmptyState(
            icon: Icons.feedback_outlined,
            title: 'لا توجد بلاغات جديدة',
            subtitle: 'بلاغات المستخدمين ستظهر هنا عند وصولها.',
          )
        else
          for (var i = 0; i < list.length; i++) ...[
            StaggeredItem(
              index: i,
              child: _AdminReportCard(
                report: list[i],
                onOpen: () => widget.onOpenReport(list[i]),
                onReview: () async =>
                    widget.onChanged(list[i], AdminReportStatus.inReview),
                onResolve: () async =>
                    widget.onChanged(list[i], AdminReportStatus.resolved),
              ),
            ),
            const SizedBox(height: 10),
          ],
      ],
    );
  }
}

class AdminSystemPage extends StatelessWidget {
  final AdminSystemSnapshot system;
  final ApiConnectionSnapshot? serverSnapshot;
  final bool checking;
  final bool syncingRules;
  final Future<void> Function() onCheckServer;
  final Future<void> Function() onSyncRules;
  final VoidCallback onOpenWeb;
  final Future<void> Function() onLogout;

  const AdminSystemPage({
    super.key,
    required this.system,
    required this.serverSnapshot,
    required this.checking,
    required this.syncingRules,
    required this.onCheckServer,
    required this.onSyncRules,
    required this.onOpenWeb,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    final connected = serverSnapshot?.isConnected ?? system.serverConnected;
    final name = LocalStorageService.instance.getSessionName();
    final email = LocalStorageService.instance.getSessionEmail();
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        _SystemSection(
          title: 'حالة الخادم',
          icon: Icons.cloud_done_rounded,
          trailing: StatusBadge(
            label: connected ? 'متصل' : 'غير متصل',
            color: connected ? AppTokens.success : AppTokens.danger,
          ),
          children: [
            _AdminRow(
              label: 'الاتصال',
              value: connected ? 'تم الاتصال بخادم التحليل' : 'غير متصل',
            ),
            _AdminRow(label: 'زمن الاستجابة', value: '${system.responseMs}ms'),
            _AdminRow(label: 'آخر فحص', value: system.lastSync),
            const SizedBox(height: 10),
            SecondaryButton(
              label: checking ? 'جارِ الاختبار...' : 'اختبار الاتصال',
              icon: Icons.wifi_tethering_rounded,
              onPressed: checking ? null : onCheckServer,
            ),
          ],
        ),
        _SystemSection(
          title: 'قاعدة البيانات',
          icon: Icons.storage_rounded,
          trailing: StatusBadge(
            label: system.databaseConnected ? 'متصلة' : 'مشكلة',
            color: system.databaseConnected
                ? AppTokens.success
                : AppTokens.warning,
          ),
          children: [
            _AdminRow(label: 'سجلات اليوم', value: '${system.recordsToday}'),
            _AdminRow(label: 'آخر مزامنة', value: system.lastSync),
          ],
        ),
        _SystemSection(
          title: 'النموذج والقواعد',
          icon: Icons.psychology_rounded,
          children: [
            _AdminRow(label: 'إصدار النموذج', value: system.modelVersion),
            _AdminRow(label: 'إصدار القواعد', value: system.rulesVersion),
            _AdminRow(label: 'آخر تحديث', value: system.lastSync),
            const SizedBox(height: 10),
            SecondaryButton(
              label: syncingRules ? 'جارِ المزامنة...' : 'مزامنة القواعد',
              icon: Icons.sync_rounded,
              onPressed: syncingRules ? null : onSyncRules,
            ),
          ],
        ),
        AppCard(
          padding: const EdgeInsets.all(16),
          onTap: onOpenWeb,
          child: Row(
            children: [
              Icon(Icons.open_in_new_rounded, color: AppTokens.brand),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'لوحة الويب',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'للتقارير، التصدير، وإدارة القواعد المتقدمة.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        _SystemSection(
          title: 'الحساب',
          icon: Icons.account_circle_rounded,
          trailing: StatusBadge(label: 'Admin', color: AppTokens.brand),
          children: [
            _AdminRow(label: 'الاسم', value: name.isEmpty ? 'مسؤول APG' : name),
            _AdminRow(
              label: 'البريد',
              value: email.isEmpty ? 'admin@apg.local' : maskSensitive(email),
            ),
            _AdminRow(label: 'الدور', value: 'Admin'),
            const SizedBox(height: 12),
            _DangerButton(
              label: 'تسجيل الخروج',
              icon: Icons.logout_rounded,
              onPressed: onLogout,
            ),
          ],
        ),
      ],
    );
  }
}

class AdminMessageDetailsScreen extends StatefulWidget {
  final AdminMessage message;
  final VoidCallback onOpenWeb;
  final ValueChanged<String> onMessageAction;
  const AdminMessageDetailsScreen({
    super.key,
    required this.message,
    required this.onOpenWeb,
    required this.onMessageAction,
  });

  @override
  State<AdminMessageDetailsScreen> createState() =>
      _AdminMessageDetailsScreenState();
}

class _AdminMessageDetailsScreenState extends State<AdminMessageDetailsScreen> {
  bool _showFull = false;

  void _copy(BuildContext context, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('تم نسخ النص')));
  }

  Future<void> _confirmShowFull() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('قد يحتوي النص على بيانات حساسة'),
          content: const Text(
            'يعرض النص الكامل رموزًا أو أرقامًا قد تكون حساسة. هل تريد المتابعة؟',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('إلغاء'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('إظهار'),
            ),
          ],
        ),
      ),
    );
    if (ok == true) setState(() => _showFull = true);
  }

  @override
  Widget build(BuildContext context) {
    final message = widget.message;
    final masked = maskSensitive(message.text);
    final displayText = _showFull ? message.text : masked;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: AppTokens.pageBackground(context),
        body: AppBackground(
          child: SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 40),
              children: [
                _DetailsHeader(
                  title: 'تفاصيل الرسالة',
                  onOpenWeb: widget.onOpenWeb,
                ),
                const SizedBox(height: 14),
                FadeSlideIn(
                  child: AppCard(
                    padding: const EdgeInsets.all(16),
                    gradient: LinearGradient(
                      colors: [
                        message.color.withValues(alpha: 0.14),
                        message.color.withValues(alpha: 0.035),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            StatusBadge(
                              label: message.label,
                              color: message.color,
                              icon: Icons.shield_rounded,
                            ),
                            const Spacer(),
                            Text(
                              '${message.score}/100',
                              style: Theme.of(context).textTheme.headlineSmall
                                  ?.copyWith(
                                    fontWeight: FontWeight.w900,
                                    color: message.color,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        _AdminRow(
                          label: 'وقت التحليل',
                          value: shortTime(message.createdAt),
                        ),
                        _AdminRow(label: 'المصدر', value: message.source),
                        _AdminRow(
                          label: 'الجهاز/المستخدم',
                          value: '${message.deviceHash} • ${message.userHash}',
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: SecondaryButton(
                        label: 'تعليم كمراجعة',
                        icon: Icons.fact_check_rounded,
                        onPressed: () =>
                            widget.onMessageAction('تم تعليم الرسالة كمراجعة'),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: SecondaryButton(
                        label: 'فتح في الويب',
                        icon: Icons.open_in_new_rounded,
                        onPressed: widget.onOpenWeb,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: SecondaryButton(
                        label: 'نسخ التفاصيل',
                        icon: Icons.copy_all_rounded,
                        onPressed: () => _copy(
                          context,
                          '${message.label} ${message.score}/100 - $masked',
                        ),
                      ),
                    ),
                    if (message.label == 'خطر مرتفع') ...[
                      const SizedBox(width: 10),
                      Expanded(
                        child: _DangerOutlineButton(
                          label: 'تمييز كحرج',
                          icon: Icons.priority_high_rounded,
                          onPressed: () =>
                              widget.onMessageAction('تم تمييز الرسالة كحرجة'),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 12),
                AppCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SectionHeader(
                        title: 'النص الأصلي',
                        subtitle: _showFull
                            ? 'النص الكامل ظاهر الآن.'
                            : 'تم إخفاء رموز التحقق والبيانات الحساسة تلقائيًا.',
                        icon: Icons.article_rounded,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        displayText,
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          height: 1.7,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: SecondaryButton(
                              label: 'نسخ النص',
                              icon: Icons.copy_rounded,
                              onPressed: () => _copy(context, displayText),
                            ),
                          ),
                          if (!_showFull) ...[
                            const SizedBox(width: 10),
                            Expanded(
                              child: SecondaryButton(
                                label: 'إظهار النص الكامل',
                                icon: Icons.visibility_rounded,
                                onPressed: _confirmShowFull,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                AppCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SectionHeader(
                        title: 'أسباب التصنيف',
                        icon: Icons.list_alt_rounded,
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final reason in message.reasons)
                            StatusBadge(label: reason, color: message.color),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                AppCard(
                  padding: EdgeInsets.zero,
                  child: ExpansionTile(
                    tilePadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 4,
                    ),
                    childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    title: Text(
                      'معلومات تقنية',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    subtitle: Text(
                      'مخفية افتراضيًا لتخفيف شاشة الموبايل.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                      ),
                    ),
                    children: [
                      _AdminRow(label: 'request id', value: message.requestId),
                      _AdminRow(label: 'model version', value: 'APG-NLP v1.9'),
                      _AdminRow(
                        label: 'response time',
                        value: '${message.responseMs}ms',
                      ),
                      _AdminRow(label: 'source app', value: message.sourceApp),
                      _AdminRow(
                        label: 'device hash',
                        value: message.deviceHash,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class AdminReportDetailsScreen extends StatelessWidget {
  final AdminReport report;
  final Future<void> Function(AdminReportStatus status) onChanged;
  final VoidCallback onOpenWeb;
  const AdminReportDetailsScreen({
    super.key,
    required this.report,
    required this.onChanged,
    required this.onOpenWeb,
  });

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: AppTokens.pageBackground(context),
        body: AppBackground(
          child: SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 40),
              children: [
                _DetailsHeader(title: 'تفاصيل البلاغ', onOpenWeb: onOpenWeb),
                const SizedBox(height: 14),
                AppCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          StatusBadge(
                            label: adminStatusLabel(report.status),
                            color: adminStatusColor(report.status),
                            icon: Icons.flag_rounded,
                          ),
                          const Spacer(),
                          Text(
                            shortTime(report.createdAt),
                            style: TextStyle(
                              color: AppTokens.mutedText(context),
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        report.type,
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 12),
                      _AdminRow(
                        label: 'النتيجة الحالية',
                        value: report.currentLabel,
                      ),
                      _AdminRow(
                        label: 'المستخدم/الجهاز',
                        value: report.userHash,
                      ),
                      const Divider(height: 24),
                      Text(
                        maskSensitive(report.text),
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          height: 1.7,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (report.note != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          'ملاحظة المستخدم: ${report.note}',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: AppTokens.mutedText(context),
                                height: 1.6,
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                AppCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SectionHeader(
                        title: 'إجراءات البلاغ',
                        subtitle:
                            'الموبايل لتغيير الحالة فقط، وإدارة القواعد في الويب.',
                        icon: Icons.touch_app_rounded,
                      ),
                      const SizedBox(height: 12),
                      SecondaryButton(
                        label: 'قيد المراجعة',
                        icon: Icons.pending_actions_rounded,
                        onPressed: () async =>
                            onChanged(AdminReportStatus.inReview),
                      ),
                      const SizedBox(height: 10),
                      SecondaryButton(
                        label: 'تم الحل',
                        icon: Icons.verified_rounded,
                        onPressed: () async =>
                            onChanged(AdminReportStatus.resolved),
                      ),
                      const SizedBox(height: 10),
                      _DangerOutlineButton(
                        label: 'رفض',
                        icon: Icons.block_rounded,
                        onPressed: () async =>
                            onChanged(AdminReportStatus.rejected),
                      ),
                      const SizedBox(height: 10),
                      PrimaryButton(
                        label: 'فتح في الويب',
                        icon: Icons.open_in_new_rounded,
                        onPressed: onOpenWeb,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ReviewSummaryRow extends StatelessWidget {
  final Object item;
  final ValueChanged<AdminMessage> onOpenMessage;
  final VoidCallback onGoReview;
  const _ReviewSummaryRow({
    required this.item,
    required this.onOpenMessage,
    required this.onGoReview,
  });

  @override
  Widget build(BuildContext context) {
    if (item is AdminMessage) {
      final message = item as AdminMessage;
      return PressableScale(
        onTap: () => onOpenMessage(message),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            children: [
              StatusBadge(label: 'رسالة', color: message.color),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${message.label} • ${shortTime(message.createdAt)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              Text(
                'مراجعة',
                style: TextStyle(
                  color: AppTokens.brand,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      );
    }
    final report = item as AdminReport;
    return PressableScale(
      onTap: onGoReview,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            StatusBadge(label: 'بلاغ', color: adminStatusColor(report.status)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                '${report.type} • ${shortTime(report.createdAt)}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w900),
              ),
            ),
            Text(
              'مراجعة',
              style: TextStyle(
                color: AppTokens.brand,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdminReviewCard extends StatelessWidget {
  final AdminMessage message;
  final VoidCallback onTap;
  final ValueChanged<String> onAction;
  const _AdminReviewCard({
    required this.message,
    required this.onTap,
    required this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(15),
      onTap: onTap,
      borderColor: message.color.withValues(alpha: 0.24),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 5,
              decoration: BoxDecoration(
                color: message.color,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      StatusBadge(label: message.label, color: message.color),
                      const Spacer(),
                      Text(
                        '${message.score}/100',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          color: message.color,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      PopupMenuButton<String>(
                        onSelected: (value) {
                          if (value == 'copy') {
                            Clipboard.setData(
                              ClipboardData(text: maskSensitive(message.text)),
                            );
                            onAction('تم نسخ النص');
                          } else if (value == 'review') {
                            onAction('تم تعليم الرسالة كمراجعة');
                          } else {
                            onAction('رابط لوحة الويب غير مضبوط بعد');
                          }
                        },
                        itemBuilder: (context) => const [
                          PopupMenuItem(value: 'copy', child: Text('نسخ النص')),
                          PopupMenuItem(
                            value: 'review',
                            child: Text('تعليم كمراجعة'),
                          ),
                          PopupMenuItem(
                            value: 'web',
                            child: Text('فتح في الويب'),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    maskSensitive(message.text),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      height: 1.45,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 9),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      _MiniMeta(
                        icon: Icons.source_rounded,
                        text: message.source,
                      ),
                      _MiniMeta(
                        icon: Icons.devices_rounded,
                        text: message.deviceHash,
                      ),
                      _MiniMeta(
                        icon: Icons.schedule_rounded,
                        text: shortTime(message.createdAt),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: SizedBox(
                      width: 126,
                      child: PrimaryButton(
                        label: 'مراجعة',
                        icon: Icons.fact_check_rounded,
                        onPressed: onTap,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AdminReportCard extends StatelessWidget {
  final AdminReport report;
  final VoidCallback onOpen;
  final VoidCallback onReview;
  final VoidCallback onResolve;
  const _AdminReportCard({
    required this.report,
    required this.onOpen,
    required this.onReview,
    required this.onResolve,
  });

  @override
  Widget build(BuildContext context) {
    final color = adminStatusColor(report.status);
    return AppCard(
      padding: const EdgeInsets.all(15),
      onTap: onOpen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              StatusBadge(
                label: adminStatusLabel(report.status),
                color: color,
                icon: Icons.flag_rounded,
              ),
              const Spacer(),
              Text(
                shortTime(report.createdAt),
                style: TextStyle(
                  color: AppTokens.mutedText(context),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            report.type,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(
            maskSensitive(report.text),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              height: 1.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          if (report.note != null) ...[
            const SizedBox(height: 6),
            Text(
              'ملاحظة: ${report.note}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.mutedText(context),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: SecondaryButton(
                  label: 'مراجعة',
                  icon: Icons.rate_review_rounded,
                  onPressed: onReview,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: SecondaryButton(
                  label: 'تم الحل',
                  icon: Icons.verified_rounded,
                  onPressed: onResolve,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SystemSection extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget? trailing;
  final List<Widget> children;
  const _SystemSection({
    required this.title,
    required this.icon,
    this.trailing,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AppCard(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionHeader(title: title, icon: icon, trailing: trailing),
            const SizedBox(height: 10),
            ...children,
          ],
        ),
      ),
    );
  }
}

class _MiniMetric extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;
  const _MiniMetric({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                    color: color,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTokens.mutedText(context),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TinyCounter extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _TinyCounter({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.14)),
      ),
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w900,
              fontSize: 17,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminInfoTile extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _AdminInfoTile({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminRow extends StatelessWidget {
  final String label;
  final String value;
  const _AdminRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTokens.mutedText(context),
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.end,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniMeta extends StatelessWidget {
  final IconData icon;
  final String text;
  const _MiniMeta({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppTokens.mutedText(context)),
        const SizedBox(width: 4),
        Text(
          text,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AppTokens.mutedText(context),
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _AdminSearchField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final ValueChanged<String> onChanged;
  const _AdminSearchField({
    required this.controller,
    required this.hint,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      onChanged: onChanged,
      decoration: InputDecoration(
        prefixIcon: const Icon(Icons.search_rounded),
        hintText: hint,
      ),
    );
  }
}

class _AdminChips extends StatelessWidget {
  final List<String> filters;
  final String selected;
  final ValueChanged<String> onChanged;
  const _AdminChips({
    required this.filters,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final filter in filters) ...[
            PressableScale(
              onTap: () => onChanged(filter),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 9,
                ),
                decoration: BoxDecoration(
                  color: filter == selected
                      ? AppTokens.brand
                      : AppTokens.surfaceAlt(context),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: filter == selected
                        ? AppTokens.brand
                        : AppTokens.outline(context),
                  ),
                ),
                child: Text(
                  filter,
                  style: TextStyle(
                    color: filter == selected
                        ? Colors.white
                        : AppTokens.textPrimary(context),
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }
}

class _AdminLoadingPage extends StatelessWidget {
  const _AdminLoadingPage();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        AppCard(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SkeletonLine(width: 150, height: 18),
              const SizedBox(height: 14),
              Row(
                children: const [
                  Expanded(child: _SkeletonBox(height: 70)),
                  SizedBox(width: 10),
                  Expanded(child: _SkeletonBox(height: 70)),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: const [
                  Expanded(child: _SkeletonBox(height: 58)),
                  SizedBox(width: 10),
                  Expanded(child: _SkeletonBox(height: 58)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: const [
            Expanded(child: _SkeletonBox(height: 86)),
            SizedBox(width: 10),
            Expanded(child: _SkeletonBox(height: 86)),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: const [
            Expanded(child: _SkeletonBox(height: 86)),
            SizedBox(width: 10),
            Expanded(child: _SkeletonBox(height: 86)),
          ],
        ),
        const SizedBox(height: 12),
        const _SkeletonBox(height: 180),
      ],
    );
  }
}

class _AdminErrorPage extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const _AdminErrorPage({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        20,
        8,
        20,
        AppTokens.bottomNavContentPadding,
      ),
      children: [
        AppCard(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: AppTokens.danger.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Icon(
                  Icons.cloud_off_rounded,
                  color: AppTokens.danger,
                  size: 30,
                ),
              ),
              const SizedBox(height: 14),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 8),
              Text(
                'تأكد أن خادم APG يعمل ثم حاول تحديث لوحة الإدارة مرة أخرى.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTokens.mutedText(context),
                  height: 1.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),
              PrimaryButton(
                label: 'إعادة المحاولة',
                icon: Icons.refresh_rounded,
                onPressed: onRetry,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SkeletonBox extends StatelessWidget {
  final double height;
  const _SkeletonBox({required this.height});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(
          context,
        ).withValues(alpha: AppTokens.isDark(context) ? 0.55 : 0.86),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.55),
        ),
      ),
    );
  }
}

class _SkeletonLine extends StatelessWidget {
  final double width;
  final double height;
  const _SkeletonLine({required this.width, required this.height});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(
          context,
        ).withValues(alpha: AppTokens.isDark(context) ? 0.60 : 0.90),
        borderRadius: BorderRadius.circular(999),
      ),
    );
  }
}

class _AdminEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  const _AdminEmptyState({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        children: [
          Icon(icon, color: AppTokens.brand, size: 42),
          const SizedBox(height: 12),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailsHeader extends StatelessWidget {
  final String title;
  final VoidCallback onOpenWeb;
  const _DetailsHeader({required this.title, required this.onOpenWeb});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        PressableScale(
          onTap: () => Navigator.of(context).maybePop(),
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTokens.surface(context),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTokens.outline(context)),
            ),
            child: const Icon(Icons.arrow_back_rounded),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: Theme.of(
              context,
            ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
          ),
        ),
        PressableScale(
          onTap: onOpenWeb,
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTokens.brand.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppTokens.brand.withValues(alpha: 0.18),
              ),
            ),
            child: Icon(Icons.open_in_new_rounded, color: AppTokens.brand),
          ),
        ),
      ],
    );
  }
}

class _DangerButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  const _DangerButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return PressableScale(
      onTap: onPressed,
      child: SizedBox(
        width: double.infinity,
        height: 50,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: AppTokens.danger.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(AppTokens.radiusMd),
            border: Border.all(color: AppTokens.danger.withValues(alpha: 0.45)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: AppTokens.danger, size: 20),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  color: AppTokens.danger,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DangerOutlineButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onPressed;
  const _DangerOutlineButton({
    required this.label,
    required this.icon,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return PressableScale(
      onTap: onPressed,
      child: Container(
        height: 50,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppTokens.radiusMd),
          border: Border.all(color: AppTokens.danger.withValues(alpha: 0.45)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: AppTokens.danger, size: 19),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: AppTokens.danger,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
