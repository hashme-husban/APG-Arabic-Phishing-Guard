import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../models/analysis_history_item.dart';
import '../models/analysis_result.dart';
import 'device_service.dart';
import 'local_storage_service.dart';

class ApiConnectionSnapshot {
  final bool isConnected;
  final String? activeBaseUrl;
  final String lastTriedBaseUrl;
  final List<String> candidateBaseUrls;

  const ApiConnectionSnapshot({
    required this.isConnected,
    required this.activeBaseUrl,
    required this.lastTriedBaseUrl,
    required this.candidateBaseUrls,
  });
}

class ApgApiService {
  final String? preferredBaseUrl;

  const ApgApiService({this.preferredBaseUrl});

  static String? _cachedWorkingBaseUrl;
  static const Duration _healthTimeout = Duration(seconds: 2);
  static const Duration _analyzeTimeout = Duration(seconds: 22);
  static const Duration _dataTimeout = Duration(seconds: 14);

  List<String> _candidateBaseUrls() {
    final seen = <String>{};
    final ordered = <String>[
      if (_cachedWorkingBaseUrl != null) _cachedWorkingBaseUrl!,
      ...AppConfig.apiBaseCandidates(preferredBaseUrl),
    ];

    return ordered
        .map(AppConfig.normalizeBaseUrl)
        .where((value) => value.isNotEmpty && seen.add(value))
        .toList();
  }

  Map<String, String> _headers({bool json = false, bool auth = false}) {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    final token = LocalStorageService.instance.getSessionToken();
    if (auth &&
        token != null &&
        token.isNotEmpty &&
        !token.startsWith('demo-')) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<ApiConnectionSnapshot> checkConnection({
    bool forceRefresh = false,
  }) async {
    if (forceRefresh) _cachedWorkingBaseUrl = null;
    final candidates = _candidateBaseUrls();
    String lastTried = candidates.isNotEmpty
        ? candidates.first
        : AppConfig.normalizeBaseUrl(AppConfig.apiBaseUrl);
    for (final baseUrl in candidates) {
      lastTried = baseUrl;
      final endpoint = '$baseUrl/health';
      try {
        final response = await http
            .get(Uri.parse(endpoint))
            .timeout(_healthTimeout);
        if (_isHealthyResponse(response)) {
          _cachedWorkingBaseUrl = baseUrl;
          return ApiConnectionSnapshot(
            isConnected: true,
            activeBaseUrl: baseUrl,
            lastTriedBaseUrl: baseUrl,
            candidateBaseUrls: candidates,
          );
        }
        _logEndpointFailure(endpoint, 'HTTP ${response.statusCode}');
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    return ApiConnectionSnapshot(
      isConnected: false,
      activeBaseUrl: null,
      lastTriedBaseUrl: lastTried,
      candidateBaseUrls: candidates,
    );
  }

  bool _isHealthyResponse(http.Response response) {
    if (response.statusCode == 200) return true;
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map) return false;
      final data = decoded['data'] is Map
          ? Map<String, dynamic>.from(decoded['data'] as Map)
          : const <String, dynamic>{};
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

  Future<AnalysisResult> analyze({
    required String rawText,
    String sender = '',
    String url = '',
    List<String>? urls,
    String channel = 'manual',
    bool? isKnownContact,
    String senderTrust = 'unknown',
    String packageName = '',
    String sourceApp = '',
  }) async {
    final trimmedText = rawText.trim();
    final trimmedUrl = url.trim();
    final trimmedUrls = <String>{
      if (trimmedUrl.isNotEmpty) trimmedUrl,
      ...?urls?.map((value) => value.trim()).where((value) => value.isNotEmpty),
    }.toList();
    final trimmedSender = sender.trim();
    if (trimmedText.isEmpty && trimmedUrls.isEmpty) {
      throw Exception('الصق الرسالة أو الرابط أولًا.');
    }
    final primaryUrl = trimmedUrls.isNotEmpty ? trimmedUrls.first : '';
    final inputText = trimmedText.isNotEmpty ? trimmedText : primaryUrl;
    final source = _sourceFromChannel(
      channel,
      primaryUrl.isNotEmpty && trimmedText.isEmpty,
    );
    final device = const DeviceService();
    final body = <String, dynamic>{
      'input_text': inputText,
      'source': source,
      'device_id': device.deviceId,
      ...device.metadata(),
      if (trimmedSender.isNotEmpty) 'sender': trimmedSender,
      if (packageName.trim().isNotEmpty) 'package_name': packageName.trim(),
      if (sourceApp.trim().isNotEmpty) 'source_app': sourceApp.trim(),
      if (isKnownContact != null) 'is_known_contact': isKnownContact,
      if (senderTrust.trim().isNotEmpty) 'sender_trust': senderTrust.trim(),
      if (trimmedUrls.isNotEmpty) 'urls': trimmedUrls,
    };

    final token = LocalStorageService.instance.getSessionToken();
    if (token != null && token.isNotEmpty && !token.startsWith('demo-')) {
      return _tryAuthenticatedAnalyze(body);
    }

    return _legacyAnalyze(
      trimmedText,
      primaryUrl,
      trimmedSender,
      channel,
      isKnownContact: isKnownContact,
      senderTrust: senderTrust,
      packageName: packageName,
      sourceApp: sourceApp,
    );
  }

  Future<AnalysisResult> _tryAuthenticatedAnalyze(
    Map<String, dynamic> body,
  ) async {
    Object? lastConnectionError;
    for (final baseUrl in _candidateBaseUrls()) {
      final endpoint = '$baseUrl/analysis/analyze';
      try {
        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: _headers(json: true, auth: true),
              body: jsonEncode(body),
            )
            .timeout(_analyzeTimeout);
        if (response.statusCode == 401) {
          throw Exception('انتهت الجلسة، سجّل الدخول مرة أخرى');
        }
        if (response.statusCode == 400) {
          throw Exception('الصق الرسالة أو الرابط أولًا.');
        }
        if (response.statusCode >= 500) {
          throw Exception('تعذر إكمال التحليل. حاول مرة أخرى.');
        }
        if (response.statusCode != 200) {
          throw Exception('فشل التحليل (${response.statusCode}).');
        }
        _cachedWorkingBaseUrl = baseUrl;
        final decoded = jsonDecode(response.body);
        if (decoded is! Map) throw Exception('استجابة التحليل غير صالحة.');
        return AnalysisResult.fromJson(Map<String, dynamic>.from(decoded));
      } on SocketException catch (error) {
        lastConnectionError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      } on TimeoutException catch (error) {
        lastConnectionError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      }
    }
    throw Exception(
      lastConnectionError == null
          ? 'تعذر الاتصال بالخادم'
          : 'تعذر الاتصال بالخادم',
    );
  }

  Future<AnalysisResult> _legacyAnalyze(
    String rawText,
    String url,
    String sender,
    String channel, {
    bool? isKnownContact,
    String senderTrust = 'unknown',
    String packageName = '',
    String sourceApp = '',
  }) async {
    final inputText = rawText.isNotEmpty ? rawText : url;
    final body = <String, dynamic>{
      'input_text': inputText,
      'source': _sourceFromChannel(channel, url.isNotEmpty && rawText.isEmpty),
      'channel': channel,
      'response_view': 'public',
    };
    if (rawText.isNotEmpty) body['raw_text'] = rawText;
    if (sender.isNotEmpty) body['sender'] = sender;
    if (packageName.trim().isNotEmpty) {
      body['package_name'] = packageName.trim();
    }
    if (sourceApp.trim().isNotEmpty) body['source_app'] = sourceApp.trim();
    if (isKnownContact != null) body['is_known_contact'] = isKnownContact;
    if (senderTrust.trim().isNotEmpty) {
      body['sender_trust'] = senderTrust.trim();
    }
    if (url.isNotEmpty) body['urls'] = <String>[url];
    Object? lastConnectionError;
    for (final baseUrl in _candidateBaseUrls()) {
      final endpoint = '$baseUrl/analyze';
      try {
        final result = await _postLegacyAnalyze(baseUrl, body);
        _cachedWorkingBaseUrl = baseUrl;
        return result;
      } on SocketException catch (error) {
        lastConnectionError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      } on TimeoutException catch (error) {
        lastConnectionError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      } on http.ClientException catch (error) {
        lastConnectionError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      } on FormatException {
        throw Exception('استجابة الخادم ليست JSON صالحة.');
      } catch (error) {
        if (error is Exception) rethrow;
        throw Exception('تعذر إكمال التحليل. حاول مرة أخرى.');
      }
    }
    throw Exception(
      lastConnectionError == null
          ? 'تعذر الاتصال بالخادم'
          : 'تعذر الاتصال بالخادم',
    );
  }

  Future<AnalysisResult> _postLegacyAnalyze(
    String baseUrl,
    Map<String, dynamic> body,
  ) async {
    final endpoint = '$baseUrl/analyze';
    final response = await http
        .post(
          Uri.parse(endpoint),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(_analyzeTimeout);
    if (response.statusCode == 400) {
      throw Exception('الصق الرسالة أو الرابط أولًا.');
    }
    if (response.statusCode >= 500) {
      throw Exception('تعذر إكمال التحليل. حاول مرة أخرى.');
    }
    if (response.statusCode != 200) {
      throw Exception('فشل التحليل (${response.statusCode}).');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map) throw Exception('استجابة التحليل غير صالحة.');
    return AnalysisResult.fromJson(Map<String, dynamic>.from(decoded));
  }

  Future<List<AnalysisHistoryItem>> fetchHistory({
    String classification = 'all',
    String source = 'all',
    String search = '',
    int page = 1,
    int limit = 20,
  }) async {
    final token = LocalStorageService.instance.getSessionToken();
    if (token == null || token.startsWith('demo-')) {
      return <AnalysisHistoryItem>[];
    }
    for (final baseUrl in _candidateBaseUrls()) {
      final endpoint = '$baseUrl/analysis/history';
      final uri = Uri.parse(endpoint).replace(
        queryParameters: {
          'page': '$page',
          'limit': '$limit',
          if (classification != 'all') 'classification': classification,
          if (source != 'all') 'source': source,
          if (search.trim().isNotEmpty) 'search': search.trim(),
        },
      );
      try {
        final response = await http
            .get(uri, headers: _headers(auth: true))
            .timeout(_dataTimeout);
        if (response.statusCode != 200) continue;
        _cachedWorkingBaseUrl = baseUrl;
        final decoded = jsonDecode(response.body);
        final items = decoded is Map ? decoded['items'] : null;
        if (items is! List) return <AnalysisHistoryItem>[];
        return items
            .map(
              (e) => _historyItemFromApi(Map<String, dynamic>.from(e as Map)),
            )
            .toList();
      } catch (error) {
        _logEndpointFailure(endpoint, error);
      }
    }
    return <AnalysisHistoryItem>[];
  }

  Future<bool> deleteHistoryItem(String analysisId) async {
    final token = LocalStorageService.instance.getSessionToken();
    final id = int.tryParse(analysisId.trim()) ?? 0;
    if (token == null || token.startsWith('demo-') || id <= 0) return false;

    for (final baseUrl in _candidateBaseUrls()) {
      final endpoints = <String>[
        '$baseUrl/analysis/history/$id',
        '$baseUrl/analysis/$id',
      ];
      for (final endpoint in endpoints) {
        try {
          final response = await http
              .delete(Uri.parse(endpoint), headers: _headers(auth: true))
              .timeout(_dataTimeout);
          if (response.statusCode == 200 ||
              response.statusCode == 202 ||
              response.statusCode == 204 ||
              response.statusCode == 404) {
            _cachedWorkingBaseUrl = baseUrl;
            return true;
          }
          if (response.statusCode == 401) return false;
          _logEndpointFailure(endpoint, 'HTTP ${response.statusCode}');
        } catch (error) {
          _logEndpointFailure(endpoint, error);
        }
      }
    }
    return false;
  }

  Future<void> submitReport({
    required String analysisId,
    required String reportType,
    required String message,
  }) async {
    final token = LocalStorageService.instance.getSessionToken();
    if (token == null || token.startsWith('demo-')) {
      throw Exception('سجّل الدخول أولًا لإرسال البلاغ للأدمن.');
    }
    final id = int.tryParse(analysisId) ?? 0;
    if (id <= 0) {
      throw Exception('هذه النتيجة محلية ولا يمكن إرسال بلاغها للخادم.');
    }

    Object? lastError;
    for (final baseUrl in _candidateBaseUrls()) {
      final endpoint = '$baseUrl/reports';
      try {
        final response = await http
            .post(
              Uri.parse(endpoint),
              headers: _headers(json: true, auth: true),
              body: jsonEncode({
                'analysis_id': id,
                'report_type': reportType,
                'message': message,
              }),
            )
            .timeout(_dataTimeout);
        if (response.statusCode == 200 || response.statusCode == 201) {
          _cachedWorkingBaseUrl = baseUrl;
          return;
        }
        if (response.statusCode == 401) {
          throw Exception('انتهت الجلسة، سجّل الدخول مرة أخرى.');
        }
        if (response.statusCode == 404) {
          throw Exception('لم يتم العثور على نتيجة التحليل في الخادم.');
        }
        _logEndpointFailure(endpoint, 'HTTP ${response.statusCode}');
        lastError = 'HTTP ${response.statusCode}';
      } on SocketException catch (error) {
        lastError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      } on TimeoutException catch (error) {
        lastError = error;
        _cachedWorkingBaseUrl = null;
        _logEndpointFailure(endpoint, error);
      }
    }
    throw Exception(
      lastError == null ? 'تعذر إرسال البلاغ' : 'تعذر إرسال البلاغ',
    );
  }

  AnalysisHistoryItem _historyItemFromApi(Map<String, dynamic> json) {
    final result = AnalysisResult.fromJson(json);
    final text = (json['masked_text'] ?? json['maskedText'] ?? '').toString();
    final url = (json['detected_url'] ?? json['detectedUrl'] ?? '').toString();
    return AnalysisHistoryItem(
      id: (json['id'] ?? result.remoteId).toString(),
      sender: (json['source_app'] ?? '').toString(),
      rawText: text,
      url: url,
      result: result,
      createdAt:
          DateTime.tryParse((json['created_at'] ?? '').toString()) ??
          DateTime.now(),
      channel: (json['source'] ?? result.channel).toString(),
      selectedIndicators: const <String>[],
      sourceTrust: 'server',
      linkOpened: url.isEmpty ? 'no_link' : 'unknown',
    );
  }

  String _sourceFromChannel(String channel, bool urlOnly) {
    if (urlOnly) return 'link';
    switch (channel.toLowerCase().trim()) {
      case 'sms':
        return 'sms';
      case 'email':
        return 'email';
      case 'whatsapp':
        return 'whatsapp';
      case 'telegram':
        return 'notification';
      case 'notification':
        return 'notification';
      case 'url':
        return 'link';
      default:
        return 'manual';
    }
  }

  static void _log(String message) {
    if (kDebugMode) debugPrint('[APG API] $message');
  }

  static void _logEndpointFailure(String endpoint, Object error) {
    _log('Endpoint failed: $endpoint ($error)');
  }
}
