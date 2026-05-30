import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import 'app_surface_card.dart';
import 'apg_ui.dart';

class HistoryItemCard extends StatelessWidget {
  final AnalysisHistoryItem item;
  final VoidCallback onTap;
  final VoidCallback onMore;

  const HistoryItemCard({
    super.key,
    required this.item,
    required this.onTap,
    required this.onMore,
  });

  @override
  Widget build(BuildContext context) {
    final color = TextMapper.riskColor(item.result.finalLabel);
    final preview = item.previewText.isEmpty
        ? context.l10n.noTextAvailable
        : item.previewText;
    final intentBadge = _intentBadge();
    return AppSurfaceCard(
      padding: EdgeInsets.zero,
      border: Border.all(color: color.withValues(alpha: 0.18)),
      onTap: onTap,
      child: IntrinsicHeight(
        child: Row(
          children: [
            Container(
              width: 3,
              decoration: BoxDecoration(
                color: color,
                borderRadius: const BorderRadiusDirectional.only(
                  topStart: Radius.circular(AppTokens.radiusLg),
                  bottomStart: Radius.circular(AppTokens.radiusLg),
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 7,
                      runSpacing: 7,
                      children: [
                        StatusBadge(
                          label: TextMapper.label(
                            context,
                            item.result.finalLabel,
                          ),
                          color: color,
                          icon: _icon(item.result.finalLabel),
                        ),
                        if (intentBadge != null)
                          StatusBadge(
                            label: intentBadge,
                            color: AppTokens.brandCyan,
                            icon: Icons.sell_rounded,
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${context.l10n.score}: ${item.result.finalScore}/100',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w900),
                          ),
                        ),
                        IconButton(
                          onPressed: onMore,
                          tooltip: context.l10n.actions,
                          visualDensity: VisualDensity.compact,
                          icon: const Icon(Icons.more_horiz_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      preview,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        height: 1.55,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        if (item.sender.trim().isNotEmpty)
                          Expanded(
                            child: Text(
                              '${context.l10n.sender}: ${item.sender}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(
                                    color: AppTokens.mutedText(context),
                                    fontWeight: FontWeight.w700,
                                  ),
                            ),
                          )
                        else
                          const Spacer(),
                        const SizedBox(width: 10),
                        Text(
                          TextMapper.formatDateTime(context, item.createdAt),
                          style: Theme.of(context).textTheme.bodySmall
                              ?.copyWith(
                                color: AppTokens.mutedText(context),
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _icon(String label) {
    switch (label.toLowerCase()) {
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
      case 'malicious':
        return Icons.gpp_bad_rounded;
      case 'warning':
      case 'suspicious':
        return Icons.warning_rounded;
      case 'safe':
        return Icons.verified_rounded;
      default:
        return Icons.analytics_rounded;
    }
  }

  String? _intentBadge() {
    final intent =
        item.result.messageIntent?.toLowerCase().trim() ??
        item.messageIntent?.toLowerCase().trim() ??
        '';
    final text =
        '${item.rawText} ${item.url} ${item.result.detectedUrl} ${item.result.reasons.join(' ')}'
            .toLowerCase();
    if (intent.contains('otp') || text.contains('otp')) return 'OTP';
    if (intent.contains('payment') ||
        intent.contains('financial') ||
        text.contains('payment') ||
        text.contains('دفع')) {
      return 'دفع';
    }
    if (intent.contains('phishing') ||
        text.contains('credential') ||
        text.contains('تصيد')) {
      return 'تصيد';
    }
    if (intent.contains('advertisement')) return 'إعلان';
    if (item.url.trim().isNotEmpty ||
        item.result.detectedUrl.trim().isNotEmpty) {
      return 'رابط';
    }
    return null;
  }
}
