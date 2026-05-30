import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/history_actions_sheet.dart';
import '../widgets/history_item_card.dart';
import '../widgets/page_intro_header.dart';
import '../widgets/apg_ui.dart';
import 'result_details_screen.dart';
import '../widgets/motion.dart';

class HistoryScreen extends StatefulWidget {
  final List<AnalysisHistoryItem> items;
  final ValueChanged<String> onDeleteHistoryItem;
  final VoidCallback? onStartAnalyze;
  final Future<void> Function()? onRefresh;
  final bool isRefreshing;

  const HistoryScreen({
    super.key,
    required this.items,
    required this.onDeleteHistoryItem,
    this.onStartAnalyze,
    this.onRefresh,
    this.isRefreshing = false,
  });

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _selectedFilter = 'all';

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_handleSearchChanged);
  }

  void _handleSearchChanged() => setState(() {});

  List<AnalysisHistoryItem> get _filteredItems {
    final query = _searchController.text.trim().toLowerCase();
    return widget.items.where((item) {
      final matchesFilter = _selectedFilter == 'all'
          ? true
          : item.result.finalLabel.toLowerCase() == _selectedFilter;
      final searchable = [
        item.sender,
        item.rawText,
        item.url,
        item.result.finalLabel,
        item.result.summary,
      ].join(' ').toLowerCase();
      return matchesFilter && (query.isEmpty || searchable.contains(query));
    }).toList();
  }

  int _countByLabel(String label) {
    return widget.items
        .where((e) => e.result.finalLabel.toLowerCase() == label)
        .length;
  }

  void _showSnack(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _copyItem(AnalysisHistoryItem item) async {
    final text = item.rawText.trim().isNotEmpty
        ? item.rawText.trim()
        : item.previewText;
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) _showSnack(context.l10n.textCopied);
  }

  Future<void> _copyUrl(AnalysisHistoryItem item) async {
    final url = item.url.trim().isNotEmpty
        ? item.url.trim()
        : item.result.detectedUrl.trim();
    if (url.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: url));
    if (mounted) _showSnack(context.l10n.urlCopied);
  }

  Future<void> _confirmDelete(AnalysisHistoryItem item) async {
    final l10n = context.l10n;
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (context) {
            return AlertDialog(
              title: Text(l10n.confirmDeleteHistoryItemTitle),
              content: Text(l10n.confirmDeleteHistoryItemMessage),
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
    widget.onDeleteHistoryItem(item.id);
    if (mounted) _showSnack(context.l10n.historyDeleted);
  }

  void _openDetails(AnalysisHistoryItem item) {
    if (kDebugMode) {
      debugPrint(
        'APG_SCORE_TRACE screen=history itemId=${item.id} '
        'analysisId=${item.result.remoteId} score=${item.result.finalScore}',
      );
    }
    Navigator.of(context).push(
      apgSlideFadeRoute(
        ResultDetailsScreen(
          item: item,
          onDelete: () => widget.onDeleteHistoryItem(item.id),
        ),
      ),
    );
  }

  void _openActions(AnalysisHistoryItem item) {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black54,
      builder: (sheetContext) {
        return HistoryActionsSheet(
          item: item,
          onOpenDetails: () {
            Navigator.of(sheetContext).pop();
            _openDetails(item);
          },
          onCopy: () async {
            Navigator.of(sheetContext).pop();
            await _copyItem(item);
          },
          onCopyUrl:
              (item.url.trim().isNotEmpty ||
                  item.result.detectedUrl.trim().isNotEmpty)
              ? () async {
                  Navigator.of(sheetContext).pop();
                  await _copyUrl(item);
                }
              : null,
          onDelete: () async {
            Navigator.of(sheetContext).pop();
            await _confirmDelete(item);
          },
        );
      },
    );
  }

  Widget _filterChip(String label, String value) {
    return ChoiceChip(
      label: Text(label),
      selected: _selectedFilter == value,
      onSelected: (_) => setState(() => _selectedFilter = value),
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
              labelText: l10n.searchHistory,
              hintText: l10n.searchHistoryHint,
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
                _filterChip(l10n.safe, 'safe'),
                _filterChip(l10n.suspicious, 'suspicious'),
                _filterChip(l10n.highRisk, 'phishing'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryRow() {
    final l10n = context.l10n;
    return AppSurfaceCard(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          _smallSummary(
            l10n.total,
            '${widget.items.length}',
            AppTokens.brandCyan,
          ),
          const SizedBox(width: 8),
          _smallSummary(
            l10n.safe,
            '${_countByLabel('safe')}',
            AppTokens.success,
          ),
          const SizedBox(width: 8),
          _smallSummary(
            l10n.suspicious,
            '${_countByLabel('suspicious')}',
            AppTokens.warning,
          ),
          const SizedBox(width: 8),
          _smallSummary(
            l10n.highRisk,
            '${_countByLabel('phishing')}',
            AppTokens.danger,
          ),
        ],
      ),
    );
  }

  Widget _smallSummary(String title, String value, Color color) {
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
            Text(
              value,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: color,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 3),
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

  Widget _buildEmptyFilteredState() {
    final l10n = context.l10n;
    return AppSurfaceCard(
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 28),
      child: Column(
        children: [
          Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(
              color: AppTokens.warning.withValues(alpha: 0.10),
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.search_off_rounded,
              size: 34,
              color: AppTokens.warning,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            l10n.matchingResultsTitle,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.matchingResultsSubtitle,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: AppTokens.mutedText(context),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.removeListener(_handleSearchChanged);
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filteredItems;
    final l10n = context.l10n;
    return AppBackground(
      child: SafeArea(
        child: RefreshIndicator(
          onRefresh: widget.onRefresh ?? () async {},
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(
              20,
              16,
              20,
              AppTokens.bottomNavContentPadding,
            ),
            children: [
              FadeSlideIn(
                beginOffset: const Offset(0, 8),
                child: PageIntroHeader(
                  icon: Icons.history_rounded,
                  title: l10n.history,
                  subtitle: l10n.historySubtitle,
                ),
              ),
              const SizedBox(height: 14),
              if (widget.isRefreshing) ...[
                LinearProgressIndicator(
                  minHeight: 3,
                  borderRadius: BorderRadius.circular(999),
                ),
                const SizedBox(height: 12),
              ],
              if (widget.items.isEmpty)
                FadeSlideIn(
                  delay: const Duration(milliseconds: 80),
                  beginOffset: const Offset(0, 10),
                  child: EmptyState(
                    title: l10n.historyEmptyTitle,
                    subtitle: l10n.historyEmptySubtitle,
                    icon: Icons.history_rounded,
                    action: widget.onStartAnalyze == null
                        ? null
                        : PrimaryButton(
                            label: l10n.analyzeMessageButton,
                            icon: Icons.search_rounded,
                            onPressed: widget.onStartAnalyze,
                          ),
                  ),
                )
              else ...[
                FadeSlideIn(
                  delay: const Duration(milliseconds: 60),
                  beginOffset: const Offset(0, 8),
                  child: _buildSearchAndFilters(),
                ),
                const SizedBox(height: 12),
                FadeSlideIn(
                  delay: const Duration(milliseconds: 100),
                  beginOffset: const Offset(0, 8),
                  child: _buildSummaryRow(),
                ),
                const SizedBox(height: 12),
                if (filtered.isEmpty)
                  _buildEmptyFilteredState()
                else
                  ...filtered.asMap().entries.map((entry) {
                    final item = entry.value;
                    return StaggeredItem(
                      key: ValueKey(item.id),
                      index: entry.key > 6 ? 6 : entry.key,
                      beginOffset: const Offset(0, 12),
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: HistoryItemCard(
                          item: item,
                          onTap: () => _openDetails(item),
                          onMore: () => _openActions(item),
                        ),
                      ),
                    );
                  }),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
