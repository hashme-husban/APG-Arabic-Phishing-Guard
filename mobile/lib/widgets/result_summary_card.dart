import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_result.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import 'animated_score_bar.dart';
import 'app_surface_card.dart';
import 'apg_ui.dart';

class ResultSummaryCard extends StatelessWidget {
  final AnalysisResult result;
  final VoidCallback onCopySummary;
  final VoidCallback onShareSummary;
  final VoidCallback? onOpenDetails;

  const ResultSummaryCard({
    super.key,
    required this.result,
    required this.onCopySummary,
    required this.onShareSummary,
    this.onOpenDetails,
  });

  bool get _isDanger =>
      result.finalLabel.toLowerCase() == 'phishing' || result.finalScore >= 61;

  String _title(BuildContext context) {
    final ar = context.isArabic;
    final label = result.finalLabel.toLowerCase();
    if (label == 'safe' || result.finalScore <= 30) {
      return ar ? 'لا يوجد دليل قوي على التصيد' : 'No strong phishing evidence';
    }
    if (label == 'suspicious' || result.finalScore <= 60) {
      return ar
          ? 'رسالة مشبوهة تحتاج انتباه'
          : 'Suspicious message needs attention';
    }
    return ar ? 'تم اكتشاف خطر تصيد مرتفع' : 'High phishing risk detected';
  }

  String _scoreHint(BuildContext context) {
    return context.isArabic
        ? 'الدرجة تعبر عن مستوى خطورة الرسالة من 0 إلى 100 بناءً على مؤشرات النص والرابط والمرسل.'
        : 'The score reflects message risk from 0 to 100 based on text, URL, and sender signals.';
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final color = TextMapper.riskColor(result.finalLabel);

    return AppSurfaceCard(
      padding: const EdgeInsets.all(20),
      gradient: AppTokens.riskGradient(result.finalLabel),
      border: Border.all(
        color: color.withValues(alpha: _isDanger ? 0.34 : 0.22),
      ),
      glow: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: color.withValues(alpha: 0.35),
                    width: 1.3,
                  ),
                ),
                child: Icon(_icon(), color: color, size: 30),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    StatusBadge(
                      label: TextMapper.label(context, result.finalLabel),
                      color: color,
                      icon: _icon(),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _title(context),
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      TextMapper.summary(context, result.summary),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppTokens.mutedText(context),
                        height: 1.55,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _scoreBox(
            context,
            context.isArabic ? 'نتيجة الخطورة' : 'Risk result',
            '${result.finalScore}/100',
            Icons.speed_rounded,
            color,
          ),
          const SizedBox(height: 12),
          Text(
            _scoreHint(context),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.45,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          AnimatedScoreBar(score: result.finalScore, color: color, height: 8),
          if (_isDanger) ...[
            const SizedBox(height: 14),
            _dangerActions(context),
          ],
          if (true) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _infoPill(
                  context,
                  '${context.isArabic ? 'مستوى الثقة' : 'Confidence level'}: ${(result.confidence * 100).toStringAsFixed(1)}%',
                ),
                if (result.claimedEntity.trim().isNotEmpty)
                  _infoPill(
                    context,
                    '${l10n.claimedEntity}: ${result.claimedEntity}',
                  ),
                if (result.channel.trim().isNotEmpty)
                  _infoPill(
                    context,
                    '${l10n.channel}: ${TextMapper.channel(context, result.channel)}',
                  ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          Wrap(
            spacing: 9,
            runSpacing: 9,
            children: [
              OutlinedButton.icon(
                onPressed: onCopySummary,
                icon: const Icon(Icons.copy_rounded),
                label: Text(l10n.copy),
              ),
              OutlinedButton.icon(
                onPressed: onShareSummary,
                icon: const Icon(Icons.share_rounded),
                label: Text(l10n.share),
              ),
              if (onOpenDetails != null)
                FilledButton.icon(
                  onPressed: onOpenDetails,
                  icon: const Icon(Icons.open_in_new_rounded),
                  label: Text(l10n.details),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _scoreBox(
    BuildContext context,
    String title,
    String value,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context).withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.70),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 19),
          const SizedBox(height: 8),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 2),
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _dangerActions(BuildContext context) {
    final items = context.isArabic
        ? [
            'لا تضغط على الرابط',
            'لا تدخل رمز OTP',
            'لا تشارك بياناتك البنكية',
            'احذف الرسالة فورًا',
            'تواصل مع الجهة الرسمية إن لزم',
          ]
        : [
            'Do not open the link',
            'Do not enter OTP codes',
            'Do not share banking data',
            'Delete the message immediately',
            'Contact the official entity if needed',
          ];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
      decoration: BoxDecoration(
        color: AppTokens.danger.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTokens.danger.withValues(alpha: 0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.isArabic ? 'ماذا أفعل الآن؟' : 'What should I do now?',
            style: const TextStyle(
              color: AppTokens.danger,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 12),
          ...items.map(
            (e) => Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                children: [
                  const Icon(
                    Icons.block_rounded,
                    color: AppTokens.danger,
                    size: 16,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      e,
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        height: 1.45,
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

  Widget _infoPill(BuildContext context, String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.60),
        ),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: AppTokens.mutedText(context),
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  IconData _icon() {
    switch (result.finalLabel.toLowerCase()) {
      case 'phishing':
        return Icons.gpp_bad_rounded;
      case 'suspicious':
        return Icons.report_problem_rounded;
      case 'safe':
        return Icons.verified_rounded;
      default:
        return Icons.analytics_rounded;
    }
  }
}
