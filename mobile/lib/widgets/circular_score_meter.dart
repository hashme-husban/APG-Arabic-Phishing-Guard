import 'dart:math' as math;
import 'package:flutter/material.dart';

class CircularScoreMeter extends StatelessWidget {
  final int score;
  final Color color;
  final String? caption;
  final double size;
  final double strokeWidth;
  final double? scoreFontSize;

  const CircularScoreMeter({
    super.key,
    required this.score,
    required this.color,
    this.caption,
    this.size = 102,
    this.strokeWidth = 8,
    this.scoreFontSize,
  });

  @override
  Widget build(BuildContext context) {
    final safeScore = score.clamp(0, 100);
    final effectiveStroke = strokeWidth.clamp(7.0, 9.0).toDouble();

    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: safeScore / 100),
      duration: const Duration(milliseconds: 1150),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) {
        return SizedBox(
          width: size,
          height: size,
          child: Stack(
            alignment: Alignment.center,
            children: [
              CustomPaint(
                size: Size.square(size),
                painter: _ScoreRingPainter(
                  progress: value,
                  color: color,
                  strokeWidth: effectiveStroke,
                  backgroundColor: Colors.white.withValues(alpha: 0.16),
                ),
              ),
              Padding(
                padding: EdgeInsets.all(effectiveStroke + 11),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '$safeScore',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize:
                            scoreFontSize ?? (size * 0.245).clamp(22.0, 48.0),
                        height: 1.0,
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      caption ?? 'درجة الخطورة',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 9.4,
                        height: 1.0,
                        fontWeight: FontWeight.w800,
                        color: Colors.white.withValues(alpha: 0.82),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ScoreRingPainter extends CustomPainter {
  final double progress;
  final Color color;
  final Color backgroundColor;
  final double strokeWidth;

  const _ScoreRingPainter({
    required this.progress,
    required this.color,
    required this.backgroundColor,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final center = rect.center;
    final radius = (size.shortestSide - strokeWidth) / 2;
    final bgPaint = Paint()
      ..color = backgroundColor
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final progressPaint = Paint()
      ..shader = SweepGradient(
        startAngle: -math.pi / 2,
        endAngle: math.pi * 1.5,
        colors: [
          color.withValues(alpha: 0.72),
          color,
          color.withValues(alpha: 0.88),
        ],
      ).createShader(Rect.fromCircle(center: center, radius: radius))
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, bgPaint);
    final sweep = (math.pi * 2) * progress.clamp(0.0, 1.0);
    if (sweep > 0) {
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        -math.pi / 2,
        sweep,
        false,
        progressPaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _ScoreRingPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.color != color ||
        oldDelegate.backgroundColor != backgroundColor ||
        oldDelegate.strokeWidth != strokeWidth;
  }
}
