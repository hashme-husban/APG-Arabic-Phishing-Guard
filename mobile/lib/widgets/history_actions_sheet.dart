import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import 'motion.dart';

class HistoryActionsSheet extends StatelessWidget {
  final AnalysisHistoryItem item;
  final VoidCallback onOpenDetails;
  final VoidCallback onCopy;
  final VoidCallback? onCopyUrl;
  final VoidCallback onDelete;

  const HistoryActionsSheet({
    super.key,
    required this.item,
    required this.onOpenDetails,
    required this.onCopy,
    this.onCopyUrl,
    required this.onDelete,
  });

  Widget _actionTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return PressableScale(
      onTap: onTap,
      pressedScale: 0.97,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: AppTokens.surfaceAlt(context).withValues(alpha: 0.62),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppTokens.outline(context).withValues(alpha: 0.58),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: color, size: 21),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    textAlign: TextAlign.right,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      height: 1.35,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    textAlign: TextAlign.right,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppTokens.mutedText(context),
                      height: 1.45,
                      fontWeight: FontWeight.w700,
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

  @override
  Widget build(BuildContext context) {
    final color = TextMapper.riskColor(item.result.finalLabel);
    final preview = item.previewText.isEmpty
        ? context.l10n.noTextAvailable
        : item.previewText;

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 28),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: AppTokens.surfaceGradient(context),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: AppTokens.outline(context).withValues(alpha: 0.85),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.30),
                blurRadius: 26,
                offset: const Offset(0, 14),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 46,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppTokens.outline(context).withValues(alpha: 0.70),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: color.withValues(alpha: 0.24)),
                    ),
                    child: Text(
                      TextMapper.label(context, item.result.finalLabel),
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      preview,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.right,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        height: 1.45,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _actionTile(
                context: context,
                icon: Icons.open_in_new_rounded,
                title: 'عرض التفاصيل',
                subtitle: 'فتح تفاصيل التحليل لهذه الرسالة.',
                color: AppTokens.brand,
                onTap: onOpenDetails,
              ),
              const SizedBox(height: 10),
              _actionTile(
                context: context,
                icon: Icons.copy_rounded,
                title: 'نسخ النص',
                subtitle: 'نسخ نص الرسالة إلى الحافظة.',
                color: AppTokens.warning,
                onTap: onCopy,
              ),
              const SizedBox(height: 10),
              if (onCopyUrl != null) ...[
                _actionTile(
                  context: context,
                  icon: Icons.link_rounded,
                  title: 'نسخ الرابط',
                  subtitle: 'نسخ الرابط المكتشف إلى الحافظة.',
                  color: AppTokens.brandCyan,
                  onTap: onCopyUrl!,
                ),
                const SizedBox(height: 10),
              ],
              _actionTile(
                context: context,
                icon: Icons.delete_outline_rounded,
                title: 'حذف من السجل',
                subtitle: 'إزالة هذا العنصر من السجل المحلي.',
                color: AppTokens.danger,
                onTap: onDelete,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
