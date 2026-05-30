import 'dart:async';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'config/app_config.dart';
import 'l10n/app_localizations.dart';
import 'screens/admin_shell.dart';
import 'screens/app_shell.dart';
import 'screens/login_screen.dart';
import 'screens/onboarding_screen.dart';
import 'services/auth_service.dart';
import 'services/local_storage_service.dart';
import 'theme/app_theme.dart';
import 'theme/app_tokens.dart';

Future<void> main() async {
  await runZonedGuarded<Future<void>>(
    () async {
      WidgetsFlutterBinding.ensureInitialized();

      FlutterError.onError = (FlutterErrorDetails details) {
        FlutterError.presentError(details);
      };

      PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
        debugPrint('[APG FATAL] $error');
        debugPrint(stack.toString());
        return true;
      };

      try {
        await LocalStorageService.instance.init();
      } catch (error, stack) {
        debugPrint('[APG STORAGE INIT ERROR] $error');
        debugPrint(stack.toString());
      }

      AppConfig.logStartupConfig();
      runApp(const ApgMobileApp());
    },
    (Object error, StackTrace stack) {
      debugPrint('[APG ZONE ERROR] $error');
      debugPrint(stack.toString());
    },
  );
}

class ApgMobileApp extends StatefulWidget {
  const ApgMobileApp({super.key});

  @override
  State<ApgMobileApp> createState() => _ApgMobileAppState();
}

class _ApgMobileAppState extends State<ApgMobileApp> {
  late bool _isDarkMode;
  late bool _onboardingSeen;
  late Locale _locale;
  late String _accentThemeKey;
  String? _sessionRole;

  @override
  void initState() {
    super.initState();
    _isDarkMode = LocalStorageService.instance.getDarkMode();
    _onboardingSeen = LocalStorageService.instance.getOnboardingSeen();
    _locale = Locale(LocalStorageService.instance.getLanguageCode());
    _accentThemeKey = LocalStorageService.instance.getAccentThemeKey();
    AppTokens.setAccentTheme(_accentThemeKey);
    _sessionRole = LocalStorageService.instance.getSessionRole();
  }

  Future<void> _toggleDarkMode(bool value) async {
    setState(() {
      _isDarkMode = value;
    });
    await LocalStorageService.instance.setDarkMode(value);
  }

  Future<void> _setLocale(Locale locale) async {
    final languageCode = locale.languageCode.toLowerCase() == 'en'
        ? 'en'
        : 'ar';
    setState(() {
      _locale = Locale(languageCode);
    });
    await LocalStorageService.instance.setLanguageCode(languageCode);
  }

  Future<void> _setAccentTheme(String key) async {
    final normalized = AppTokens.accentThemeByKey(key).key;
    setState(() {
      _accentThemeKey = normalized;
      AppTokens.setAccentTheme(normalized);
    });
    await LocalStorageService.instance.setAccentThemeKey(normalized);
  }

  Future<void> _finishOnboarding() async {
    await LocalStorageService.instance.setOnboardingSeen(true);
    setState(() {
      _onboardingSeen = true;
    });
  }

  Future<void> _handleLogin(AuthSession session) async {
    await LocalStorageService.instance.setSession(
      role: session.role,
      token: session.token,
      name: session.displayName,
      email: session.email,
      userId: session.userId,
    );
    setState(() {
      _sessionRole = session.role;
    });
  }

  Future<void> _handleLogout() async {
    await LocalStorageService.instance.clearSessionRole();
    setState(() {
      _sessionRole = null;
    });
  }

  Widget _buildHome() {
    if (!_onboardingSeen) {
      return OnboardingScreen(
        onFinish: _finishOnboarding,
        currentLocale: _locale,
        onChangeLocale: _setLocale,
      );
    }
    if (_sessionRole == null ||
        LocalStorageService.instance.getSessionToken() == null) {
      return LoginScreen(
        onLogin: _handleLogin,
        currentLocale: _locale,
        onChangeLocale: _setLocale,
      );
    }
    if (_sessionRole == 'admin') {
      return AdminShell(
        onLogout: _handleLogout,
        currentLocale: _locale,
        onChangeLocale: _setLocale,
      );
    }
    return AppShell(
      key: ValueKey(
        'app-shell-${LocalStorageService.instance.getSessionUserId() ?? 'none'}',
      ),
      isDarkMode: _isDarkMode,
      onToggleDarkMode: _toggleDarkMode,
      currentLocale: _locale,
      onChangeLocale: _setLocale,
      accentThemeKey: _accentThemeKey,
      onChangeAccentTheme: _setAccentTheme,
      onLogout: _handleLogout,
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      locale: _locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localeResolutionCallback: (locale, supportedLocales) {
        if (locale == null) return const Locale('ar');
        for (final supported in supportedLocales) {
          if (supported.languageCode == locale.languageCode) {
            return supported;
          }
        }
        return const Locale('ar');
      },
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: AppTheme.light(_locale),
      darkTheme: AppTheme.dark(_locale),
      themeAnimationDuration: const Duration(milliseconds: 320),
      themeAnimationCurve: Curves.easeOutCubic,
      themeMode: _isDarkMode ? ThemeMode.dark : ThemeMode.light,
      home: _LaunchGate(child: _buildHome()),
    );
  }
}

class _LaunchGate extends StatefulWidget {
  final Widget child;
  const _LaunchGate({required this.child});

  @override
  State<_LaunchGate> createState() => _LaunchGateState();
}

class _LaunchGateState extends State<_LaunchGate>
    with SingleTickerProviderStateMixin {
  bool _showSplash = true;
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
    Future<void>.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) setState(() => _showSplash = false);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 360),
      child: _showSplash
          ? Scaffold(
              key: const ValueKey('apg-splash'),
              backgroundColor: const Color(0xFF020B12),
              body: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ScaleTransition(
                      scale: Tween<double>(begin: 0.94, end: 1.05).animate(
                        CurvedAnimation(
                          parent: _controller,
                          curve: Curves.easeInOut,
                        ),
                      ),
                      child: SizedBox(
                        width: 132,
                        height: 132,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            Container(
                              width: 104,
                              height: 104,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                boxShadow: [
                                  BoxShadow(
                                    color: AppTokens.brandCyan.withValues(
                                      alpha: 0.24,
                                    ),
                                    blurRadius: 42,
                                    spreadRadius: 8,
                                  ),
                                ],
                              ),
                            ),
                            Image.asset(
                              'assets/branding/apg_logo_transparent.png',
                              width: 148,
                              height: 148,
                              fit: BoxFit.contain,
                              filterQuality: FilterQuality.high,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'APG',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 30,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.2,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '\u062C\u0627\u0631\u0650 \u062A\u0641\u0639\u064A\u0644 \u0627\u0644\u062D\u0645\u0627\u064A\u0629...',
                      style: TextStyle(
                        color: Color(0xFFAAB6C5),
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            )
          : KeyedSubtree(key: const ValueKey('apg-app'), child: widget.child),
    );
  }
}
