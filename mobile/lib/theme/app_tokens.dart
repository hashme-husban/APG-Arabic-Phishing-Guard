import 'package:flutter/material.dart';

class AppAccentTheme {
  final String key;
  final String label;
  final Color primary;
  final Color light;

  const AppAccentTheme({
    required this.key,
    required this.label,
    required this.primary,
    required this.light,
  });
}

class AppTokens {
  static const List<AppAccentTheme> accentThemes = [
    AppAccentTheme(
      key: 'blue',
      label: 'الأزرق',
      primary: Color(0xFF2563EB),
      light: Color(0xFFDBEAFE),
    ),
    AppAccentTheme(
      key: 'purple',
      label: 'البنفسجي',
      primary: Color(0xFF8B5CF6),
      light: Color(0xFFE9D5FF),
    ),
    AppAccentTheme(
      key: 'cyan',
      label: 'السماوي',
      primary: Color(0xFF06B6D4),
      light: Color(0xFFCFFAFE),
    ),
    AppAccentTheme(
      key: 'green',
      label: 'الأخضر',
      primary: Color(0xFF22C55E),
      light: Color(0xFFDCFCE7),
    ),
    AppAccentTheme(
      key: 'orange',
      label: 'البرتقالي',
      primary: Color(0xFFF97316),
      light: Color(0xFFFFEDD5),
    ),
    AppAccentTheme(
      key: 'pink',
      label: 'الوردي',
      primary: Color(0xFFEC4899),
      light: Color(0xFFFCE7F3),
    ),
  ];

  static Color brand = const Color(0xFF2563EB);
  static Color brandAlt = const Color(0xFF1D4ED8);
  static Color brandLight = const Color(0xFFDBEAFE);
  static String accentThemeKey = 'blue';

  static AppAccentTheme accentThemeByKey(String key) {
    return accentThemes.firstWhere(
      (theme) => theme.key == key,
      orElse: () => accentThemes.first,
    );
  }

  static void setAccentTheme(String key) {
    final theme = accentThemeByKey(key);
    accentThemeKey = theme.key;
    brand = theme.primary;
    brandLight = theme.light;
    brandAlt =
        Color.lerp(theme.primary, const Color(0xFF111827), 0.14) ??
        theme.primary;
  }

  static const Color brandDeep = Color(0xFF24145E);
  static const Color brandCyan = Color(0xFF00D9FF);
  static const Color brandBlue = Color(0xFF38BDF8);
  static const Color brandTeal = Color(0xFF2CC5BE);

  static const Color danger = Color(0xFFFF4D6D);
  static const Color warning = Color(0xFFFACC15);
  static const Color success = Color(0xFF22C55E);
  static const Color neutral = Color(0xFF94A3B8);

  static const Color lightBackground = Color(0xFFF4F7FB);
  static const Color lightBackgroundAlt = Color(0xFFEAF0FF);
  static const Color darkBackground = Color(0xFF020B12);
  static const Color darkBackgroundAlt = Color(0xFF031016);

  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceAlt = Color(0xFFF1F5F9);
  static const Color darkSurface = Color(0xFF071B26);
  static const Color darkSurfaceAlt = Color(0xFF111827);
  static const Color darkSurfaceDeep = Color(0xFF061725);

  static const Color outlineLight = Color(0xFFD7E0EF);
  static const Color outlineDark = Color(0xFF1E3A4D);

  static const Color lightText = Color(0xFF0B1220);
  static const Color lightMutedText = Color(0xFF475467);
  static const Color darkText = Color(0xFFF8FAFC);
  static const Color darkMutedText = Color(0xFFB8C4D6);

  static const double radiusXs = 12;
  static const double radiusSm = 16;
  static const double radiusMd = 22;
  static const double radiusLg = 26;
  static const double radiusXl = 28;

  // Reserved space for the floating bottom navigation.
  // Keeps every scrollable screen clear of the nav bar and Android gesture area.
  static const double bottomNavContentPadding = 136;

  static bool isDark(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark;

  static Color surface(BuildContext context) =>
      isDark(context) ? darkSurface : lightSurface;
  static Color surfaceAlt(BuildContext context) =>
      isDark(context) ? darkSurfaceAlt : lightSurfaceAlt;
  static Color pageBackground(BuildContext context) =>
      isDark(context) ? darkBackground : lightBackground;
  static Color pageBackgroundAlt(BuildContext context) =>
      isDark(context) ? darkBackgroundAlt : lightBackgroundAlt;
  static Color textPrimary(BuildContext context) =>
      isDark(context) ? darkText : lightText;
  static Color mutedText(BuildContext context) =>
      isDark(context) ? darkMutedText : lightMutedText;
  static Color outline(BuildContext context) =>
      isDark(context) ? outlineDark : outlineLight;

  static Color chipBackground(BuildContext context) =>
      isDark(context) ? const Color(0xFF0A2F43) : const Color(0xFFEFF4FF);
  static Color chipSelected(BuildContext context) =>
      isDark(context) ? brand : brandLight;

  static List<BoxShadow> cardShadow(BuildContext context) {
    if (isDark(context)) {
      return [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.22),
          blurRadius: 24,
          spreadRadius: -4,
          offset: const Offset(0, 14),
        ),
      ];
    }
    return [
      BoxShadow(
        color: const Color(0xFF0F172A).withValues(alpha: 0.055),
        blurRadius: 24,
        spreadRadius: -4,
        offset: const Offset(0, 12),
      ),
    ];
  }

  static LinearGradient heroGradient(BuildContext context) {
    return const LinearGradient(
      colors: [Color(0xFF071B26), Color(0xFF1B1450), Color(0xFF031016)],
      stops: [0.0, 0.58, 1.0],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }

  static LinearGradient cyberGradient(BuildContext context) {
    return LinearGradient(
      colors: isDark(context)
          ? const [Color(0xF008283A), Color(0xEF101B2E)]
          : const [Color(0xFFFFFFFF), Color(0xFFF7FAFF)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }

  static LinearGradient surfaceGradient(BuildContext context) {
    return LinearGradient(
      colors: isDark(context)
          ? const [Color(0xE8092535), Color(0xEA101B2E)]
          : const [Color(0xFFFFFFFF), Color(0xFFF8FBFF)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }

  static LinearGradient primaryButtonGradient() {
    return LinearGradient(
      colors: [brand, brandAlt],
      begin: Alignment.centerLeft,
      end: Alignment.centerRight,
    );
  }

  static LinearGradient riskGradient(String label) {
    final color = riskColor(label);
    return LinearGradient(
      colors: [color.withValues(alpha: 0.15), color.withValues(alpha: 0.04)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }

  static Color riskColor(String label) {
    switch (label.toLowerCase()) {
      case 'phishing':
      case 'dangerous':
      case 'high_risk':
        return danger;
      case 'suspicious':
      case 'warning':
        return warning;
      case 'safe':
        return success;
      default:
        return neutral;
    }
  }
}
