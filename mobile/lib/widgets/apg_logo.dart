import 'package:flutter/material.dart';

class APGLogo extends StatelessWidget {
  final double size;
  final double glowOpacity;
  final double paddingFraction;
  final bool showContainer;

  const APGLogo({
    super.key,
    this.size = 64,
    this.glowOpacity = 0.16,
    this.paddingFraction = 0.04,
    this.showContainer = true,
  });

  @override
  Widget build(BuildContext context) {
    if (!showContainer) {
      return SizedBox(
        width: size,
        height: size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Container(
              width: size * 0.86,
              height: size * 0.86,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Color(0xFF38BDF8).withValues(alpha: glowOpacity),
                    blurRadius: size * 0.28,
                    spreadRadius: size * 0.02,
                  ),
                ],
              ),
            ),
            Padding(
              padding: EdgeInsets.all(size * paddingFraction),
              child: Image.asset(
                'assets/branding/apg_logo_transparent.png',
                fit: BoxFit.contain,
                filterQuality: FilterQuality.high,
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * 0.26),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF071B26), Color(0xFF172554)],
        ),
        border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
        boxShadow: [
          BoxShadow(
            color: Color(0xFF38BDF8).withValues(alpha: glowOpacity),
            blurRadius: size * 0.18,
            offset: Offset(0, size * 0.10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(size * 0.22),
        child: Padding(
          padding: EdgeInsets.all(size * paddingFraction),
          child: Image.asset(
            'assets/branding/apg_logo_transparent.png',
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
          ),
        ),
      ),
    );
  }
}
