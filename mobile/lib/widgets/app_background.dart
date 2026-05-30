import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';

class AppBackground extends StatelessWidget {
  final Widget child;

  const AppBackground({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final isDark = AppTokens.isDark(context);
    return Stack(
      fit: StackFit.expand,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: isDark
                  ? const [
                      Color(0xFF03131D),
                      Color(0xFF061725),
                      Color(0xFF03131D),
                    ]
                  : const [
                      Color(0xFFFFFFFF),
                      Color(0xFFF3F6FB),
                      Color(0xFFEAF0FF),
                    ],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        PositionedDirectional(
          top: -140,
          end: -120,
          child: _orb(
            330,
            AppTokens.brand.withValues(alpha: isDark ? 0.085 : 0.05),
          ),
        ),
        PositionedDirectional(
          top: 210,
          start: -155,
          child: _orb(
            310,
            AppTokens.brandCyan.withValues(alpha: isDark ? 0.042 : 0.035),
          ),
        ),
        PositionedDirectional(
          bottom: -170,
          end: 15,
          child: _orb(
            360,
            AppTokens.brandTeal.withValues(alpha: isDark ? 0.036 : 0.030),
          ),
        ),
        Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(
              painter: _CyberLinesPainter(
                lineColor: Colors.white.withValues(
                  alpha: isDark ? 0.009 : 0.006,
                ),
                accentColor: AppTokens.brand.withValues(
                  alpha: isDark ? 0.010 : 0.008,
                ),
              ),
            ),
          ),
        ),
        child,
      ],
    );
  }

  Widget _orb(double size, Color color) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color,
          boxShadow: [BoxShadow(color: color, blurRadius: 70, spreadRadius: 8)],
        ),
      ),
    );
  }
}

class _CyberLinesPainter extends CustomPainter {
  final Color lineColor;
  final Color accentColor;

  const _CyberLinesPainter({
    required this.lineColor,
    required this.accentColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = lineColor
      ..strokeWidth = 1;
    const gap = 54.0;
    for (double x = 0; x <= size.width; x += gap) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += gap) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }

    final slash = Paint()
      ..color = accentColor
      ..strokeWidth = 24
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(
      Offset(size.width * 0.85, -30),
      Offset(size.width * 0.22, size.height * 0.55),
      slash,
    );
    canvas.drawLine(
      Offset(size.width * 1.05, size.height * 0.18),
      Offset(size.width * 0.50, size.height * 0.70),
      slash,
    );
  }

  @override
  bool shouldRepaint(covariant _CyberLinesPainter oldDelegate) {
    return oldDelegate.lineColor != lineColor ||
        oldDelegate.accentColor != accentColor;
  }
}
