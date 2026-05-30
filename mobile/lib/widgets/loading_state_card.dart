import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/motion.dart';

class LoadingStateCard extends StatelessWidget {
  const LoadingStateCard({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AppSurfaceCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2.2,
                  color: AppTokens.brand,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  l10n.analyzingTitle,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            l10n.analyzingSubtitle,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 20),
          // Skeleton rows mimicking score + label layout
          const SkeletonBox(height: 11, borderRadius: 7),
          const SizedBox(height: 9),
          SkeletonBox(height: 11, width: 200, borderRadius: 7),
          const SizedBox(height: 9),
          SkeletonBox(height: 11, width: 140, borderRadius: 7),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: SkeletonBox(height: 48, borderRadius: 14),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: SkeletonBox(height: 48, borderRadius: 14),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
