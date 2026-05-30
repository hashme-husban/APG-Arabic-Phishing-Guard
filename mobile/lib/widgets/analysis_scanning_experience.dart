import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';

class AnalysisScanningExperience extends StatefulWidget {
  final bool isUrlAnalysis;

  const AnalysisScanningExperience({super.key, required this.isUrlAnalysis});

  @override
  State<AnalysisScanningExperience> createState() =>
      _AnalysisScanningExperienceState();
}

class _AnalysisScanningExperienceState extends State<AnalysisScanningExperience>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  int _activeStage = 0;

  List<String> get _stages => widget.isUrlAnalysis
      ? [
          'استخراج الرابط',
          'فحص السمعة',
          'فتح الرابط في بيئة آمنة',
          'مراقبة سلوك الصفحة',
          'تشغيل محرك المخاطر',
          'بناء النتيجة',
        ]
      : [
          'تهيئة النص العربي',
          'استخراج المؤشرات',
          'تشغيل محرك المخاطر',
          'بناء النتيجة',
        ];

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
    _progressStages();
  }

  Future<void> _progressStages() async {
    final stepMs = widget.isUrlAnalysis ? 860 : 680;
    for (var i = 0; i < _stages.length; i++) {
      await Future.delayed(Duration(milliseconds: stepMs));
      if (!mounted) return;
      setState(() => _activeStage = i);
    }
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
      builder: (context, _) => _buildCard(context, _ctrl.value),
    );
  }

  Widget _buildCard(BuildContext context, double t) {
    final pulse = math.sin(t * math.pi * 2);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 22),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF071B26),
            Color.lerp(
              const Color(0xFF0A2535),
              AppTokens.brandCyan,
              0.05 + pulse * 0.025,
            )!,
            const Color(0xFF031016),
          ],
          stops: const [0, 0.52, 1],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(AppTokens.radiusMd),
        border: Border.all(
          color: AppTokens.brandCyan.withValues(alpha: 0.28 + pulse * 0.12),
        ),
        boxShadow: [
          BoxShadow(
            color: AppTokens.brandCyan.withValues(alpha: 0.08 + pulse * 0.04),
            blurRadius: 20,
            spreadRadius: -4,
          ),
        ],
      ),
      child: Column(
        children: [
          _buildCore(t),
          const SizedBox(height: 6),
          Text(
            widget.isUrlAnalysis
                ? 'APG يفحص الرابط في بيئة آمنة'
                : 'APG يحلل الرسالة',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.90),
              fontWeight: FontWeight.w900,
              fontSize: 14,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'محرك APG للمخاطر يعمل...',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppTokens.brandCyan.withValues(alpha: 0.78),
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 18),
          _buildStages(),
        ],
      ),
    );
  }

  Widget _buildCore(double t) {
    final angle = t * math.pi * 2;
    return SizedBox(
      width: 96,
      height: 96,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Outer pulsing halo
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: AppTokens.brandCyan.withValues(
                  alpha: 0.16 + math.sin(angle) * 0.08,
                ),
                width: 1.0,
              ),
            ),
          ),
          // Radar sweep ring
          CustomPaint(
            size: const Size(76, 76),
            painter: _RadarSweepPainter(angle: angle),
          ),
          // Inner APG mark
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppTokens.brandCyan.withValues(alpha: 0.12),
              border: Border.all(
                color: AppTokens.brandCyan.withValues(alpha: 0.45),
                width: 1.4,
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(9),
              child: Image.asset(
                'assets/branding/apg_logo_transparent.png',
                fit: BoxFit.contain,
                filterQuality: FilterQuality.high,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStages() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: _stages.asMap().entries.map((entry) {
        final index = entry.key;
        final label = entry.value;
        final isActive = index == _activeStage;
        final isDone = index < _activeStage;

        final color = isDone
            ? AppTokens.success
            : isActive
            ? AppTokens.brandCyan
            : Colors.white.withValues(alpha: 0.26);

        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              // Status indicator
              Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: color.withValues(alpha: 0.14),
                  border: Border.all(
                    color: color.withValues(alpha: isDone ? 0.60 : 0.38),
                    width: isDone ? 1.5 : 1.0,
                  ),
                ),
                child: Center(
                  child: isDone
                      ? Icon(
                          Icons.check_rounded,
                          color: AppTokens.success,
                          size: 12,
                        )
                      : isActive
                      ? SizedBox(
                          width: 10,
                          height: 10,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.5,
                            color: AppTokens.brandCyan,
                          ),
                        )
                      : Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.white.withValues(alpha: 0.24),
                          ),
                        ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  label,
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    color: color,
                    fontWeight: isActive ? FontWeight.w900 : FontWeight.w700,
                    fontSize: isActive ? 13.5 : 13.0,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }
}

class _RadarSweepPainter extends CustomPainter {
  final double angle;

  const _RadarSweepPainter({required this.angle});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide / 2 - 1;

    // Background ring
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..color = AppTokens.brandCyan.withValues(alpha: 0.22)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2,
    );

    // Sweep trail (12 segments fading out)
    const trailLength = 1.6;
    const segments = 14;
    final segPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round;

    for (var i = 0; i < segments; i++) {
      final frac = i / segments;
      final segStart = angle - trailLength + frac * trailLength;
      segPaint.color = AppTokens.brandCyan.withValues(
        alpha: (frac * 0.62).clamp(0.0, 1.0),
      );
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        segStart,
        trailLength / segments,
        false,
        segPaint,
      );
    }

    // Leading bright dot
    final dotX = center.dx + radius * math.cos(angle);
    final dotY = center.dy + radius * math.sin(angle);
    canvas.drawCircle(
      Offset(dotX, dotY),
      3.2,
      Paint()..color = AppTokens.brandCyan,
    );
    canvas.drawCircle(
      Offset(dotX, dotY),
      5.5,
      Paint()
        ..color = AppTokens.brandCyan.withValues(alpha: 0.22)
        ..style = PaintingStyle.fill,
    );
  }

  @override
  bool shouldRepaint(covariant _RadarSweepPainter old) => old.angle != angle;
}
