import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';
import 'motion.dart';

/// A soft production-style switch used in APG settings.
///
/// It intentionally does not fill the whole control with the accent color.
/// The selected state keeps a calm track while the thumb carries the accent,
/// matching the requested polished look.
class AppSoftSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool>? onChanged;

  const AppSoftSwitch({
    super.key,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onChanged != null;
    final isDark = AppTokens.isDark(context);
    final textDirection = Directionality.of(context);
    final activeAlignment = textDirection == TextDirection.rtl
        ? Alignment.centerLeft
        : Alignment.centerRight;
    final inactiveAlignment = textDirection == TextDirection.rtl
        ? Alignment.centerRight
        : Alignment.centerLeft;

    // Keep the active state polished: the track stays calm/neutral and
    // only the thumb carries the accent color. This avoids the heavy
    // full-cyan/blue fill that was visually covering the switch.
    final trackColor = value
        ? (isDark
              ? const Color(0xFFF8FAFC).withValues(alpha: 0.16)
              : const Color(0xFFFFF7E8))
        : (isDark ? const Color(0xFF142235) : const Color(0xFFE9EEF5));
    final borderColor = value
        ? AppTokens.brand.withValues(alpha: isDark ? 0.58 : 0.42)
        : AppTokens.outline(context).withValues(alpha: 0.58);
    final thumbColor = value
        ? AppTokens.brand
        : (isDark ? const Color(0xFF667085) : Colors.white);
    final glowColor = value
        ? AppTokens.brand.withValues(alpha: isDark ? 0.20 : 0.18)
        : Colors.transparent;

    return Semantics(
      toggled: value,
      button: true,
      enabled: enabled,
      child: Opacity(
        opacity: enabled ? 1 : 0.48,
        child: PressableScale(
          onTap: enabled ? () => onChanged!(!value) : null,
          pressedScale: 0.96,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            width: 52,
            height: 30,
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: trackColor,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: borderColor, width: 1.2),
              boxShadow: value && enabled
                  ? [
                      BoxShadow(
                        color: glowColor,
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ]
                  : null,
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOutBack,
              alignment: value ? activeAlignment : inactiveAlignment,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: thumbColor,
                  boxShadow: [
                    BoxShadow(
                      color: value
                          ? AppTokens.brand.withValues(alpha: 0.22)
                          : Colors.black.withValues(
                              alpha: isDark ? 0.28 : 0.10,
                            ),
                      blurRadius: value ? 10 : 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
