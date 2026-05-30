import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../models/user.dart';
import 'local_storage_service.dart';

class AuthSession {
  final String token;
  final String role;
  final String displayName;
  final String email;
  final int? userId;

  const AuthSession({
    required this.token,
    required this.role,
    required this.displayName,
    required this.email,
    this.userId,
  });

  bool get isAdmin => role == 'admin';

  factory AuthSession.fromJson(Map<String, dynamic> json, String token) {
    final user = ApgUser.fromJson(
      Map<String, dynamic>.from(json['user'] ?? json),
    );
    return AuthSession(
      token: token,
      role: user.role,
      displayName: user.name,
      email: user.email,
      userId: user.id,
    );
  }
}

class RegisterResult {
  final AuthSession? session;
  final bool verificationRequired;
  final String email;

  const RegisterResult._({
    required this.session,
    required this.verificationRequired,
    required this.email,
  });

  factory RegisterResult.session(AuthSession session) => RegisterResult._(
    session: session,
    verificationRequired: false,
    email: session.email,
  );

  factory RegisterResult.verificationRequired(String email) =>
      RegisterResult._(session: null, verificationRequired: true, email: email);
}

/// Auth facade backed by /auth/login and /auth/me.
///
/// The visible User/Admin selector is only a UX hint. Routing uses the role
/// returned by the backend token response.
class AuthService {
  const AuthService({this.preferredBaseUrl});
  final String? preferredBaseUrl;
  static const Duration _timeout = Duration(seconds: 12);

  List<String> _candidates() => AppConfig.apiBaseCandidates(preferredBaseUrl);

  Future<AuthSession> signIn({
    required String login,
    required String password,
    required String requestedRole,
  }) async {
    final email = login.trim().toLowerCase();
    final pass = password.trim();
    if (email.isEmpty || pass.isEmpty) {
      throw const AuthException('أدخل البريد الإلكتروني وكلمة المرور');
    }

    for (final baseUrl in _candidates()) {
      final endpoint = '$baseUrl/auth/login';
      try {
        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: const {'Content-Type': 'application/json'},
              body: jsonEncode({'email': email, 'password': pass}),
            )
            .timeout(_timeout);
        if (response.statusCode == 401) {
          throw const AuthException(
            'البريد الإلكتروني أو كلمة المرور غير صحيحة',
          );
        }
        if (response.statusCode == 403 &&
            _responseDetail(
              response.body,
            ).toLowerCase().contains('verification')) {
          throw EmailVerificationRequiredException(email);
        }
        if (response.statusCode == 400 || response.statusCode == 422) {
          throw const AuthException('تحقق من البريد الإلكتروني وكلمة المرور');
        }
        if (response.statusCode >= 500) {
          throw const AuthException('الخادم غير متاح حاليًا');
        }
        if (response.statusCode != 200) {
          throw AuthException('فشل تسجيل الدخول (${response.statusCode})');
        }
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) {
          throw const AuthException('استجابة تسجيل الدخول غير صالحة');
        }
        final map = Map<String, dynamic>.from(decoded);
        final token = (map['token'] ?? '').toString();
        if (token.isEmpty) {
          throw const AuthException('لم يرجع الخادم رمز جلسة صالح');
        }
        return AuthSession.fromJson(map, token);
      } on AuthException {
        rethrow;
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    throw const AuthException('تعذر الاتصال بالخادم');
  }

  Future<RegisterResult> register({
    required String email,
    required String password,
    String? name,
  }) async {
    final normalizedEmail = email.trim().toLowerCase();
    final pass = password.trim();
    final displayName = name?.trim();
    if (normalizedEmail.isEmpty || pass.isEmpty) {
      throw const AuthException('أدخل البريد الإلكتروني وكلمة المرور');
    }

    for (final baseUrl in _candidates()) {
      final endpoint = '$baseUrl/auth/register';
      try {
        final body = <String, dynamic>{
          'email': normalizedEmail,
          'password': pass,
        };
        if (displayName != null && displayName.isNotEmpty) {
          body['name'] = displayName;
        }

        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: const {'Content-Type': 'application/json'},
              body: jsonEncode(body),
            )
            .timeout(_timeout);
        if (response.statusCode == 400 ||
            response.statusCode == 409 ||
            response.statusCode == 422) {
          throw AuthException(_registerErrorMessage(response.body));
        }
        if (response.statusCode >= 500) {
          throw const AuthException('الخادم غير متاح حالياً');
        }
        if (response.statusCode != 200) {
          throw AuthException('فشل إنشاء الحساب (${response.statusCode})');
        }
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) {
          throw const AuthException('استجابة إنشاء الحساب غير صالحة');
        }
        final map = Map<String, dynamic>.from(decoded);
        if (map['verification_required'] == true) {
          return RegisterResult.verificationRequired(normalizedEmail);
        }
        final token = (map['token'] ?? '').toString();
        if (token.isEmpty) {
          throw const AuthException('لم يرجع الخادم رمز جلسة صالح');
        }
        return RegisterResult.session(AuthSession.fromJson(map, token));
      } on AuthException {
        rethrow;
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    throw const AuthException('تعذر الاتصال بالخادم');
  }

  Future<AuthSession> verifyEmail({
    required String email,
    required String code,
  }) async {
    final normalizedEmail = email.trim().toLowerCase();
    final normalizedCode = code.trim();
    if (normalizedEmail.isEmpty ||
        normalizedCode.length != 6 ||
        int.tryParse(normalizedCode) == null) {
      throw const AuthException('أدخل رمز التحقق المكون من 6 أرقام');
    }

    for (final baseUrl in _candidates()) {
      final endpoint = '$baseUrl/auth/verify-email';
      try {
        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: const {'Content-Type': 'application/json'},
              body: jsonEncode({
                'email': normalizedEmail,
                'code': normalizedCode,
              }),
            )
            .timeout(_timeout);
        if (response.statusCode == 400 ||
            response.statusCode == 422 ||
            response.statusCode == 429) {
          throw AuthException(_verifyEmailErrorMessage(response.body));
        }
        if (response.statusCode >= 500) {
          throw const AuthException('الخادم غير متاح حالياً');
        }
        if (response.statusCode != 200) {
          throw const AuthException('تعذر التحقق من البريد حالياً');
        }
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) {
          throw const AuthException('استجابة التحقق غير صالحة');
        }
        final map = Map<String, dynamic>.from(decoded);
        final token = (map['token'] ?? '').toString();
        if (token.isEmpty) {
          throw const AuthException('تعذر بدء الجلسة بعد التحقق');
        }
        return AuthSession.fromJson(map, token);
      } on AuthException {
        rethrow;
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    throw const AuthException('تعذر الاتصال بالخادم');
  }

  Future<void> resendVerification({required String email}) async {
    final normalizedEmail = email.trim().toLowerCase();
    if (normalizedEmail.isEmpty) {
      throw const AuthException('أدخل البريد الإلكتروني أولاً');
    }

    for (final baseUrl in _candidates()) {
      final endpoint = '$baseUrl/auth/resend-verification';
      try {
        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: const {'Content-Type': 'application/json'},
              body: jsonEncode({'email': normalizedEmail}),
            )
            .timeout(_timeout);
        if (response.statusCode >= 500) {
          throw const AuthException('الخادم غير متاح حالياً');
        }
        if (response.statusCode == 200 ||
            response.statusCode == 400 ||
            response.statusCode == 422 ||
            response.statusCode == 429) {
          return;
        }
      } on AuthException {
        rethrow;
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    throw const AuthException('تعذر الاتصال بالخادم');
  }

  Future<AuthSession> currentSession(String token) async {
    if (token.trim().isEmpty) {
      throw const SessionExpiredException();
    }
    for (final baseUrl in _candidates()) {
      final endpoint = '$baseUrl/auth/me';
      try {
        final response = await http
            .get(
              Uri.parse(endpoint),
              headers: {'Authorization': 'Bearer $token'},
            )
            .timeout(_timeout);
        if (response.statusCode == 401 || response.statusCode == 403) {
          await LocalStorageService.instance.clearSessionRole();
          throw const SessionExpiredException();
        }
        if (response.statusCode != 200) {
          throw AuthException('فشل التحقق من الجلسة (${response.statusCode})');
        }
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) {
          throw const AuthException('استجابة الجلسة غير صالحة');
        }
        return AuthSession.fromJson({
          'user': Map<String, dynamic>.from(decoded),
        }, token);
      } on AuthException {
        rethrow;
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    throw const AuthException('تعذر الاتصال بالخادم');
  }

  Future<void> logout({String? token}) async {
    final activeToken =
        (token ?? LocalStorageService.instance.getSessionToken())?.trim();
    if (activeToken != null &&
        activeToken.isNotEmpty &&
        !activeToken.startsWith('demo-')) {
      for (final baseUrl in _candidates()) {
        final endpoint = '$baseUrl/auth/logout';
        try {
          final response = await http
              .post(
                Uri.parse(endpoint),
                headers: {'Authorization': 'Bearer $activeToken'},
              )
              .timeout(_timeout);
          if (response.statusCode == 200 ||
              response.statusCode == 401 ||
              response.statusCode == 403) {
            break;
          }
        } catch (error) {
          _logEndpointFailure(endpoint, error);
        }
      }
    }
    await LocalStorageService.instance.clearSessionRole();
  }

  Future<AuthSession> signInWithGoogle({required String requestedRole}) async {
    throw const AuthException('تسجيل Google غير مربوط بعد');
  }

  Future<AuthSession> demoSession(String role) async {
    final normalized = role.toLowerCase() == 'admin' ? 'admin' : 'user';

    // Quick demo is now a real-backend shortcut. It signs in with seeded DB
    // accounts so Demo User analyses are saved and immediately visible to Admin.
    try {
      return await signIn(
        login: normalized == 'admin' ? 'admin@apg.local' : 'user@apg.local',
        password: normalized == 'admin' ? 'admin123' : 'user123',
        requestedRole: normalized,
      );
    } catch (error) {
      if (!AppConfig.enableOfflineDemoFallback) {
        throw AuthException(
          'الديمو السريع يحتاج تشغيل الباك إند أولًا. شغّل الخادم ثم حاول مرة أخرى.',
        );
      }
      await Future<void>.delayed(const Duration(milliseconds: 420));
      return AuthSession(
        token: 'demo-$normalized-token',
        role: normalized,
        displayName: normalized == 'admin' ? 'مسؤول الديمو' : 'مستخدم الديمو',
        email: '$normalized@apg.demo',
        userId: normalized == 'admin' ? 2 : 1,
      );
    }
  }
}

String _registerErrorMessage(String body) {
  try {
    final decoded = jsonDecode(body);
    final detail = decoded is Map ? decoded['detail']?.toString() ?? '' : '';
    final normalized = detail.toLowerCase();
    if (normalized.contains('already')) {
      return 'البريد الإلكتروني مستخدم بالفعل';
    }
    if (normalized.contains('weak') || normalized.contains('password')) {
      return 'كلمة المرور يجب أن تكون 8 أحرف على الأقل';
    }
    if (normalized.contains('email')) {
      return 'البريد الإلكتروني غير صالح';
    }
  } catch (_) {}
  return 'تعذر إنشاء الحساب. تحقق من البيانات وحاول مرة أخرى';
}

String _verifyEmailErrorMessage(String body) {
  try {
    final decoded = jsonDecode(body);
    final detail = decoded is Map ? decoded['detail']?.toString() ?? '' : '';
    final normalized = detail.toLowerCase();
    if (normalized.contains('expired')) {
      return 'انتهت صلاحية الرمز. اطلب رمزاً جديداً';
    }
    if (normalized.contains('attempt')) {
      return 'تم تجاوز عدد المحاولات. اطلب رمزاً جديداً';
    }
    if (normalized.contains('code')) {
      return 'رمز التحقق غير صحيح';
    }
  } catch (_) {}
  return 'تعذر التحقق من البريد. تحقق من الرمز وحاول مرة أخرى';
}

String _responseDetail(String body) {
  try {
    final decoded = jsonDecode(body);
    return decoded is Map ? decoded['detail']?.toString() ?? '' : '';
  } catch (_) {
    return '';
  }
}

void _logEndpointFailure(String endpoint, Object error) {
  if (kDebugMode) debugPrint('[APG AUTH] Endpoint failed: $endpoint ($error)');
}

class AuthException implements Exception {
  final String message;
  const AuthException(this.message);

  @override
  String toString() => message;
}

class SessionExpiredException extends AuthException {
  const SessionExpiredException()
    : super('انتهت الجلسة، يرجى تسجيل الدخول مجددًا');
}

class EmailVerificationRequiredException extends AuthException {
  final String email;

  const EmailVerificationRequiredException(this.email)
    : super('يرجى تأكيد البريد الإلكتروني قبل تسجيل الدخول');
}
