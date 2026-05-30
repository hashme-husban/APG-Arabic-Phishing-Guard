import 'dart:ui';

import 'package:flutter/material.dart';

import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';

enum ApgThreatLevel { safe, suspicious, dangerous }

class ApgThreatOverlay extends StatefulWidget {
  final AnalysisHistoryItem item;
  final VoidCallback onOpenDetails;
  final VoidCallback onDismiss;

  const ApgThreatOverlay({
    super.key,
    required this.item,
    required this.onOpenDetails,
    required this.onDismiss,
  });

  static ApgThreatLevel levelFor(String label) {
    switch (label.trim().toLowerCase()) {
      case 'safe':
      case 'legit':
      case 'benign':
        return ApgThreatLevel.safe;
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
      case 'high-risk':
      case 'malicious':
      case 'scam':
        return ApgThreatLevel.dangerous;
      default:
        return ApgThreatLevel.suspicious;
    }
  }

  @override
  State<ApgThreatOverlay> createState() => _ApgThreatOverlayState();
}

class _ApgThreatOverlayState extends State<ApgThreatOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _dangerPulseController;
  late final Animation<double> _dangerPulse;

  @override
  void initState() {
    super.initState();
    _dangerPulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 780),
    );
    _dangerPulse =
        TweenSequence<double>([
          TweenSequenceItem(tween: Tween<double>(begin: 0, end: 1), weight: 42),
          TweenSequenceItem(tween: Tween<double>(begin: 1, end: 0), weight: 58),
        ]).animate(
          CurvedAnimation(
            parent: _dangerPulseController,
            curve: Curves.easeOutCubic,
          ),
        );
    if (_isDangerous) {
      _dangerPulseController.forward();
    }
  }

  @override
  void didUpdateWidget(covariant ApgThreatOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_isDangerous &&
        oldWidget.item.id != widget.item.id &&
        !_dangerPulseController.isAnimating) {
      _dangerPulseController.forward(from: 0);
    } else if (!_isDangerous && _dangerPulseController.isAnimating) {
      _dangerPulseController.stop();
      _dangerPulseController.value = 0;
    }
  }

  @override
  void dispose() {
    _dangerPulseController.dispose();
    super.dispose();
  }

  bool get _isDangerous =>
      ApgThreatOverlay.levelFor(widget.item.result.finalLabel) ==
      ApgThreatLevel.dangerous;

  @override
  Widget build(BuildContext context) {
    final level = ApgThreatOverlay.levelFor(widget.item.result.finalLabel);
    final style = _ThreatStyle.forLevel(level);
    final explanation = _explanationFor(context, widget.item);

    return Directionality(
      textDirection: TextDirection.rtl,
      child: SafeArea(
        minimum: const EdgeInsets.fromLTRB(18, 10, 18, 0),
        child: Align(
          alignment: Alignment.topCenter,
          child: Material(
            elevation: 18,
            shadowColor: style.glow.withValues(alpha: style.shadowAlpha),
            color: Colors.transparent,
            child: AnimatedBuilder(
              animation: _dangerPulse,
              builder: (context, child) {
                final pulse = level == ApgThreatLevel.dangerous
                    ? _dangerPulse.value
                    : 0.0;
                return ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: BackdropFilter(
                    filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                    child: Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(maxWidth: 440),
                      padding: const EdgeInsets.fromLTRB(11, 10, 11, 9),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [style.backgroundStart, style.backgroundEnd],
                          begin: Alignment.topRight,
                          end: Alignment.bottomLeft,
                        ),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: style.accent.withValues(
                            alpha: style.borderAlpha + (pulse * 0.26),
                          ),
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: style.glow.withValues(
                              alpha: style.glowAlpha + (pulse * 0.07),
                            ),
                            blurRadius: style.glowBlur + (pulse * 4),
                            spreadRadius: style.glowSpread,
                            offset: const Offset(0, 16),
                          ),
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.30),
                            blurRadius: 24,
                            offset: const Offset(0, 13),
                          ),
                        ],
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              _ThreatIcon(
                                level: level,
                                style: style,
                                emphasis: pulse,
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
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
                                    if (explanation.isNotEmpty) ...[
                                      const SizedBox(height: 4),
                                      Text(
                                        explanation,
                                        maxLines: level == ApgThreatLevel.safe
                                            ? 1
                                            : 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: Theme.of(context)
                                            .textTheme
                                            .bodySmall
                                            ?.copyWith(
                                              color: const Color(0xFFD1DCEB),
                                              height: 1.22,
                                              fontWeight: FontWeight.w700,
                                            ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              _ScorePill(
                                score: widget.item.result.finalScore,
                                style: style,
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              Expanded(
                                flex: 5,
                                child: FilledButton.icon(
                                  onPressed: widget.onOpenDetails,
                                  style: FilledButton.styleFrom(
                                    backgroundColor: style.actionBackground(
                                      pulse,
                                    ),
                                    foregroundColor: _foregroundFor(
                                      style.accent,
                                    ),
                                    minimumSize: const Size(0, 34),
                                    tapTargetSize:
                                        MaterialTapTargetSize.shrinkWrap,
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 9,
                                      vertical: 7,
                                    ),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                  ),
                                  icon: const Icon(
                                    Icons.open_in_new_rounded,
                                    size: 17,
                                  ),
                                  label: const Text(
                                    '\u0639\u0631\u0636 \u0627\u0644\u062A\u0641\u0627\u0635\u064A\u0644',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                flex: 3,
                                child: OutlinedButton(
                                  onPressed: widget.onDismiss,
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: Colors.white,
                                    minimumSize: const Size(0, 34),
                                    tapTargetSize:
                                        MaterialTapTargetSize.shrinkWrap,
                                    side: BorderSide(
                                      color: Colors.white.withValues(
                                        alpha: 0.24,
                                      ),
                                    ),
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 7,
                                    ),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                  ),
                                  child: const Text(
                                    '\u0625\u063A\u0644\u0627\u0642',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  String _titleFor(ApgThreatLevel level) {
    switch (level) {
      case ApgThreatLevel.safe:
        return 'الرسالة تبدو مطمئنة';
      case ApgThreatLevel.suspicious:
        return 'رسالة تحتاج تحققًا';
      case ApgThreatLevel.dangerous:
        return 'تحذير: خطر تصيد مرتفع';
    }
  }

  Color _foregroundFor(Color color) {
    return color.computeLuminance() > 0.55
        ? const Color(0xFF111827)
        : Colors.white;
  }

  String _explanationFor(BuildContext context, AnalysisHistoryItem item) {
    switch (ApgThreatOverlay.levelFor(item.result.finalLabel)) {
      case ApgThreatLevel.safe:
        return 'لم تظهر مؤشرات خطورة واضحة.';
      case ApgThreatLevel.suspicious:
        return 'تحقق من المصدر قبل المتابعة.';
      case ApgThreatLevel.dangerous:
        return 'توجد مؤشرات قوية تستدعي الانتباه.';
    }
  }
}

class _ThreatIcon extends StatelessWidget {
  final ApgThreatLevel level;
  final _ThreatStyle style;
  final double emphasis;

  const _ThreatIcon({
    required this.level,
    required this.style,
    required this.emphasis,
  });

  @override
  Widget build(BuildContext context) {
    return Transform.scale(
      scale: 1 + (emphasis * 0.025),
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: style.accent.withValues(alpha: style.iconFillAlpha),
          border: Border.all(
            color: style.accent.withValues(
              alpha: style.iconBorderAlpha + (emphasis * 0.18),
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: style.glow.withValues(
                alpha: style.iconGlowAlpha + (emphasis * 0.10),
              ),
              blurRadius: style.iconGlowBlur + (emphasis * 3),
              spreadRadius: 0,
            ),
          ],
        ),
        child: Icon(_iconFor(level), color: style.accent, size: 22),
      ),
    );
  }

  IconData _iconFor(ApgThreatLevel level) {
    switch (level) {
      case ApgThreatLevel.safe:
        return Icons.verified_user_rounded;
      case ApgThreatLevel.suspicious:
        return Icons.report_problem_rounded;
      case ApgThreatLevel.dangerous:
        return Icons.gpp_maybe_rounded;
    }
  }
}

class _ScorePill extends StatelessWidget {
  final int score;
  final _ThreatStyle style;

  const _ScorePill({required this.score, required this.style});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 50),
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: style.accent.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: style.accent.withValues(alpha: 0.32)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '$score',
            style: TextStyle(
              color: style.accent,
              fontWeight: FontWeight.w900,
              fontSize: 17,
              height: 1,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            '/100',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.72),
              fontWeight: FontWeight.w800,
              fontSize: 10,
              height: 1,
            ),
          ),
        ],
      ),
    );
  }
}

class _ThreatStyle {
  final Color accent;
  final Color glow;
  final Color backgroundStart;
  final Color backgroundEnd;
  final double borderAlpha;
  final double glowAlpha;
  final double shadowAlpha;
  final double glowBlur;
  final double glowSpread;
  final double iconFillAlpha;
  final double iconBorderAlpha;
  final double iconGlowAlpha;
  final double iconGlowBlur;
  final double actionAlpha;

  const _ThreatStyle({
    required this.accent,
    required this.glow,
    required this.backgroundStart,
    required this.backgroundEnd,
    required this.borderAlpha,
    required this.glowAlpha,
    required this.shadowAlpha,
    required this.glowBlur,
    required this.glowSpread,
    required this.iconFillAlpha,
    required this.iconBorderAlpha,
    required this.iconGlowAlpha,
    required this.iconGlowBlur,
    required this.actionAlpha,
  });

  Color actionBackground(double pulse) {
    return accent.withValues(alpha: actionAlpha + (pulse * 0.08));
  }

  factory _ThreatStyle.forLevel(ApgThreatLevel level) {
    switch (level) {
      case ApgThreatLevel.safe:
        return const _ThreatStyle(
          accent: AppTokens.success,
          glow: AppTokens.brandCyan,
          backgroundStart: Color(0xEE071A20),
          backgroundEnd: Color(0xF206151D),
          borderAlpha: 0.24,
          glowAlpha: 0.08,
          shadowAlpha: 0.12,
          glowBlur: 20,
          glowSpread: -3,
          iconFillAlpha: 0.12,
          iconBorderAlpha: 0.30,
          iconGlowAlpha: 0.10,
          iconGlowBlur: 12,
          actionAlpha: 0.82,
        );
      case ApgThreatLevel.suspicious:
        return const _ThreatStyle(
          accent: Color(0xFFF59E0B),
          glow: Color(0xFFF97316),
          backgroundStart: Color(0xF3141414),
          backgroundEnd: Color(0xF31D1608),
          borderAlpha: 0.42,
          glowAlpha: 0.13,
          shadowAlpha: 0.18,
          glowBlur: 24,
          glowSpread: -3,
          iconFillAlpha: 0.17,
          iconBorderAlpha: 0.48,
          iconGlowAlpha: 0.16,
          iconGlowBlur: 14,
          actionAlpha: 0.86,
        );
      case ApgThreatLevel.dangerous:
        return const _ThreatStyle(
          accent: AppTokens.danger,
          glow: Color(0xFFEC4899),
          backgroundStart: Color(0xF41A0B13),
          backgroundEnd: Color(0xF4140710),
          borderAlpha: 0.58,
          glowAlpha: 0.22,
          shadowAlpha: 0.28,
          glowBlur: 30,
          glowSpread: -2,
          iconFillAlpha: 0.20,
          iconBorderAlpha: 0.62,
          iconGlowAlpha: 0.24,
          iconGlowBlur: 17,
          actionAlpha: 0.92,
        );
    }
  }
}
