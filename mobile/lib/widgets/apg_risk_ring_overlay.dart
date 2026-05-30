import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';

import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';

enum ApgRiskLevel { safe, suspicious, dangerous }

class ApgRiskRingOverlay extends StatefulWidget {
  final AnalysisHistoryItem item;
  final VoidCallback onOpenDetails;
  final VoidCallback onDismiss;

  const ApgRiskRingOverlay({
    super.key,
    required this.item,
    required this.onOpenDetails,
    required this.onDismiss,
  });

  static ApgRiskLevel levelFor(String label) {
    switch (label.trim().toLowerCase()) {
      case 'safe':
      case 'legit':
      case 'benign':
      case 'low_risk':
      case 'low-risk':
        return ApgRiskLevel.safe;
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
      case 'high-risk':
      case 'malicious':
      case 'scam':
        return ApgRiskLevel.dangerous;
      default:
        return ApgRiskLevel.suspicious;
    }
  }

  @override
  State<ApgRiskRingOverlay> createState() => _ApgRiskRingOverlayState();
}

class _ApgRiskRingOverlayState extends State<ApgRiskRingOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _score;
  late final Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 920),
    );
    _configureAnimations();
    _controller.forward(from: 0);
  }

  @override
  void didUpdateWidget(covariant ApgRiskRingOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.id != widget.item.id ||
        oldWidget.item.result.finalScore != widget.item.result.finalScore) {
      _configureAnimations();
      _controller.forward(from: 0);
    }
  }

  void _configureAnimations() {
    final target = widget.item.result.finalScore.clamp(0, 100) / 100;
    _score = Tween<double>(
      begin: 0,
      end: target,
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));
    _pulse = TweenSequence<double>(
      [
        TweenSequenceItem(tween: Tween<double>(begin: 0, end: 1), weight: 45),
        TweenSequenceItem(tween: Tween<double>(begin: 1, end: 0), weight: 55),
      ],
    ).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final level = ApgRiskRingOverlay.levelFor(widget.item.result.finalLabel);
    final style = _RiskRingStyle.forLevel(level);

    return Directionality(
      textDirection: TextDirection.rtl,
      child: SafeArea(
        minimum: const EdgeInsets.fromLTRB(16, 8, 16, 0),
        child: Align(
          alignment: Alignment.topCenter,
          child: Material(
            color: Colors.transparent,
            elevation: 18,
            shadowColor: style.glow.withValues(alpha: 0.28),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (context, child) {
                    final pulse = level == ApgRiskLevel.dangerous
                        ? _pulse.value
                        : 0.0;
                    return Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(maxWidth: 430),
                      padding: const EdgeInsets.fromLTRB(11, 10, 11, 10),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [style.backgroundStart, style.backgroundEnd],
                          begin: Alignment.topRight,
                          end: Alignment.bottomLeft,
                        ),
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: style.accent.withValues(
                            alpha: 0.34 + (pulse * 0.22),
                          ),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: style.glow.withValues(
                              alpha: style.glowAlpha + (pulse * 0.08),
                            ),
                            blurRadius: 28 + (pulse * 6),
                            offset: const Offset(0, 14),
                          ),
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.28),
                            blurRadius: 24,
                            offset: const Offset(0, 12),
                          ),
                        ],
                      ),
                      child: Row(
                        children: [
                          _AnimatedRiskRing(
                            progress: _score.value,
                            score: widget.item.result.finalScore,
                            style: style,
                          ),
                          const SizedBox(width: 11),
                          Expanded(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Container(
                                      width: 24,
                                      height: 24,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        color: style.accent.withValues(
                                          alpha: 0.16,
                                        ),
                                      ),
                                      child: Icon(
                                        _iconFor(level),
                                        color: style.accent,
                                        size: 15,
                                      ),
                                    ),
                                    const SizedBox(width: 7),
                                    Expanded(
                                      child: Text(
                                        _titleFor(level),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleSmall
                                            ?.copyWith(
                                              color: Colors.white,
                                              fontWeight: FontWeight.w900,
                                              height: 1.15,
                                            ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _reasonFor(level),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context).textTheme.bodySmall
                                      ?.copyWith(
                                        color: const Color(0xFFD6E3F3),
                                        height: 1.25,
                                        fontWeight: FontWeight.w700,
                                      ),
                                ),
                                const SizedBox(height: 8),
                                Align(
                                  alignment: AlignmentDirectional.centerStart,
                                  child: FilledButton.icon(
                                    onPressed: widget.onOpenDetails,
                                    style: FilledButton.styleFrom(
                                      backgroundColor: style.accent,
                                      foregroundColor:
                                          style.accent.computeLuminance() > 0.55
                                          ? const Color(0xFF101828)
                                          : Colors.white,
                                      minimumSize: const Size(0, 32),
                                      tapTargetSize:
                                          MaterialTapTargetSize.shrinkWrap,
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 10,
                                        vertical: 7,
                                      ),
                                      shape: RoundedRectangleBorder(
                                        borderRadius: BorderRadius.circular(11),
                                      ),
                                    ),
                                    icon: const Icon(
                                      Icons.open_in_new_rounded,
                                      size: 16,
                                    ),
                                    label: const Text(
                                      'عرض التفاصيل',
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            onPressed: widget.onDismiss,
                            visualDensity: VisualDensity.compact,
                            tooltip: 'إغلاق',
                            icon: Icon(
                              Icons.close_rounded,
                              color: Colors.white.withValues(alpha: 0.82),
                              size: 20,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  IconData _iconFor(ApgRiskLevel level) {
    switch (level) {
      case ApgRiskLevel.safe:
        return Icons.verified_user_rounded;
      case ApgRiskLevel.suspicious:
        return Icons.shield_rounded;
      case ApgRiskLevel.dangerous:
        return Icons.gpp_maybe_rounded;
    }
  }

  String _titleFor(ApgRiskLevel level) {
    switch (level) {
      case ApgRiskLevel.safe:
        return 'تم الفحص';
      case ApgRiskLevel.suspicious:
        return 'رسالة تحتاج تحققًا';
      case ApgRiskLevel.dangerous:
        return 'تحذير أمني';
    }
  }

  String _reasonFor(ApgRiskLevel level) {
    switch (level) {
      case ApgRiskLevel.safe:
        return 'لا توجد مؤشرات خطيرة.';
      case ApgRiskLevel.suspicious:
        return 'تحقق من الرسالة قبل فتح الرابط.';
      case ApgRiskLevel.dangerous:
        return 'لا تفتح الرابط أو تشارك بيانات حساسة.';
    }
  }
}

class _AnimatedRiskRing extends StatelessWidget {
  final double progress;
  final int score;
  final _RiskRingStyle style;

  const _AnimatedRiskRing({
    required this.progress,
    required this.score,
    required this.style,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 58,
      height: 58,
      child: CustomPaint(
        painter: _RiskRingPainter(
          progress: progress,
          accent: style.accent,
          track: Colors.white.withValues(alpha: 0.13),
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${(score.clamp(0, 100) * progress).round()}',
                style: TextStyle(
                  color: style.accent,
                  fontSize: 17,
                  height: 1,
                  fontWeight: FontWeight.w900,
                ),
              ),
              Text(
                'APG',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.70),
                  fontSize: 8.5,
                  height: 1.1,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RiskRingPainter extends CustomPainter {
  final double progress;
  final Color accent;
  final Color track;

  const _RiskRingPainter({
    required this.progress,
    required this.accent,
    required this.track,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final center = rect.center;
    final radius = math.min(size.width, size.height) / 2 - 4;
    final trackPaint = Paint()
      ..color = track
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;
    final ringPaint = Paint()
      ..shader = SweepGradient(
        colors: [
          accent.withValues(alpha: 0.42),
          accent,
          Colors.white.withValues(alpha: 0.84),
          accent,
        ],
        stops: const [0, 0.55, 0.78, 1],
      ).createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, trackPaint);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      math.pi * 2 * progress.clamp(0, 1),
      false,
      ringPaint,
    );
  }

  @override
  bool shouldRepaint(covariant _RiskRingPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.accent != accent ||
        oldDelegate.track != track;
  }
}

class _RiskRingStyle {
  final Color accent;
  final Color glow;
  final Color backgroundStart;
  final Color backgroundEnd;
  final double glowAlpha;

  const _RiskRingStyle({
    required this.accent,
    required this.glow,
    required this.backgroundStart,
    required this.backgroundEnd,
    required this.glowAlpha,
  });

  factory _RiskRingStyle.forLevel(ApgRiskLevel level) {
    switch (level) {
      case ApgRiskLevel.safe:
        return const _RiskRingStyle(
          accent: AppTokens.success,
          glow: AppTokens.brandCyan,
          backgroundStart: Color(0xEE071A20),
          backgroundEnd: Color(0xF205121B),
          glowAlpha: 0.10,
        );
      case ApgRiskLevel.suspicious:
        return const _RiskRingStyle(
          accent: Color(0xFFF59E0B),
          glow: Color(0xFFF97316),
          backgroundStart: Color(0xF2151412),
          backgroundEnd: Color(0xF21F1607),
          glowAlpha: 0.17,
        );
      case ApgRiskLevel.dangerous:
        return const _RiskRingStyle(
          accent: Color(0xFFFF4D6D),
          glow: Color(0xFFEC4899),
          backgroundStart: Color(0xF31A0912),
          backgroundEnd: Color(0xF3120710),
          glowAlpha: 0.24,
        );
    }
  }
}
