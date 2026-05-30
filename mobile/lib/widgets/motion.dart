import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_tokens.dart';

/// Tiny press feedback used across APG. It keeps the app feeling responsive
/// without making security UI look playful or distracting.
class PressableScale extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double pressedScale;
  final Duration duration;
  final BorderRadiusGeometry? borderRadius;
  final bool haptic;
  final HitTestBehavior behavior;

  const PressableScale({
    super.key,
    required this.child,
    this.onTap,
    this.pressedScale = 0.99,
    this.duration = const Duration(milliseconds: 120),
    this.borderRadius,
    this.haptic = false,
    this.behavior = HitTestBehavior.opaque,
  });

  @override
  State<PressableScale> createState() => _PressableScaleState();
}

class _PressableScaleState extends State<PressableScale> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (!mounted || widget.onTap == null) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final content = AnimatedScale(
      scale: _pressed ? widget.pressedScale : 1,
      duration: widget.duration,
      curve: Curves.easeOutCubic,
      child: widget.child,
    );

    if (widget.onTap == null) return content;

    return GestureDetector(
      behavior: widget.behavior,
      onTapDown: (_) => _setPressed(true),
      onTapCancel: () => _setPressed(false),
      onTapUp: (_) => _setPressed(false),
      onTap: () {
        if (widget.haptic) HapticFeedback.selectionClick();
        widget.onTap?.call();
      },
      child: content,
    );
  }
}

class FadeSlideIn extends StatelessWidget {
  final Widget child;
  final Duration duration;
  final Duration delay;
  final Offset beginOffset;
  final Curve curve;

  const FadeSlideIn({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 360),
    this.delay = Duration.zero,
    this.beginOffset = const Offset(0, 10),
    this.curve = Curves.easeOutCubic,
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: duration + delay,
      curve: Curves.linear,
      builder: (context, raw, child) {
        final delayMs = delay.inMilliseconds;
        final durationMs = duration.inMilliseconds;
        final start = delayMs == 0 ? 0.0 : delayMs / (delayMs + durationMs);
        final t = raw <= start
            ? 0.0
            : ((raw - start) / (1 - start)).clamp(0.0, 1.0);
        final eased = curve.transform(t);
        return Opacity(
          opacity: eased,
          child: Transform.translate(
            offset: Offset(
              beginOffset.dx * (1 - eased),
              beginOffset.dy * (1 - eased),
            ),
            child: child,
          ),
        );
      },
      child: child,
    );
  }
}

class StaggeredItem extends StatelessWidget {
  final int index;
  final Widget child;
  final Duration step;
  final Offset beginOffset;

  const StaggeredItem({
    super.key,
    required this.index,
    required this.child,
    this.step = const Duration(milliseconds: 36),
    this.beginOffset = const Offset(0, 6),
  });

  @override
  Widget build(BuildContext context) {
    return FadeSlideIn(
      delay: Duration(milliseconds: step.inMilliseconds * index),
      duration: const Duration(milliseconds: 280),
      beginOffset: beginOffset,
      child: child,
    );
  }
}

Route<T> apgSlideFadeRoute<T>(Widget page) {
  return PageRouteBuilder<T>(
    transitionDuration: const Duration(milliseconds: 300),
    reverseTransitionDuration: const Duration(milliseconds: 230),
    pageBuilder: (context, animation, secondaryAnimation) => page,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curved = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return FadeTransition(
        opacity: curved,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.028),
            end: Offset.zero,
          ).animate(curved),
          child: child,
        ),
      );
    },
  );
}

// ── Shimmer loading effect ────────────────────────────────────────────────────

/// Animated shimmer skeleton placeholder. Use [SkeletonBox] for the most common
/// rectangular skeleton shape, or wrap arbitrary widgets with [ShimmerEffect].
class ShimmerEffect extends StatefulWidget {
  final double width;
  final double height;
  final double borderRadius;

  const ShimmerEffect({
    super.key,
    this.width = double.infinity,
    this.height = 14,
    this.borderRadius = 8,
  });

  @override
  State<ShimmerEffect> createState() => _ShimmerEffectState();
}

class _ShimmerEffectState extends State<ShimmerEffect>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1300),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = AppTokens.isDark(context);
    final base =
        isDark ? const Color(0xFF0A2030) : const Color(0xFFE4EAF6);
    final glow =
        isDark ? const Color(0xFF1C4060) : const Color(0xFFF5F8FF);

    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        final t = _ctrl.value * 3 - 1;
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            gradient: LinearGradient(
              begin: Alignment(t - 1, 0),
              end: Alignment(t + 1, 0),
              colors: [base, glow, base],
            ),
          ),
        );
      },
    );
  }
}

/// Convenience alias for a single rectangular shimmer placeholder.
class SkeletonBox extends StatelessWidget {
  final double width;
  final double height;
  final double borderRadius;

  const SkeletonBox({
    super.key,
    this.width = double.infinity,
    this.height = 14,
    this.borderRadius = 8,
  });

  @override
  Widget build(BuildContext context) => ShimmerEffect(
    width: width,
    height: height,
    borderRadius: borderRadius,
  );
}

// ── Smooth expand / collapse ──────────────────────────────────────────────────

/// Animates its [child] in and out vertically. Toggle [expanded] to reveal or
/// collapse. Uses [AnimatedSize] so no controller is needed.
class AnimatedExpandCollapse extends StatelessWidget {
  final bool expanded;
  final Widget child;
  final Duration duration;
  final Curve curve;

  const AnimatedExpandCollapse({
    super.key,
    required this.expanded,
    required this.child,
    this.duration = const Duration(milliseconds: 260),
    this.curve = Curves.easeOutCubic,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedSize(
      duration: duration,
      curve: curve,
      alignment: Alignment.topCenter,
      child: ClipRect(
        child: expanded
            ? child
            : const SizedBox(width: double.infinity, height: 0),
      ),
    );
  }
}

/// Concentric pulsing rings that give a "live protection" feeling.
/// Manages its own AnimationController — no parent controller required.
/// Uses only Border drawing — no fill, no shadow — stays GPU-light.
class ProtectionPulseRing extends StatefulWidget {
  final Color color;
  final double size;
  final Widget child;
  final double maxExpand;
  final double maxAlpha;

  const ProtectionPulseRing({
    super.key,
    required this.color,
    required this.size,
    required this.child,
    this.maxExpand = 38,
    this.maxAlpha = 0.38,
  });

  @override
  State<ProtectionPulseRing> createState() => _ProtectionPulseRingState();
}

class _ProtectionPulseRingState extends State<ProtectionPulseRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2100),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, child) {
        final t1 = _ctrl.value;
        final t2 = (_ctrl.value + 0.5) % 1.0;
        return SizedBox(
          width: widget.size + widget.maxExpand + 4,
          height: widget.size + widget.maxExpand + 4,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Container(
                width: widget.size + t1 * widget.maxExpand,
                height: widget.size + t1 * widget.maxExpand,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: widget.color.withValues(
                      alpha: (1 - t1) * widget.maxAlpha,
                    ),
                    width: 1.5,
                  ),
                ),
              ),
              Container(
                width: widget.size + t2 * widget.maxExpand,
                height: widget.size + t2 * widget.maxExpand,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: widget.color.withValues(
                      alpha: (1 - t2) * widget.maxAlpha * 0.65,
                    ),
                    width: 1.0,
                  ),
                ),
              ),
              child!,
            ],
          ),
        );
      },
      child: Center(
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: widget.child,
        ),
      ),
    );
  }
}
