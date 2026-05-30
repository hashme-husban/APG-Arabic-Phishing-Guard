import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import '../l10n/l10n_extensions.dart';
import '../models/notification_inbox_item.dart';
import '../theme/app_tokens.dart';
import '../utils/analysis_share_helper.dart';
import '../utils/text_mapper.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/motion.dart';
import '../widgets/page_intro_header.dart';
import '../widgets/feedback_report_sheet.dart';
import 'result_details_screen.dart';

class NotificationsScreen extends StatefulWidget {
  final List<NotificationInboxItem> items;
  final bool permissionGranted;
  final bool autoAnalyzeEnabled;
  final Future<void> Function() onRequestNotificationAccess;
  final ValueChanged<String> onDeleteNotificationItem;
  final VoidCallback onOpenSettings;

  const NotificationsScreen({
    super.key,
    required this.items,
    required this.permissionGranted,
    required this.autoAnalyzeEnabled,
    required this.onRequestNotificationAccess,
    required this.onDeleteNotificationItem,
    required this.onOpenSettings,
  });

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _selectedFilter = 'all';

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_handleSearch);
  }

  void _handleSearch() {
    setState(() {});
  }

  List<NotificationInboxItem> get _filteredItems {
    final query = _searchController.text.trim().toLowerCase();

    return widget.items.where((item) {
      final matchesFilter = switch (_selectedFilter) {
        'analyzed' => item.isAnalyzed,
        'high' => item.result?.finalLabel.toLowerCase() == 'phishing',
        'raw' => !item.isAnalyzed,
        _ => true,
      };

      final searchable = [
        item.sourceAppName,
        item.channel,
        item.sender,
        item.mentionedEntity,
        item.title,
        item.content,
        item.result?.finalLabel ?? '',
        item.result?.summary ?? '',
      ].join(' ').toLowerCase();

      final matchesSearch = query.isEmpty || searchable.contains(query);
      return matchesFilter && matchesSearch;
    }).toList();
  }

  int _countAnalyzed() => widget.items.where((e) => e.isAnalyzed).length;

  int _countHighRisk() {
    return widget.items
        .where((e) => e.result?.finalLabel.toLowerCase() == 'phishing')
        .length;
  }

  String _verificationText(String value) {
    final trimmed = value.trim();
    if (trimmed == 'غير معروف' || trimmed == 'غير محددة') {
      return 'تعذر التحقق';
    }
    return trimmed;
  }

  void _showSnack(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _copyItem(NotificationInboxItem item) async {
    final text = item.isAnalyzed && item.toHistoryItem() != null
        ? AnalysisShareHelper.buildShareText(context, item.toHistoryItem()!)
        : item.rawCombinedText;

    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    _showSnack(context.l10n.copied);
  }

  Future<void> _shareItem(NotificationInboxItem item) async {
    if (item.toHistoryItem() == null) {
      _showSnack(context.l10n.noAnalysisToShare);
      return;
    }

    await AnalysisShareHelper.shareAnalysis(context, item.toHistoryItem()!);
    if (!mounted) return;
    _showSnack(context.l10n.shareOpened);
  }

  void _openDetails(NotificationInboxItem item) {
    final historyItem = item.toHistoryItem();
    if (historyItem == null) return;
    if (kDebugMode) {
      debugPrint(
        'APG_SCORE_TRACE screen=notifications itemId=${item.id} '
        'analysisId=${historyItem.result.remoteId} '
        'score=${historyItem.result.finalScore}',
      );
    }

    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ResultDetailsScreen(item: historyItem)),
    );
  }

  Future<void> _confirmDelete(NotificationInboxItem item) async {
    final l10n = context.l10n;
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (context) {
            return AlertDialog(
              title: Text(l10n.confirmDeleteNotificationTitle),
              content: Text(l10n.confirmDeleteNotificationMessage),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: Text(l10n.cancel),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: Text(l10n.delete),
                ),
              ],
            );
          },
        ) ??
        false;

    if (!confirmed) return;
    if (!mounted) return;

    widget.onDeleteNotificationItem(item.id);
    _showSnack(context.l10n.notificationDeleted);
  }

  void _openActions(NotificationInboxItem item) {
    final l10n = context.l10n;

    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      builder: (sheetContext) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (item.isAnalyzed)
                ListTile(
                  onTap: () {
                    Navigator.of(sheetContext).pop();
                    _openDetails(item);
                  },
                  leading: const Icon(Icons.open_in_new_rounded),
                  title: Text(l10n.openDetails),
                  subtitle: Text(
                    context.isArabic
                        ? 'عرض نتيجة التحليل الكاملة'
                        : 'Open the full analysis result.',
                  ),
                ),
              ListTile(
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _copyItem(item);
                },
                leading: const Icon(Icons.copy_rounded),
                title: Text(l10n.copy),
                subtitle: Text(
                  context.isArabic
                      ? 'نسخ النص أو النتيجة'
                      : 'Copy the raw text or the analysis result.',
                ),
              ),
              if (item.isAnalyzed)
                ListTile(
                  onTap: () async {
                    Navigator.of(sheetContext).pop();
                    await _shareItem(item);
                  },
                  leading: const Icon(Icons.share_rounded),
                  title: Text(l10n.share),
                  subtitle: Text(
                    context.isArabic
                        ? 'مشاركة نتيجة التحليل'
                        : 'Share the analysis result.',
                  ),
                ),
              if (item.isAnalyzed && item.toHistoryItem() != null)
                ListTile(
                  onTap: () {
                    Navigator.of(sheetContext).pop();
                    FeedbackReportSheet.show(context, item.toHistoryItem()!);
                  },
                  leading: const Icon(Icons.feedback_rounded),
                  title: const Text('الإبلاغ عن نتيجة غير دقيقة'),
                  subtitle: const Text('إرسال ملاحظة لتحسين التصنيف'),
                ),
              ListTile(
                onTap: () async {
                  Navigator.of(sheetContext).pop();
                  await _confirmDelete(item);
                },
                leading: const Icon(Icons.delete_outline_rounded),
                title: Text(l10n.delete),
                subtitle: Text(
                  context.isArabic
                      ? 'إزالة الإشعار من صندوق الإشعارات'
                      : 'Remove the notification from the inbox.',
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _filterChip(String label, String value) {
    return ChoiceChip(
      label: Text(label),
      selected: _selectedFilter == value,
      onSelected: (_) {
        setState(() {
          _selectedFilter = value;
        });
      },
    );
  }

  Widget _buildPermissionCard() {
    final l10n = context.l10n;

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      gradient: AppTokens.heroGradient(context),
      border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            l10n.permissionCardTitle,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            widget.permissionGranted
                ? l10n.permissionCardGranted
                : (context.isArabic
                      ? 'لم يتم منح صلاحية الوصول للإشعارات بعد. افتح الإعدادات وفعّلها.'
                      : l10n.permissionCardRequired),
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Colors.white.withValues(alpha: 0.86),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _statusChip(
                widget.permissionGranted
                    ? l10n.accessGranted
                    : (context.isArabic
                          ? 'الصلاحية مطلوبة'
                          : l10n.accessRequired),
              ),
              _statusChip(
                widget.autoAnalyzeEnabled
                    ? l10n.autoAnalyzeOn
                    : (context.isArabic
                          ? 'التحليل التلقائي مقفل'
                          : l10n.autoAnalyzeOff),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              ElevatedButton.icon(
                onPressed: () async {
                  await widget.onRequestNotificationAccess();
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: AppTokens.brand,
                ),
                icon: const Icon(Icons.lock_open_rounded),
                label: Text(
                  widget.permissionGranted
                      ? l10n.recheckPermission
                      : (context.isArabic
                            ? 'منح الصلاحية'
                            : l10n.grantPermission),
                ),
              ),
              OutlinedButton.icon(
                onPressed: widget.onOpenSettings,
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Colors.white54),
                ),
                icon: const Icon(Icons.settings_rounded),
                label: Text(context.isArabic ? 'الإعدادات' : l10n.openSettings),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _statusChip(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildSummaryCard() {
    final l10n = context.l10n;

    return AppSurfaceCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          _miniStat(
            l10n.total,
            '${widget.items.length}',
            Icons.inbox_rounded,
            AppTokens.brandCyan,
          ),
          const SizedBox(width: 8),
          _miniStat(
            l10n.analyzed,
            '${_countAnalyzed()}',
            Icons.fact_check_rounded,
            AppTokens.success,
          ),
          const SizedBox(width: 8),
          _miniStat(
            l10n.highRisk,
            '${_countHighRisk()}',
            Icons.gpp_bad_rounded,
            AppTokens.danger,
          ),
          const SizedBox(width: 8),
          _miniStat(
            l10n.notAnalyzed,
            '${widget.items.length - _countAnalyzed()}',
            Icons.hourglass_empty_rounded,
            AppTokens.warning,
          ),
        ],
      ),
    );
  }

  Widget _miniStat(String title, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 11),
        decoration: BoxDecoration(
          color: AppTokens.surfaceAlt(context).withValues(alpha: 0.72),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppTokens.outline(context).withValues(alpha: 0.60),
          ),
        ),
        child: Column(
          children: [
            Icon(icon, color: color, size: 17),
            const SizedBox(height: 6),
            Text(
              value,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.mutedText(context),
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchAndFilters() {
    final l10n = context.l10n;

    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          TextField(
            controller: _searchController,
            decoration: InputDecoration(
              labelText: context.isArabic
                  ? 'بحث داخل الإشعارات'
                  : l10n.searchNotifications,
              hintText: context.isArabic
                  ? 'بحث داخل الإشعارات'
                  : l10n.searchNotificationsHint,
              prefixIcon: const Icon(Icons.search_rounded),
            ),
          ),
          const SizedBox(height: 14),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _filterChip(l10n.all, 'all'),
                _filterChip(l10n.analyzed, 'analyzed'),
                _filterChip(l10n.highRisk, 'high'),
                _filterChip(l10n.raw, 'raw'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationCard(NotificationInboxItem item) {
    final analysisColor = item.isAnalyzed
        ? AppTokens.riskColor(item.result!.finalLabel)
        : AppTokens.neutral;
    final preview = item.previewText.isEmpty
        ? context.l10n.noContentAvailable
        : item.previewText;

    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      onTap: item.isAnalyzed
          ? () => _openDetails(item)
          : () => _openActions(item),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: analysisColor.withValues(alpha: 0.12),
                child: Icon(
                  item.isAnalyzed
                      ? Icons.notifications_active_rounded
                      : Icons.notifications_none_rounded,
                  color: analysisColor,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.sourceAppName,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      TextMapper.formatDateTime(context, item.receivedAt),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTokens.mutedText(context),
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: () => _openActions(item),
                icon: const Icon(Icons.more_horiz_rounded),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            preview,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'القناة: ${item.channel}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'الجهة المذكورة: ${_verificationText(item.mentionedEntity)}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'المرسل: ${_verificationText(item.sender)}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'الرابط: ${item.detectedUrl.isEmpty ? 'غير موجود' : 'موجود'}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
              if (item.isAnalyzed)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: analysisColor.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: analysisColor.withValues(alpha: 0.18),
                    ),
                  ),
                  child: Text(
                    '${TextMapper.label(context, item.result!.finalLabel)} • ${item.result!.finalScore}/100',
                    style: TextStyle(
                      color: analysisColor,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                )
              else
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: AppTokens.neutral.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    context.l10n.notAnalyzed,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    final l10n = context.l10n;

    return AppSurfaceCard(
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 32),
      child: Column(
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              color: AppTokens.brandCyan.withValues(alpha: 0.10),
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.inbox_outlined,
              size: 36,
              color: AppTokens.brandCyan,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            context.isArabic
                ? 'لا توجد إشعارات ملتقطة بعد'
                : l10n.notificationsEmptyTitle,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(
            context.isArabic
                ? 'فعّل صلاحية الإشعارات ليبدأ APG بتحليل الرسائل الواردة من التطبيقات.'
                : l10n.notificationsEmptySubtitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: AppTokens.mutedText(context),
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: widget.onRequestNotificationAccess,
            icon: const Icon(Icons.lock_open_rounded),
            label: const Text('تفعيل الوصول للإشعارات'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.removeListener(_handleSearch);
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filteredItems;

    return AppBackground(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            22,
            14,
            22,
            AppTokens.bottomNavContentPadding,
          ),
          children: [
            FadeSlideIn(
              beginOffset: const Offset(0, 8),
              child: PageIntroHeader(
                icon: Icons.notifications_active_rounded,
                title: context.isArabic
                    ? 'الإشعارات'
                    : context.l10n.notificationsInbox,
                subtitle: context.isArabic
                    ? 'التقاط الإشعارات وتحليلها، ثم مراجعتها في مكان واحد.'
                    : context.l10n.notificationsInboxSubtitle,
              ),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 50),
              beginOffset: const Offset(0, 8),
              child: _buildPermissionCard(),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 100),
              beginOffset: const Offset(0, 8),
              child: _buildSummaryCard(),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 140),
              beginOffset: const Offset(0, 8),
              child: _buildSearchAndFilters(),
            ),
            const SizedBox(height: 16),
            if (filtered.isEmpty)
              FadeSlideIn(
                delay: const Duration(milliseconds: 180),
                beginOffset: const Offset(0, 10),
                child: _buildEmptyState(),
              )
            else
              ...filtered.asMap().entries.map(
                (entry) => StaggeredItem(
                  key: ValueKey(entry.value.id),
                  index: entry.key > 6 ? 6 : entry.key,
                  beginOffset: const Offset(0, 12),
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _buildNotificationCard(entry.value),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
