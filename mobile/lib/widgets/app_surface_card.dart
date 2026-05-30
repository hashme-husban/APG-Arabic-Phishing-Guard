import 'dart:ui';
import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';
import 'motion.dart';

class AppSurfaceCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Gradient? gradient;
  final Color? color;
  final double radius;
  final Border? border;
  final bool glow;
  final VoidCallback? onTap;

  const AppSurfaceCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.gradient,
    this.color,
    this.radius = AppTokens.radiusLg,
    this.border,
    this.glow = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = AppTokens.isDark(context);
    final content = ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: isDark ? 7.0 : 3.0,
          sigmaY: isDark ? 7.0 : 3.0,
        ),
        child: Container(
          width: double.infinity,
          padding: padding,
          decoration: BoxDecoration(
            color: gradient == null ? color : null,
            gradient:
                gradient ??
                (color == null ? AppTokens.surfaceGradient(context) : null),
            borderRadius: BorderRadius.circular(radius),
            border:
                border ??
                Border.all(
                  color: AppTokens.outline(
                    context,
                  ).withValues(alpha: isDark ? 0.58 : 0.82),
                ),
            boxShadow: [
              ...AppTokens.cardShadow(context),
              if (isDark)
                BoxShadow(
                  color: AppTokens.brandCyan.withValues(alpha: 0.025),
                  blurRadius: 30,
                  offset: const Offset(0, 16),
                ),
              if (glow)
                BoxShadow(
                  color: AppTokens.brandCyan.withValues(
                    alpha: isDark ? 0.10 : 0.06,
                  ),
                  blurRadius: 34,
                  spreadRadius: -6,
                  offset: const Offset(0, 14),
                ),
            ],
          ),
          child: child,
        ),
      ),
    );

    if (onTap == null) return content;
    return PressableScale(
      onTap: onTap,
      haptic: true,
      borderRadius: BorderRadius.circular(radius),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(radius),
          splashColor: AppTokens.brand.withValues(alpha: 0.06),
          highlightColor: AppTokens.brand.withValues(alpha: 0.035),
          child: content,
        ),
      ),
    );
  }
}
