import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../services/local_storage_service.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import '../widgets/animated_score_bar.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/apg_ui.dart';
import '../widgets/circular_score_meter.dart';
import '../widgets/motion.dart';
import 'result_details_screen.dart';

class HomeScreen extends StatefulWidget {
  final List<AnalysisHistoryItem> history;
  final VoidCallback onStartAnalyze;
  final VoidCallback onOpenHistory;
  final ValueChanged<String> onDeleteHistoryItem;
  final bool notificationAccessGranted;
  final int monitoredAppsCount;

  const HomeScreen({
    super.key,
    required this.history,
    required this.onStartAnalyze,
    required this.onOpenHistory,
    required this.onDeleteHistoryItem,
    required this.notificationAccessGranted,
    required this.monitoredAppsCount,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  static const List<(String, String)> _securityTipPairs = [
    (
      'لا تشارك كلمات المرور أو رموز التحقق مع أي جهة.',
      'Never share passwords or verification codes with anyone.',
    ),
    (
      'تحقق من رابط الموقع قبل إدخال بياناتك.',
      'Check the website URL before entering your data.',
    ),
    (
      'لا تضغط على روابط مختصرة من مرسلين غير معروفين.',
      'Do not click shortened links from unknown senders.',
    ),
    (
      'البنك لن يطلب منك رمز OTP عبر رسالة.',
      'Your bank will never ask for an OTP via a message.',
    ),
  ];

  late int _tipIndex;
  late final AnimationController _heroGlowController;
  late final Animation<double> _heroGlow;

  @override
  void initState() {
    super.initState();
    _heroGlowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3600),
    )..repeat(reverse: true);
    _heroGlow = CurvedAnimation(
      parent: _heroGlowController,
      curve: Curves.easeInOut,
    );
    _tipIndex = _pickTipIndex();
    LocalStorageService.instance.setLastTipIndex(_tipIndex);
  }

  @override
  void dispose() {
    _heroGlowController.dispose();
    super.dispose();
  }

  int _pickTipIndex() {
    final previous = LocalStorageService.instance.getLastTipIndex();
    final random = math.Random(DateTime.now().microsecondsSinceEpoch);
    var next = random.nextInt(_securityTipPairs.length);
    if (next == previous) next = (next + 1) % _securityTipPairs.length;
    return next;
  }

  Future<void> _nextTip() async {
    setState(() {
      _tipIndex = (_tipIndex + 1) % _securityTipPairs.length;
    });
    await LocalStorageService.instance.setLastTipIndex(_tipIndex);
  }

  int _countByLabel(String label) => widget.history
      .where((e) => e.result.finalLabel.toLowerCase() == label)
      .length;

  bool get _hasAnalysisHistory => widget.history.isNotEmpty;

  int _averageRisk() {
    final recent = widget.history.take(10).toList();
    if (recent.isEmpty) return 0;
    final total = recent.fold<int>(
      0,
      (sum, item) => sum + item.result.finalScore,
    );
    final score = (total / recent.length).round();
    return widget.notificationAccessGranted
        ? score
        : (score + 12).clamp(0, 100);
  }

  Color _statusColor(int score) {
    if (score <= 30) return AppTokens.success;
    if (score <= 65) return AppTokens.warning;
    return AppTokens.danger;
  }

  String _statusLabel(BuildContext context, int score) {
    final l10n = context.l10n;
    if (score <= 30) return l10n.safe;
    if (score <= 65) return l10n.attentionStatus;
    return l10n.highRiskStatus;
  }

  Widget _protectionCard(BuildContext context) {
    final score = _hasAnalysisHistory ? _averageRisk() : 0;
    final color = _statusColor(score);
    return FadeSlideIn(
      beginOffset: const Offset(0, 16),
      child: AnimatedBuilder(
        animation: _heroGlow,
        builder: (context, child) {
          final glow = _heroGlow.value;
          return AppSurfaceCard(
            padding: EdgeInsets.zero,
            gradient: LinearGradient(
              colors: [
                const Color(0xFF071B26),
                Color.lerp(
                  const Color(0xFF1B1450),
                  color,
                  0.10 + (glow * 0.04),
                )!,
                const Color(0xFF031016),
              ],
              stops: const [0, 0.58, 1],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.12 + (glow * 0.04)),
            ),
            glow: true,
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      ProtectionPulseRing(
                        color: color,
                        size: _hasAnalysisHistory ? 108 : 98,
                        maxAlpha: _hasAnalysisHistory ? 0.28 : 0.22,
                        maxExpand: 28,
                        child: _hasAnalysisHistory
                            ? CircularScoreMeter(
                                score: score,
                                caption: context.l10n.averageRisk,
                                color: color,
                                size: 108,
                                strokeWidth: 8.5,
                              )
                            : Container(
                                width: 98,
                                height: 98,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: Colors.white.withValues(alpha: 0.08),
                                  border: Border.all(
                                    color: Colors.white.withValues(alpha: 0.16),
                                  ),
                                ),
                                child: Icon(
                                  Icons.shield_outlined,
                                  color: color,
                                  size: 42,
                                ),
                              ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              context.l10n.overallProtectionStatus,
                              style: Theme.of(context).textTheme.titleLarge
                                  ?.copyWith(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w900,
                                  ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _hasAnalysisHistory
                                  ? _statusLabel(context, score)
                                  : context.l10n.readyToStart,
                              style: Theme.of(context).textTheme.titleMedium
                                  ?.copyWith(
                                    color: color,
                                    fontWeight: FontWeight.w900,
                                  ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _hasAnalysisHistory
                                  ? context.l10n.reassuringHint
                                  : context.l10n.readyToStartHint,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(
                                    color: Colors.white.withValues(alpha: 0.88),
                                    height: 1.5,
                                  ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  AnimatedScoreBar(score: score, color: color, height: 11),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Icon(
                        Icons.biotech_rounded,
                        color: AppTokens.brandCyan,
                        size: 13,
                      ),
                      const SizedBox(width: 5),
                      Text(
                        'محرك الحماية APG',
                        style: TextStyle(
                          color: AppTokens.brandCyan,
                          fontWeight: FontWeight.w900,
                          fontSize: 11,
                          letterSpacing: 0.4,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: widget.notificationAccessGranted
                              ? AppTokens.success
                              : AppTokens.warning,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        widget.notificationAccessGranted
                            ? 'الحماية نشطة'
                            : 'الحماية جاهزة',
                        style: TextStyle(
                          color: widget.notificationAccessGranted
                              ? AppTokens.success
                              : AppTokens.warning,
                          fontWeight: FontWeight.w900,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      StatusBadge(
                        label: widget.notificationAccessGranted
                            ? context.l10n.protectionMonitoringActive
                            : context.l10n.monitoringAwaitingPermissionBadge,
                        color: widget.notificationAccessGranted
                            ? AppTokens.success
                            : AppTokens.warning,
                        icon: widget.notificationAccessGranted
                            ? Icons.verified_user_rounded
                            : Icons.lock_rounded,
                      ),
                      if (widget.notificationAccessGranted)
                        StatusBadge(
                          label: context.l10n.monitoredAppsCountLabel(
                            widget.monitoredAppsCount,
                          ),
                          color: AppTokens.brandCyan,
                          icon: Icons.apps_rounded,
                        ),
                      if (!_hasAnalysisHistory)
                        StatusBadge(
                          label: context.l10n.startFirstAnalysisCta,
                          color: AppTokens.brandCyan,
                          icon: Icons.search_rounded,
                        ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _mainCta(BuildContext context) {
    return FadeSlideIn(
      delay: const Duration(milliseconds: 120),
      beginOffset: const Offset(0, 12),
      child: PressableScale(
        onTap: widget.onStartAnalyze,
        haptic: true,
        pressedScale: 0.98,
        child: AppSurfaceCard(
          padding: const EdgeInsets.all(18),
          gradient: LinearGradient(
            colors: [
              AppTokens.brand.withValues(alpha: 0.92),
              AppTokens.brandAlt.withValues(alpha: 0.88),
            ],
            begin: AlignmentDirectional.topStart,
            end: AlignmentDirectional.bottomEnd,
          ),
          border: Border.all(color: Colors.white.withValues(alpha: 0.14)),
          glow: true,
          child: Row(
            children: [
              Container(
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.18),
                  ),
                ),
                child: const Icon(
                  Icons.search_rounded,
                  color: Colors.white,
                  size: 27,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      context.l10n.startFirstAnalysisCta,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      context.l10n.pasteMessageOrUrlHint,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.90),
                        height: 1.45,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              const Icon(
                Icons.arrow_back_rounded,
                color: Colors.white,
                size: 22,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tip(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.all(15),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AppTokens.brand.withValues(alpha: 0.13),
              borderRadius: BorderRadius.circular(15),
            ),
            child: Icon(
              Icons.tips_and_updates_rounded,
              color: AppTokens.brand,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        context.l10n.todaysTip,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: _nextTip,
                      child: Text(context.l10n.anotherTip),
                    ),
                  ],
                ),
                const SizedBox(height: 3),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 320),
                  child: Text(
                    context.isArabic
                        ? _securityTipPairs[_tipIndex].$1
                        : _securityTipPairs[_tipIndex].$2,
                    key: ValueKey(_tipIndex),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTokens.mutedText(context),
                      height: 1.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _stats(BuildContext context) {
    final l10n = context.l10n;
    final stats = [
      (l10n.total, widget.history.length, AppTokens.brandCyan),
      (l10n.safe, _countByLabel('safe'), AppTokens.success),
      (l10n.suspicious, _countByLabel('suspicious'), AppTokens.warning),
      (l10n.highRisk, _countByLabel('phishing'), AppTokens.danger),
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

  Widget _latest(BuildContext context) {
    final l10n = context.l10n;
    if (widget.history.isEmpty) {
      return EmptyState(
        title: l10n.noAnalysisYetTitle,
        subtitle: l10n.noAnalysisYetSubtitle,
        icon: Icons.shield_outlined,
        action: PrimaryButton(
          label: l10n.startFirstAnalysisCta,
          icon: Icons.search_rounded,
          onPressed: widget.onStartAnalyze,
        ),
      );
    }
    final latest = widget.history.first;
    final color = TextMapper.riskColor(latest.result.finalLabel);
    final preview = latest.previewText.isEmpty
        ? l10n.noTextAvailable
        : latest.previewText;
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      border: Border.all(color: color.withValues(alpha: 0.24)),
      onTap: () => Navigator.of(context).push(
        apgSlideFadeRoute(
          ResultDetailsScreen(
            item: latest,
            onDelete: () => widget.onDeleteHistoryItem(latest.id),
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: SectionHeader(
                  title: l10n.latestResult,
                  icon: Icons.fact_check_rounded,
                ),
              ),
              StatusBadge(
                label: TextMapper.label(context, latest.result.finalLabel),
                color: color,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            preview,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              height: 1.5,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Text(
                l10n.riskScoreLabel(latest.result.finalScore),
                style: TextStyle(color: color, fontWeight: FontWeight.w900),
              ),
              const Spacer(),
              Text(
                TextMapper.formatDateTime(context, latest.createdAt),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTokens.mutedText(context),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: () => Navigator.of(context).push(
                apgSlideFadeRoute(
                  ResultDetailsScreen(
                    item: latest,
                    onDelete: () => widget.onDeleteHistoryItem(latest.id),
                  ),
                ),
              ),
              icon: const Icon(Icons.open_in_new_rounded, size: 18),
              label: Text(l10n.viewDetailsLabel),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AppBackground(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            22,
            20,
            22,
            AppTokens.bottomNavContentPadding,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _protectionCard(context),
              const SizedBox(height: 18),
              _mainCta(context),
              const SizedBox(height: 18),
              FadeSlideIn(
                delay: const Duration(milliseconds: 200),
                child: _tip(context),
              ),
              const SizedBox(height: 16),
              FadeSlideIn(
                delay: const Duration(milliseconds: 280),
                child: _stats(context),
              ),
              const SizedBox(height: 16),
              FadeSlideIn(
                delay: const Duration(milliseconds: 340),
                child: _latest(context),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
