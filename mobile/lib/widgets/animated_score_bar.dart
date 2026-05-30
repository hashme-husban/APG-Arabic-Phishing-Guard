import 'package:flutter/material.dart';

class AnimatedScoreBar extends StatelessWidget {
  final int score;
  final Color color;
  final double height;

  const AnimatedScoreBar({
    super.key,
    required this.score,
    required this.color,
    this.height = 10,
  });

  @override
  Widget build(BuildContext context) {
    final safeScore = score.clamp(0, 100);

    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: safeScore / 100),
      duration: const Duration(milliseconds: 840),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) {
        return ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: Container(
            height: height,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.13),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: color.withValues(alpha: 0.10)),
            ),
            alignment: AlignmentDirectional.centerStart,
            child: FractionallySizedBox(
              widthFactor: value,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      color.withValues(alpha: 0.64),
                      color,
                      color.withValues(alpha: 0.82),
                    ],
                    stops: const [0, 0.74, 1],
                  ),
                  borderRadius: BorderRadius.circular(999),
                  boxShadow: [
                    BoxShadow(
                      color: color.withValues(alpha: 0.20),
                      blurRadius: 12,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
