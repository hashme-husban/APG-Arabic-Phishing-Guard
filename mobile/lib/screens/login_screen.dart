import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../services/auth_service.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/apg_logo.dart';
import '../widgets/apg_ui.dart';
import '../widgets/motion.dart';

class LoginScreen extends StatefulWidget {
  final ValueChanged<AuthSession> onLogin;
  final Locale currentLocale;
  final ValueChanged<Locale> onChangeLocale;

  const LoginScreen({
    super.key,
    required this.onLogin,
    required this.currentLocale,
    required this.onChangeLocale,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _nameController = TextEditingController();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();
  final _codeController = TextEditingController();
  final _authService = const AuthService();

  String _requestedRole = 'user';
  bool _registerMode = false;
  bool _verificationMode = false;
  bool _obscure = true;
  bool _loading = false;
  bool _resending = false;
  String? _pendingEmail;
  String? _error;
  String? _notice;

  bool get _canSubmit =>
      (_verificationMode
          ? _codeController.text.trim().length == 6
          : _loginController.text.trim().isNotEmpty &&
                _passwordController.text.trim().isNotEmpty) &&
      !_loading;

  String _t(BuildContext context, String ar, String en) =>
      context.isArabic ? ar : en;

  @override
  void initState() {
    super.initState();
    _nameController.addListener(_changed);
    _loginController.addListener(_changed);
    _passwordController.addListener(_changed);
    _codeController.addListener(_changed);
  }

  void _changed() {
    if (mounted) {
      setState(() {
        _error = null;
        _notice = null;
      });
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _loginController.dispose();
    _passwordController.dispose();
    _codeController.dispose();
    super.dispose();
  }

  void _toggleRegisterMode() {
    setState(() {
      _registerMode = !_registerMode;
      _verificationMode = false;
      _requestedRole = 'user';
      _pendingEmail = null;
      _codeController.clear();
      _error = null;
      _notice = null;
    });
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    setState(() {
      _loading = true;
      _error = null;
      _notice = null;
    });
    try {
      if (_verificationMode) {
        final session = await _authService.verifyEmail(
          email: _pendingEmail ?? _loginController.text,
          code: _codeController.text,
        );
        if (!mounted) return;
        widget.onLogin(session);
        return;
      }
      if (_registerMode) {
        final result = await _authService.register(
          email: _loginController.text,
          password: _passwordController.text,
          name: _nameController.text,
        );
        if (!mounted) return;
        if (result.verificationRequired) {
          setState(() {
            _verificationMode = true;
            _pendingEmail = result.email;
            _codeController.clear();
            _notice = _t(
              context,
              'تم إرسال رمز تحقق إلى بريدك الإلكتروني',
              'A verification code was sent to your email',
            );
          });
          return;
        }
        final session = result.session;
        if (session != null) {
          widget.onLogin(session);
        }
        return;
      }
      final session = await _authService.signIn(
        login: _loginController.text,
        password: _passwordController.text,
        requestedRole: _requestedRole,
      );
      if (!mounted) return;
      widget.onLogin(session);
    } on EmailVerificationRequiredException catch (error) {
      if (!mounted) return;
      setState(() {
        _registerMode = false;
        _verificationMode = true;
        _pendingEmail = error.email;
        _codeController.clear();
        _notice = _t(
          context,
          'أدخل رمز التحقق المرسل إلى بريدك الإلكتروني',
          'Enter the verification code sent to your email',
        );
      });
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(
        () => _error = _t(
          context,
          'تعذر تسجيل الدخول الآن',
          'Could not sign in now',
        ),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _resendVerificationCode() async {
    final email = (_pendingEmail ?? _loginController.text).trim();
    if (_resending || email.isEmpty) return;
    setState(() {
      _resending = true;
      _error = null;
      _notice = null;
    });
    try {
      await _authService.resendVerification(email: email);
      if (!mounted) return;
      setState(() {
        _notice = _t(
          context,
          'إذا كان البريد صالحًا فسيتم إرسال رمز جديد',
          'If the email is valid, a new code will be sent',
        );
      });
    } on AuthException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } finally {
      if (mounted) setState(() => _resending = false);
    }
  }

  void _backToLogin() {
    setState(() {
      _verificationMode = false;
      _registerMode = false;
      _pendingEmail = null;
      _codeController.clear();
      _error = null;
      _notice = null;
    });
  }

  void _toggleLocale() {
    final next = widget.currentLocale.languageCode == 'ar'
        ? const Locale('en')
        : const Locale('ar');
    widget.onChangeLocale(next);
  }

  @override
  Widget build(BuildContext context) {
    final isArabic = context.isArabic;
    return Directionality(
      textDirection: isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: AppTokens.pageBackground(context),
        body: AppBackground(
          child: SafeArea(
            child: Stack(
              children: [
                Align(
                  alignment: AlignmentDirectional.topEnd,
                  child: Padding(
                    padding: const EdgeInsetsDirectional.only(top: 12, end: 18),
                    child: PressableScale(
                      onTap: _toggleLocale,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: AppTokens.isDark(context)
                              ? Colors.white.withValues(alpha: 0.07)
                              : AppTokens.lightSurface.withValues(alpha: 0.85),
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(
                            color: AppTokens.isDark(context)
                                ? Colors.white.withValues(alpha: 0.10)
                                : AppTokens.outlineLight,
                          ),
                        ),
                        child: Text(
                          widget.currentLocale.languageCode == 'ar'
                              ? 'EN'
                              : 'عربي',
                          style: TextStyle(
                            color: AppTokens.textPrimary(context),
                            fontWeight: FontWeight.w900,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                Center(
                  child: SingleChildScrollView(
                    keyboardDismissBehavior:
                        ScrollViewKeyboardDismissBehavior.onDrag,
                    padding: const EdgeInsets.fromLTRB(20, 24, 20, 34),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 440),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          FadeSlideIn(child: const _CompactBrandHeader()),
                          const SizedBox(height: 22),
                          FadeSlideIn(
                            delay: const Duration(milliseconds: 80),
                            beginOffset: const Offset(0, 20),
                            child: AppCard(
                              padding: const EdgeInsets.all(20),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _verificationMode
                                        ? _t(
                                            context,
                                            'تحقق من البريد',
                                            'Verify email',
                                          )
                                        : _registerMode
                                        ? _t(
                                            context,
                                            'إنشاء حساب',
                                            'Create account',
                                          )
                                        : _t(
                                            context,
                                            'تسجيل الدخول',
                                            'Sign in',
                                          ),
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineSmall
                                        ?.copyWith(
                                          fontWeight: FontWeight.w900,
                                          color: AppTokens.textPrimary(context),
                                        ),
                                  ),
                                  const SizedBox(height: 7),
                                  Text(
                                    _t(
                                      context,
                                      _verificationMode
                                          ? 'أدخل الرمز المكون من 6 أرقام لإكمال إنشاء الحساب.'
                                          : 'ادخل إلى حسابك لمتابعة الحماية.',
                                      _verificationMode
                                          ? 'Enter the 6 digit code to finish creating your account.'
                                          : 'Access your account to continue protection.',
                                    ),
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodyMedium
                                        ?.copyWith(
                                          color: AppTokens.mutedText(context),
                                          height: 1.5,
                                        ),
                                  ),
                                  const SizedBox(height: 18),
                                  if (_verificationMode) ...[
                                    Container(
                                      width: double.infinity,
                                      padding: const EdgeInsets.all(12),
                                      decoration: BoxDecoration(
                                        color: AppTokens.isDark(context)
                                            ? Colors.white.withValues(
                                                alpha: 0.045,
                                              )
                                            : AppTokens.lightSurfaceAlt,
                                        borderRadius: BorderRadius.circular(14),
                                        border: Border.all(
                                          color: AppTokens.isDark(context)
                                              ? Colors.white.withValues(
                                                  alpha: 0.08,
                                                )
                                              : AppTokens.outlineLight,
                                        ),
                                      ),
                                      child: Text(
                                        _pendingEmail ??
                                            _loginController.text.trim(),
                                        style: TextStyle(
                                          color: AppTokens.textPrimary(context),
                                          fontWeight: FontWeight.w900,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(height: 12),
                                    _AuthField(
                                      controller: _codeController,
                                      label: _t(
                                        context,
                                        'رمز التحقق',
                                        'Verification code',
                                      ),
                                      icon: Icons.verified_user_rounded,
                                      keyboardType: TextInputType.number,
                                      textInputAction: TextInputAction.done,
                                      onSubmitted: (_) => _submit(),
                                    ),
                                    const SizedBox(height: 12),
                                  ] else ...[
                                    if (_registerMode) ...[
                                      _AuthField(
                                        controller: _nameController,
                                        label: _t(
                                          context,
                                          'الاسم اختياري',
                                          'Name optional',
                                        ),
                                        icon: Icons.person_rounded,
                                        textInputAction: TextInputAction.next,
                                      ),
                                      const SizedBox(height: 12),
                                    ],
                                    _AuthField(
                                      controller: _loginController,
                                      label: _registerMode
                                          ? _t(
                                              context,
                                              'البريد الإلكتروني',
                                              'Email',
                                            )
                                          : _t(
                                              context,
                                              'البريد الإلكتروني أو اسم المستخدم',
                                              'Email or username',
                                            ),
                                      icon: Icons.alternate_email_rounded,
                                      textInputAction: TextInputAction.next,
                                    ),
                                    const SizedBox(height: 12),
                                    _AuthField(
                                      controller: _passwordController,
                                      label: _t(
                                        context,
                                        'كلمة المرور',
                                        'Password',
                                      ),
                                      icon: Icons.lock_rounded,
                                      obscureText: _obscure,
                                      suffix: IconButton(
                                        tooltip: _t(
                                          context,
                                          'إظهار أو إخفاء كلمة المرور',
                                          'Show or hide password',
                                        ),
                                        onPressed: () => setState(
                                          () => _obscure = !_obscure,
                                        ),
                                        icon: Icon(
                                          _obscure
                                              ? Icons.visibility_rounded
                                              : Icons.visibility_off_rounded,
                                        ),
                                      ),
                                      onSubmitted: (_) => _submit(),
                                    ),
                                  ],
                                  AnimatedSwitcher(
                                    duration: const Duration(milliseconds: 220),
                                    child: _error == null && _notice == null
                                        ? const SizedBox(height: 14)
                                        : Padding(
                                            key: ValueKey(_error ?? _notice),
                                            padding: const EdgeInsets.only(
                                              top: 12,
                                            ),
                                            child: Row(
                                              children: [
                                                Icon(
                                                  _error == null
                                                      ? Icons
                                                            .check_circle_rounded
                                                      : Icons.error_rounded,
                                                  color: _error == null
                                                      ? AppTokens.success
                                                      : AppTokens.danger,
                                                  size: 18,
                                                ),
                                                const SizedBox(width: 8),
                                                Expanded(
                                                  child: Text(
                                                    _error ?? _notice!,
                                                    style: TextStyle(
                                                      color: _error == null
                                                          ? AppTokens.success
                                                          : AppTokens.danger,
                                                      fontWeight:
                                                          FontWeight.w800,
                                                    ),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                  ),
                                  PrimaryButton(
                                    label: _loading
                                        ? _t(
                                            context,
                                            _verificationMode
                                                ? 'جارٍ التحقق...'
                                                : _registerMode
                                                ? 'جارٍ إنشاء الحساب...'
                                                : 'جارِ تسجيل الدخول...',
                                            _verificationMode
                                                ? 'Verifying...'
                                                : _registerMode
                                                ? 'Creating account...'
                                                : 'Signing in...',
                                          )
                                        : _t(
                                            context,
                                            _verificationMode
                                                ? 'تحقق من البريد'
                                                : _registerMode
                                                ? 'إنشاء حساب'
                                                : 'تسجيل الدخول',
                                            _verificationMode
                                                ? 'Verify email'
                                                : _registerMode
                                                ? 'Create account'
                                                : 'Sign in',
                                          ),
                                    icon: _verificationMode
                                        ? Icons.verified_rounded
                                        : _registerMode
                                        ? Icons.person_add_rounded
                                        : Icons.login_rounded,
                                    loading: _loading,
                                    onPressed: _canSubmit ? _submit : null,
                                  ),
                                  const SizedBox(height: 12),
                                  if (_verificationMode) ...[
                                    Row(
                                      children: [
                                        Expanded(
                                          child: SecondaryButton(
                                            label: _resending
                                                ? _t(
                                                    context,
                                                    'جارٍ الإرسال...',
                                                    'Sending...',
                                                  )
                                                : _t(
                                                    context,
                                                    'إعادة إرسال الرمز',
                                                    'Resend code',
                                                  ),
                                            icon: Icons.refresh_rounded,
                                            onPressed: _resending
                                                ? null
                                                : _resendVerificationCode,
                                          ),
                                        ),
                                      ],
                                    ),
                                    Center(
                                      child: TextButton(
                                        onPressed: _loading || _resending
                                            ? null
                                            : _backToLogin,
                                        child: Text(
                                          _t(
                                            context,
                                            'العودة لتسجيل الدخول',
                                            'Back to sign in',
                                          ),
                                        ),
                                      ),
                                    ),
                                  ] else ...[
                                    Center(
                                      child: TextButton(
                                        onPressed: _loading
                                            ? null
                                            : _toggleRegisterMode,
                                        child: Text(
                                          _registerMode
                                              ? _t(
                                                  context,
                                                  'لديك حساب؟ تسجيل الدخول',
                                                  'Already have an account? Sign in',
                                                )
                                              : _t(
                                                  context,
                                                  'إنشاء حساب جديد',
                                                  'Create a new account',
                                                ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),
                          FadeSlideIn(
                            delay: const Duration(milliseconds: 140),
                            child: Text(
                              _t(
                                context,
                                'APG يحميك من التصيد برسائل واضحة وقرارات سريعة.',
                                'APG protects you from phishing with clear results.',
                              ),
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.bodySmall
                                  ?.copyWith(
                                    color: AppTokens.mutedText(context),
                                    height: 1.5,
                                    fontWeight: FontWeight.w700,
                                  ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CompactBrandHeader extends StatelessWidget {
  const _CompactBrandHeader();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const _AnimatedLoginLogo(),
        const SizedBox(height: 13),
        Text(
          'APG',
          style: TextStyle(
            color: AppTokens.textPrimary(context),
            fontSize: 30,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.1,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          'Arabic Phishing Guard',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: AppTokens.mutedText(context).withValues(alpha: 0.96),
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}

class _AnimatedLoginLogo extends StatefulWidget {
  const _AnimatedLoginLogo();

  @override
  State<_AnimatedLoginLogo> createState() => _AnimatedLoginLogoState();
}

class _AnimatedLoginLogoState extends State<_AnimatedLoginLogo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _breath;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2600),
    )..repeat(reverse: true);
    _breath = CurvedAnimation(parent: _controller, curve: Curves.easeInOut);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _breath,
      builder: (context, child) {
        final value = _breath.value;
        return Opacity(
          opacity: 0.92 + (value * 0.08),
          child: Transform.translate(
            offset: Offset(0, -4 * value),
            child: Transform.scale(
              scale: 0.992 + (value * 0.032),
              child: SizedBox(
                width: 108,
                height: 94,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    Positioned(
                      bottom: 8,
                      child: Container(
                        width: 76 + (value * 10),
                        height: 18 + (value * 3),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(999),
                          boxShadow: [
                            BoxShadow(
                              color: AppTokens.brandCyan.withValues(
                                alpha: 0.16 + (value * 0.10),
                              ),
                              blurRadius: 28 + (value * 10),
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                      ),
                    ),
                    APGLogo(
                      size: 74,
                      glowOpacity: 0.20 + (value * 0.10),
                      paddingFraction: 0.088,
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _AuthField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final bool obscureText;
  final Widget? suffix;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;

  const _AuthField({
    required this.controller,
    required this.label,
    required this.icon,
    this.obscureText = false,
    this.suffix,
    this.keyboardType,
    this.textInputAction,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscureText,
      keyboardType: keyboardType,
      textInputAction: textInputAction,
      onSubmitted: onSubmitted,
      textAlign: TextAlign.right,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 20),
        suffixIcon: suffix,
      ),
    );
  }
}
