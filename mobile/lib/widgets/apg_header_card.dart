import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../theme/app_tokens.dart';
import 'apg_logo.dart';
import 'app_surface_card.dart';

class ApgHeaderCard extends StatelessWidget {
  final VoidCallback onPhishingExample;
  final VoidCallback onSuspiciousExample;
  final VoidCallback onSafeExample;

  const ApgHeaderCard({
    super.key,
    required this.onPhishingExample,
    required this.onSuspiciousExample,
    required this.onSafeExample,
  });

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      gradient: AppTokens.heroGradient(context),
      border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
      glow: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const APGLogo(
                size: 46,
                glowOpacity: 0.14,
                paddingFraction: 0.02,
                showContainer: false,
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'APG',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      context.isArabic
                          ? 'حماية ذكية من رسائل التصيد والروابط المشبوهة.'
                          : 'Smart protection from phishing messages and suspicious links.',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.84),
                        height: 1.45,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _ExampleChip(
                label: context.isArabic ? 'مثال آمن' : 'Safe example',
                color: AppTokens.success,
                onTap: onSafeExample,
              ),
              _ExampleChip(
                label: context.isArabic ? 'مثال مشبوه' : 'Suspicious example',
                color: AppTokens.warning,
                onTap: onSuspiciousExample,
              ),
              _ExampleChip(
                label: context.isArabic ? 'مثال خطر' : 'High-risk example',
                color: AppTokens.danger,
                onTap: onPhishingExample,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ExampleChip extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ExampleChip({
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.13),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: color.withValues(alpha: 0.25)),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w900,
            fontSize: 12,
          ),
        ),
      ),
    );
  }
}
