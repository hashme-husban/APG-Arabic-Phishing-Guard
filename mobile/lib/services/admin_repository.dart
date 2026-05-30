import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../theme/app_tokens.dart';
import 'local_storage_service.dart';

class AdminRepository {
  const AdminRepository({this.preferredBaseUrl});
  final String? preferredBaseUrl;
  static const Duration _timeout = Duration(seconds: 14);

  List<String> _candidates() => AppConfig.apiBaseCandidates(preferredBaseUrl);

  Map<String, String> _headers({bool json = false}) {
    final token = LocalStorageService.instance.getSessionToken();
    return {
      if (json) 'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty && !token.startsWith('demo-'))
        'Authorization': 'Bearer $token',
    };
  }

  bool get _hasRealToken {
    final token = LocalStorageService.instance.getSessionToken();
    return token != null && token.isNotEmpty && !token.startsWith('demo-');
  }

  bool get _allowOfflineDemo => AppConfig.enableOfflineDemoFallback;

  Future<AdminOverviewData> fetchOverview() async {
    if (!_hasRealToken) {
      return _allowOfflineDemo
          ? demoOverview()
          : AdminOverviewData.empty(system: offlineSystemSnapshot());
    }
    for (final baseUrl in _candidates()) {
      try {
        final response = await http
            .get(Uri.parse('$baseUrl/admin/overview'), headers: _headers())
            .timeout(_timeout);
        if (response.statusCode == 200) {
          final json = Map<String, dynamic>.from(
            jsonDecode(response.body) as Map,
          );
          return _overviewFromJson(json);
        }
      } catch (_) {}
    }
    return _allowOfflineDemo
        ? demoOverview()
        : AdminOverviewData.empty(system: offlineSystemSnapshot());
  }

  Future<AdminSystemSnapshot> fetchSystemSnapshot() async {
    if (!_hasRealToken) {
      return _allowOfflineDemo ? systemSnapshot() : offlineSystemSnapshot();
    }
    for (final baseUrl in _candidates()) {
      try {
        final response = await http
            .get(Uri.parse('$baseUrl/admin/system/status'), headers: _headers())
            .timeout(_timeout);
        if (response.statusCode == 200) {
          return _systemFromJson(
            Map<String, dynamic>.from(jsonDecode(response.body) as Map),
          );
        }
      } catch (_) {}
    }
    return _allowOfflineDemo ? systemSnapshot() : offlineSystemSnapshot();
  }

  Future<List<AdminMessage>> fetchMessages({
    String filter = 'needs_review',
    int page = 1,
    int limit = 20,
  }) async {
    if (!_hasRealToken) {
      return _allowOfflineDemo ? messages() : <AdminMessage>[];
    }
    for (final baseUrl in _candidates()) {
      try {
        final uri = Uri.parse('$baseUrl/admin/review').replace(
          queryParameters: {
            'filter': filter,
            'page': '$page',
            'limit': '$limit',
          },
        );
        final response = await http
            .get(uri, headers: _headers())
            .timeout(_timeout);
        if (response.statusCode == 200) {
          final decoded = jsonDecode(response.body);
          final items = decoded is Map ? decoded['items'] : null;
          if (items is List) {
            return items
                .map(
                  (e) => _messageFromJson(Map<String, dynamic>.from(e as Map)),
                )
                .toList();
          }
        }
      } catch (_) {}
    }
    return _allowOfflineDemo ? messages() : <AdminMessage>[];
  }

  Future<List<AdminReport>> fetchReports({String status = 'all'}) async {
    if (!_hasRealToken) return _allowOfflineDemo ? reports() : <AdminReport>[];
    for (final baseUrl in _candidates()) {
      try {
        final uri = Uri.parse(
          '$baseUrl/admin/reports',
        ).replace(queryParameters: {'status': status});
        final response = await http
            .get(uri, headers: _headers())
            .timeout(_timeout);
        if (response.statusCode == 200) {
          final decoded = jsonDecode(response.body);
          final items = decoded is Map ? decoded['items'] : null;
          if (items is List) {
            return items
                .map(
                  (e) => _reportFromJson(Map<String, dynamic>.from(e as Map)),
                )
                .toList();
          }
        }
      } catch (_) {}
    }
    return _allowOfflineDemo ? reports() : <AdminReport>[];
  }

  Future<void> updateReportStatus(
    String id,
    AdminReportStatus status, {
    String note = '',
  }) async {
    if (!_hasRealToken) return;
    for (final baseUrl in _candidates()) {
      try {
        final response = await http
            .patch(
              Uri.parse('$baseUrl/admin/reports/$id'),
              headers: _headers(json: true),
              body: jsonEncode({
                'status': _statusApi(status),
                'admin_note': note,
              }),
            )
            .timeout(_timeout);
        if (response.statusCode == 200) return;
      } catch (_) {}
    }
  }

  Future<AdminSystemSnapshot> testConnection() async {
    for (final baseUrl in _candidates()) {
      try {
        final started = Stopwatch()..start();
        final response = await http
            .get(Uri.parse('$baseUrl/health'))
            .timeout(_timeout);
        started.stop();
        if (_healthResponseOk(response)) {
          Map<String, dynamic> payload = const <String, dynamic>{};
          try {
            final decoded = jsonDecode(response.body);
            if (decoded is Map) payload = Map<String, dynamic>.from(decoded);
          } catch (_) {}
          return _systemFromHealthJson(
            payload,
            baseUrl,
            started.elapsedMilliseconds,
          );
        }
      } catch (_) {}
    }
    return _allowOfflineDemo ? systemSnapshot() : offlineSystemSnapshot();
  }

  AdminSystemSnapshot systemSnapshot() => const AdminSystemSnapshot(
    serverConnected: true,
    responseMs: 124,
    databaseConnected: true,
    recordsToday: 1248,
    activeDevices: 36,
    devicesToday: 51,
    lastDevice: 'device-9F3A',
    modelVersion: 'APG-NLP v1.9',
    rulesVersion: 'rules-2026.05',
    apiUrl: AppConfig.apiBaseUrl,
    lastSync: 'منذ 4 دقائق',
  );

  AdminSystemSnapshot offlineSystemSnapshot() => const AdminSystemSnapshot(
    serverConnected: false,
    responseMs: 0,
    databaseConnected: false,
    recordsToday: 0,
    activeDevices: 0,
    devicesToday: 0,
    lastDevice: 'dev-0000',
    modelVersion: 'غير متاح',
    rulesVersion: 'غير متاح',
    apiUrl: AppConfig.apiBaseUrl,
    lastSync: 'غير متصل',
  );

  AdminOverviewData demoOverview() => AdminOverviewData(
    system: systemSnapshot(),
    today: todayStats(messages()),
    mainAlert: 'بيانات تجريبية غير حقيقية',
    newReports: reports()
        .where((r) => r.status == AdminReportStatus.newReport)
        .length,
    needsReview: messages()
        .where((m) => m.label == 'خطر مرتفع' || m.label == 'مشبوه')
        .take(3)
        .toList(),
  );

  AdminOverviewData _overviewFromJson(Map<String, dynamic> json) {
    final systemJson = Map<String, dynamic>.from(
      (json['system'] as Map?) ?? const <String, dynamic>{},
    );
    final todayJson = Map<String, dynamic>.from(
      (json['today'] as Map?) ?? const <String, dynamic>{},
    );
    final alertsJson = Map<String, dynamic>.from(
      (json['alerts'] as Map?) ?? const <String, dynamic>{},
    );
    final rawReview = json['needs_review'];
    final review = rawReview is List
        ? rawReview
              .map((e) => _messageFromJson(Map<String, dynamic>.from(e as Map)))
              .toList()
        : <AdminMessage>[];
    return AdminOverviewData(
      system: _systemFromJson(systemJson),
      today: AdminTodayStats(
        totalAnalyses: _int(todayJson['total_analyses']),
        highRisk: _int(todayJson['dangerous']),
        suspicious: _int(todayJson['suspicious']),
        activeDevices: _int(todayJson['active_devices']),
      ),
      mainAlert: (alertsJson['main_alert'] ?? 'لا توجد مشاكل حرجة حاليًا')
          .toString(),
      newReports: _int(alertsJson['new_reports']),
      needsReview: review,
    );
  }

  List<AdminMessage> messages() => <AdminMessage>[
    AdminMessage(
      id: 'msg-001',
      label: 'خطر مرتفع',
      score: 94,
      text:
          'عاجل: سيتم إيقاف حسابك البنكي. أدخل رمز التحقق OTP عبر الرابط التالي فورًا.',
      source: 'SMS',
      sourceApp: 'Google Messages',
      deviceHash: 'dev-8A2F',
      userHash: 'user-45**',
      createdAt: DateTime.now().subtract(const Duration(minutes: 8)),
      reasons: const [
        'طلب رمز تحقق OTP',
        'صياغة استعجالية',
        'رابط مشبوه',
        'انتحال جهة بنكية',
      ],
      responseMs: 118,
      requestId: 'req_9d71a',
      automatic: true,
    ),
    AdminMessage(
      id: 'msg-002',
      label: 'مشبوه',
      score: 67,
      text: 'يرجى تحديث بيانات الجامعة من خلال الرابط المرفق قبل نهاية اليوم.',
      source: 'Email',
      sourceApp: 'Gmail',
      deviceHash: 'dev-1C7B',
      userHash: 'user-31**',
      createdAt: DateTime.now().subtract(const Duration(minutes: 22)),
      reasons: const ['رابط غير موثوق', 'طلب تحديث بيانات', 'مصدر يحتاج تحقق'],
      responseMs: 141,
      requestId: 'req_2f81b',
      automatic: true,
    ),
    AdminMessage(
      id: 'msg-003',
      label: 'آمن',
      score: 12,
      text: 'تم تأكيد موعد محاضرتك غدًا الساعة العاشرة صباحًا في القاعة 203.',
      source: 'Manual',
      sourceApp: 'APG',
      deviceHash: 'dev-77AA',
      userHash: 'user-12**',
      createdAt: DateTime.now().subtract(const Duration(hours: 1, minutes: 12)),
      reasons: const ['لا توجد روابط خطرة', 'لا يطلب بيانات حساسة'],
      responseMs: 96,
      requestId: 'req_81bc4',
      automatic: false,
    ),
    AdminMessage(
      id: 'msg-004',
      label: 'خطر مرتفع',
      score: 91,
      text: 'ربحت جائزة مالية. أرسل رقم البطاقة والرمز السري لتأكيد التحويل.',
      source: 'WhatsApp',
      sourceApp: 'WhatsApp',
      deviceHash: 'dev-4E90',
      userHash: 'user-90**',
      createdAt: DateTime.now().subtract(const Duration(hours: 2, minutes: 3)),
      reasons: const ['طلب بيانات بنكية', 'وعد بجائزة وهمية', 'مرسل غير موثوق'],
      responseMs: 133,
      requestId: 'req_7aa13',
      automatic: true,
    ),
  ];

  List<AdminReport> reports() => <AdminReport>[
    AdminReport(
      id: 'rep-001',
      type: 'نتيجة غير دقيقة',
      text: 'رسالة البنك صُنفت آمنة رغم أنها تطلب رمز تحقق.',
      currentLabel: 'آمن',
      note: 'أعتقد أنها محاولة تصيد واضحة.',
      status: AdminReportStatus.newReport,
      createdAt: DateTime.now().subtract(const Duration(minutes: 18)),
      userHash: 'user-82**',
    ),
    AdminReport(
      id: 'rep-002',
      type: 'تصنيف خاطئ',
      text: 'رسالة الجامعة الرسمية ظهرت كمشبوهة.',
      currentLabel: 'مشبوه',
      note: 'البريد رسمي من نطاق الجامعة.',
      status: AdminReportStatus.inReview,
      createdAt: DateTime.now().subtract(const Duration(hours: 3)),
      userHash: 'user-14**',
    ),
    AdminReport(
      id: 'rep-003',
      type: 'رابط لم يكتشف',
      text: 'الرابط المختصر لم يظهر كسبب في التحليل.',
      currentLabel: 'مشبوه',
      note: null,
      status: AdminReportStatus.resolved,
      createdAt: DateTime.now().subtract(const Duration(days: 1, hours: 2)),
      userHash: 'user-33**',
    ),
  ];

  AdminTodayStats todayStats(List<AdminMessage> messages) {
    final high = messages.where((m) => m.label == 'خطر مرتفع').length;
    final suspicious = messages.where((m) => m.label == 'مشبوه').length;
    return AdminTodayStats(
      totalAnalyses: max(messages.length, 1),
      highRisk: high,
      suspicious: suspicious,
      activeDevices: 36,
    );
  }

  AdminSystemSnapshot _systemFromJson(Map<String, dynamic> json) =>
      AdminSystemSnapshot(
        serverConnected: (json['server_status'] ?? '') == 'connected',
        responseMs: _int(json['latency_ms'] ?? json['api_latency_ms']),
        databaseConnected: (json['database_status'] ?? '') == 'connected',
        recordsToday: _int(json['records_today'] ?? 0),
        activeDevices: _int(json['active_devices'] ?? 0),
        devicesToday: _int(json['devices_today'] ?? 0),
        lastDevice: (json['last_device'] ?? 'dev-0000').toString(),
        modelVersion: (json['model_version'] ?? 'APG-Heuristic v1.0')
            .toString(),
        rulesVersion: (json['rules_version'] ?? 'rules-2026.05').toString(),
        apiUrl: (json['api_url'] ?? AppConfig.apiBaseUrl).toString(),
        lastSync: _relativeTime(
          DateTime.tryParse((json['last_checked'] ?? '').toString()) ??
              DateTime.now(),
        ),
      );

  bool _healthResponseOk(http.Response response) {
    if (response.statusCode == 200) return true;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map) return false;
      final data = _map(decoded['data']);
      final success = decoded['success'] == true || data['success'] == true;
      final backendStatus =
          (decoded['backend_status'] ?? data['backend_status'] ?? '')
              .toString()
              .toLowerCase();
      return success || backendStatus == 'ok';
    } catch (_) {
      return false;
    }
  }

  AdminSystemSnapshot _systemFromHealthJson(
    Map<String, dynamic> json,
    String baseUrl,
    int elapsedMs,
  ) {
    final data = _map(json['data']);
    final databaseStatus =
        (json['database_status'] ?? data['database_status'] ?? '')
            .toString()
            .toLowerCase();
    final latency = _int(json['latency_ms'] ?? data['latency_ms']);
    return AdminSystemSnapshot(
      serverConnected: true,
      responseMs: latency > 0 ? latency : elapsedMs,
      databaseConnected:
          databaseStatus == 'connected' || databaseStatus == 'ok',
      recordsToday: 0,
      activeDevices: 0,
      devicesToday: 0,
      lastDevice: 'dev-0000',
      modelVersion: (json['version'] ?? data['version'] ?? 'APG backend')
          .toString(),
      rulesVersion: 'rules-2026.05',
      apiUrl: baseUrl,
      lastSync: _relativeTime(DateTime.now()),
    );
  }

  Map<String, dynamic> _map(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return const <String, dynamic>{};
  }

  AdminMessage _messageFromJson(Map<String, dynamic> json) => AdminMessage(
    id: (json['id'] ?? '').toString(),
    label: _labelAr(
      (json['classification'] ?? json['final_label'] ?? '').toString(),
    ),
    score: _int(json['risk_score'] ?? json['final_score']),
    text: (json['masked_text'] ?? '').toString(),
    source: (json['source'] ?? 'manual').toString(),
    sourceApp: (json['source_app'] ?? '').toString(),
    deviceHash: (json['device_label'] ?? 'dev-0000').toString(),
    userHash: (json['user_label'] ?? 'user-**').toString(),
    createdAt:
        DateTime.tryParse((json['created_at'] ?? '').toString()) ??
        DateTime.now(),
    reasons: _list(json['reasons']),
    responseMs: _int(
      (json['technical'] is Map
              ? json['technical']['response_time_ms']
              : json['response_time_ms']) ??
          0,
    ),
    requestId:
        ((json['technical'] is Map ? json['technical']['request_id'] : null) ??
                'req_${json['id'] ?? ''}')
            .toString(),
    automatic: (json['source'] ?? '') == 'notification',
  );

  AdminReport _reportFromJson(Map<String, dynamic> json) => AdminReport(
    id: (json['id'] ?? '').toString(),
    type: _reportTypeAr((json['report_type'] ?? '').toString()),
    text: (json['masked_text'] ?? json['message'] ?? '').toString(),
    currentLabel: _labelAr((json['current_label'] ?? '').toString()),
    note: (json['message'] ?? '').toString().isEmpty
        ? null
        : (json['message'] ?? '').toString(),
    status: _statusFromApi((json['status'] ?? 'new').toString()),
    createdAt:
        DateTime.tryParse((json['created_at'] ?? '').toString()) ??
        DateTime.now(),
    userHash: (json['user_label'] ?? 'user-**').toString(),
  );

  String _labelAr(String value) {
    switch (value.toLowerCase()) {
      case 'dangerous':
        return 'خطر مرتفع';
      case 'suspicious':
        return 'مشبوه';
      case 'safe':
        return 'آمن';
      default:
        return value.isEmpty ? 'مشبوه' : value;
    }
  }

  String _reportTypeAr(String value) {
    switch (value) {
      case 'wrong_classification':
        return 'تصنيف خاطئ';
      case 'missed_phishing':
        return 'رابط لم يكتشف';
      case 'inaccurate_result':
        return 'نتيجة غير دقيقة';
      case 'app_issue':
        return 'مشكلة في التطبيق';
      default:
        return 'بلاغ تصيد يدوي';
    }
  }

  AdminReportStatus _statusFromApi(String value) {
    switch (value) {
      case 'in_review':
        return AdminReportStatus.inReview;
      case 'resolved':
        return AdminReportStatus.resolved;
      case 'rejected':
        return AdminReportStatus.rejected;
      default:
        return AdminReportStatus.newReport;
    }
  }

  String _statusApi(AdminReportStatus status) {
    switch (status) {
      case AdminReportStatus.inReview:
        return 'in_review';
      case AdminReportStatus.resolved:
        return 'resolved';
      case AdminReportStatus.rejected:
        return 'rejected';
      case AdminReportStatus.newReport:
        return 'new';
    }
  }

  int _int(dynamic value) => value is int
      ? value
      : (value is num ? value.round() : int.tryParse('$value') ?? 0);
  List<String> _list(dynamic value) =>
      value is List ? value.map((e) => e.toString()).toList() : <String>[];
  String _relativeTime(DateTime date) => shortTime(date);
}

class AdminOverviewData {
  final AdminSystemSnapshot system;
  final AdminTodayStats today;
  final String mainAlert;
  final int newReports;
  final List<AdminMessage> needsReview;

  const AdminOverviewData({
    required this.system,
    required this.today,
    required this.mainAlert,
    required this.newReports,
    required this.needsReview,
  });

  factory AdminOverviewData.empty({required AdminSystemSnapshot system}) =>
      AdminOverviewData(
        system: system,
        today: const AdminTodayStats(
          totalAnalyses: 0,
          highRisk: 0,
          suspicious: 0,
          activeDevices: 0,
        ),
        mainAlert: system.serverConnected
            ? 'لا توجد مشاكل حرجة حاليًا'
            : 'تعذر تحميل بيانات لوحة الإدارة',
        newReports: 0,
        needsReview: const <AdminMessage>[],
      );
}

class AdminTodayStats {
  final int totalAnalyses;
  final int highRisk;
  final int suspicious;
  final int activeDevices;
  const AdminTodayStats({
    required this.totalAnalyses,
    required this.highRisk,
    required this.suspicious,
    required this.activeDevices,
  });
}

class AdminSystemSnapshot {
  final bool serverConnected;
  final int responseMs;
  final bool databaseConnected;
  final int recordsToday;
  final int activeDevices;
  final int devicesToday;
  final String lastDevice;
  final String modelVersion;
  final String rulesVersion;
  final String apiUrl;
  final String lastSync;

  const AdminSystemSnapshot({
    required this.serverConnected,
    required this.responseMs,
    required this.databaseConnected,
    required this.recordsToday,
    required this.activeDevices,
    required this.devicesToday,
    required this.lastDevice,
    required this.modelVersion,
    required this.rulesVersion,
    required this.apiUrl,
    required this.lastSync,
  });
}

class AdminMessage {
  final String id;
  final String label;
  final int score;
  final String text;
  final String source;
  final String sourceApp;
  final String deviceHash;
  final String userHash;
  final DateTime createdAt;
  final List<String> reasons;
  final int responseMs;
  final String requestId;
  final bool automatic;

  const AdminMessage({
    required this.id,
    required this.label,
    required this.score,
    required this.text,
    required this.source,
    required this.sourceApp,
    required this.deviceHash,
    required this.userHash,
    required this.createdAt,
    required this.reasons,
    required this.responseMs,
    required this.requestId,
    required this.automatic,
  });

  Color get color => label == 'خطر مرتفع'
      ? AppTokens.danger
      : label == 'مشبوه'
      ? AppTokens.warning
      : AppTokens.success;
}

enum AdminReportStatus { newReport, inReview, resolved, rejected }

class AdminReport {
  final String id;
  final String type;
  final String text;
  final String currentLabel;
  final String? note;
  AdminReportStatus status;
  final DateTime createdAt;
  final String userHash;

  AdminReport({
    required this.id,
    required this.type,
    required this.text,
    required this.currentLabel,
    this.note,
    required this.status,
    required this.createdAt,
    required this.userHash,
  });
}

String adminStatusLabel(AdminReportStatus status) {
  switch (status) {
    case AdminReportStatus.newReport:
      return 'جديد';
    case AdminReportStatus.inReview:
      return 'قيد المراجعة';
    case AdminReportStatus.resolved:
      return 'تم الحل';
    case AdminReportStatus.rejected:
      return 'مرفوض';
  }
}

Color adminStatusColor(AdminReportStatus status) {
  switch (status) {
    case AdminReportStatus.newReport:
      return AppTokens.brand;
    case AdminReportStatus.inReview:
      return AppTokens.warning;
    case AdminReportStatus.resolved:
      return AppTokens.success;
    case AdminReportStatus.rejected:
      return AppTokens.neutral;
  }
}

String maskSensitive(String input) {
  var value = input;
  value = value.replaceAll(RegExp(r'\b\d{4,8}\b'), '****');
  value = value.replaceAll(
    RegExp(r'([\w.%+-])[\w.%+-]*@([\w.-]+)'),
    r'$1***@$2',
  );
  value = value.replaceAll(RegExp(r'\b05\d{8}\b'), '05******');
  return value;
}

String shortTime(DateTime date) {
  final diff = DateTime.now().difference(date);
  if (diff.inMinutes < 1) return 'الآن';
  if (diff.inMinutes < 60) return 'منذ ${diff.inMinutes} د';
  if (diff.inHours < 24) return 'منذ ${diff.inHours} س';
  return 'منذ ${min(diff.inDays, 99)} يوم';
}
