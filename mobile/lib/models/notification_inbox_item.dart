import 'analysis_history_item.dart';
import 'analysis_result.dart';

class NotificationInboxItem {
  final String id;
  final int? notificationId;
  final String packageName;
  final String sourceAppPackage;
  final String sourceAppName;
  final String channel;
  final String sender;
  final String mentionedEntity;
  final String messageText;
  final String detectedUrl;
  final int riskScore;
  final String classification;
  final String title;
  final String content;
  final DateTime receivedAt;
  final AnalysisResult? result;

  NotificationInboxItem({
    required this.id,
    required this.notificationId,
    required String packageName,
    String? sourceAppPackage,
    String? sourceAppName,
    String? channel,
    String? sender,
    String? mentionedEntity,
    String? messageText,
    String? detectedUrl,
    int? riskScore,
    String? classification,
    required this.title,
    required this.content,
    required this.receivedAt,
    required this.result,
  }) : packageName = packageName.trim(),
       sourceAppPackage = (sourceAppPackage ?? packageName).trim(),
       sourceAppName = _safeAppName(
         sourceAppPackage ?? packageName,
         sourceAppName,
       ),
       channel =
           (channel ?? _channelForPackage(sourceAppPackage ?? packageName))
               .trim(),
       sender = _safeSender(
         sender ?? title,
         sourceAppPackage ?? packageName,
         _safeAppName(sourceAppPackage ?? packageName, sourceAppName),
       ),
       mentionedEntity = _safeMentionedEntity(
         mentionedEntity ??
             _extractMentionedEntity(
               [
                 messageText ?? content,
                 title,
               ].where((e) => e.trim().isNotEmpty).join('\n'),
             ),
       ),
       messageText = (messageText ?? content).trim(),
       detectedUrl =
           (detectedUrl ??
                   _extractFirstUrl(
                     [
                       title,
                       content,
                       messageText ?? '',
                     ].where((e) => e.trim().isNotEmpty).join('\n'),
                   ))
               .trim(),
       riskScore = result?.finalScore ?? riskScore ?? 0,
       classification = (result?.finalLabel ?? classification ?? 'unknown')
           .trim();

  factory NotificationInboxItem.fromNotification({
    required String id,
    required int? notificationId,
    required String packageName,
    required String title,
    required String content,
    required DateTime receivedAt,
    required AnalysisResult? result,
  }) {
    final sourceAppName = _safeAppName(packageName, null);
    final rawText = [
      title.trim(),
      content.trim(),
    ].where((e) => e.isNotEmpty).join('\n');
    final url = (result?.detectedUrl.trim().isNotEmpty ?? false)
        ? result!.detectedUrl.trim()
        : _extractFirstUrl(rawText);

    return NotificationInboxItem(
      id: id,
      notificationId: notificationId,
      packageName: packageName,
      sourceAppPackage: packageName,
      sourceAppName: sourceAppName,
      channel: _channelForPackage(packageName),
      sender: _safeSender(title, packageName, sourceAppName),
      mentionedEntity: _extractMentionedEntity(rawText),
      messageText: content.trim().isNotEmpty ? content.trim() : rawText,
      detectedUrl: url,
      riskScore: result?.finalScore ?? 0,
      classification: result?.finalLabel ?? 'unknown',
      title: title,
      content: content,
      receivedAt: receivedAt,
      result: result,
    );
  }

  bool get isAnalyzed => result != null;

  String get previewText {
    final text = [
      title.trim(),
      content.trim(),
    ].where((e) => e.isNotEmpty).join(' — ');
    if (text.isEmpty) return '';
    if (text.length <= 100) return text;
    return '${text.substring(0, 100)}...';
  }

  String get rawCombinedText {
    return [title.trim(), content.trim()].where((e) => e.isNotEmpty).join('\n');
  }

  AnalysisHistoryItem? toHistoryItem() {
    if (result == null) return null;
    final remoteId = result!.remoteId.trim();
    final serverText = result!.maskedText.trim();
    final serverUrl = result!.detectedUrl.trim();
    final url = serverUrl.isNotEmpty ? serverUrl : detectedUrl;

    return AnalysisHistoryItem(
      id: remoteId.isNotEmpty ? remoteId : id,
      sender: sender,
      rawText: serverText.isNotEmpty ? serverText : rawCombinedText,
      url: url,
      result: result!,
      createdAt: receivedAt,
      channel: channel,
      claimedEntityInput: mentionedEntity == 'غير محددة' ? '' : mentionedEntity,
      sourceTrust: remoteId.isNotEmpty ? 'server' : 'local',
      linkOpened: url.isEmpty ? 'no_link' : 'unknown',
    );
  }

  factory NotificationInboxItem.fromMap(Map<String, dynamic> map) {
    AnalysisResult? parsedResult;
    final rawResult = map['result'];
    if (rawResult is Map) {
      try {
        parsedResult = AnalysisResult.fromMap(
          Map<String, dynamic>.from(rawResult),
        );
      } catch (_) {
        parsedResult = null;
      }
    }

    final packageName = (map['sourceAppPackage'] ?? map['packageName'] ?? '')
        .toString();
    final title = (map['title'] ?? '').toString();
    final content = (map['content'] ?? '').toString();
    final sourceAppName = (map['sourceAppName'] ?? '').toString();
    final rawText = [
      title.trim(),
      content.trim(),
    ].where((e) => e.isNotEmpty).join('\n');

    return NotificationInboxItem(
      id: (map['id'] ?? '').toString(),
      notificationId: map['notificationId'] is int
          ? map['notificationId'] as int
          : int.tryParse('${map['notificationId']}'),
      packageName: packageName,
      sourceAppPackage: packageName,
      sourceAppName: sourceAppName.isEmpty
          ? _safeAppName(packageName, null)
          : sourceAppName,
      channel: (map['channel'] ?? _channelForPackage(packageName)).toString(),
      sender: (map['sender'] ?? _safeSender(title, packageName, sourceAppName))
          .toString(),
      mentionedEntity:
          (map['mentionedEntity'] ?? _extractMentionedEntity(rawText))
              .toString(),
      messageText: (map['messageText'] ?? content).toString(),
      detectedUrl:
          (map['detectedUrl'] ??
                  parsedResult?.detectedUrl ??
                  _extractFirstUrl(rawText))
              .toString(),
      riskScore: map['riskScore'] is int
          ? map['riskScore'] as int
          : int.tryParse('${map['riskScore']}') ??
                parsedResult?.finalScore ??
                0,
      classification:
          (map['classification'] ?? parsedResult?.finalLabel ?? 'unknown')
              .toString(),
      title: title,
      content: content,
      receivedAt: DateTime.tryParse('${map['receivedAt']}') ?? DateTime.now(),
      result: parsedResult,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'notificationId': notificationId,
      'packageName': packageName,
      'sourceAppPackage': sourceAppPackage,
      'sourceAppName': sourceAppName,
      'channel': channel,
      'sender': sender,
      'mentionedEntity': mentionedEntity,
      'messageText': messageText,
      'detectedUrl': detectedUrl,
      'riskScore': riskScore,
      'classification': classification,
      'title': title,
      'content': content,
      'receivedAt': receivedAt.toIso8601String(),
      'result': result?.toMap(),
    };
  }

  String get analysisChannel {
    switch (sourceAppPackage) {
      case 'com.google.android.gm':
        return 'email';
      case 'com.google.android.apps.messaging':
      case 'com.samsung.android.messaging':
      case 'com.android.mms':
        return 'sms';
      case 'com.whatsapp':
        return 'whatsapp';
      case 'org.telegram.messenger':
        return 'telegram';
      default:
        return 'notification';
    }
  }
}

const Map<String, String> _knownAppNames = {
  'com.whatsapp': 'WhatsApp',
  'org.telegram.messenger': 'Telegram',
  'com.google.android.gm': 'Gmail',
  'com.google.android.apps.messaging': 'Google Messages',
  'com.samsung.android.messaging': 'Samsung Messages',
  'com.android.mms': 'SMS',
};

String _safeAppName(String packageName, String? provided) {
  final value = provided?.trim() ?? '';
  if (value.isNotEmpty && !_looksLikePackageName(value)) return value;
  return _knownAppNames[packageName.trim()] ?? 'تطبيق';
}

String _channelForPackage(String packageName) {
  switch (packageName.trim()) {
    case 'com.whatsapp':
      return 'واتساب';
    case 'org.telegram.messenger':
      return 'تيليجرام';
    case 'com.google.android.gm':
      return 'Email';
    case 'com.google.android.apps.messaging':
    case 'com.samsung.android.messaging':
    case 'com.android.mms':
      return 'SMS';
    default:
      return 'إشعار تطبيق';
  }
}

String _safeSender(String value, String packageName, String appName) {
  final sender = value.trim();
  if (sender.isEmpty) return 'غير معروف';
  final normalized = sender.toLowerCase();
  if (normalized == packageName.toLowerCase()) return 'غير معروف';
  if (normalized == appName.toLowerCase()) return 'غير معروف';
  if (_looksLikePackageName(sender)) return 'غير معروف';
  return sender;
}

String _safeMentionedEntity(String value) {
  final entity = value.trim();
  if (entity.isEmpty || _looksLikePackageName(entity)) return 'غير محددة';
  return entity;
}

String _extractMentionedEntity(String text) {
  final lower = text.toLowerCase();
  if (lower.contains('بنك') ||
      lower.contains('مصرف') ||
      lower.contains('حساب بنكي') ||
      lower.contains('بطاقة')) {
    return 'بنك';
  }
  if (lower.contains('otp') || lower.contains('رمز تحقق')) return 'OTP';
  if (lower.contains('جامعة')) return 'جامعة';
  if (lower.contains('فيسبوك') || lower.contains('facebook')) return 'فيسبوك';
  if (lower.contains('واتساب') || lower.contains('whatsapp')) return 'واتساب';
  if (lower.contains('بريد') ||
      lower.contains('email') ||
      lower.contains('gmail')) {
    return 'بريد';
  }
  if (lower.contains('توصيل') ||
      lower.contains('delivery') ||
      lower.contains('shipping')) {
    return 'توصيل';
  }
  if (lower.contains('dhl')) return 'DHL';
  if (lower.contains('أرامكس') ||
      lower.contains('ارامكس') ||
      lower.contains('aramex')) {
    return 'أرامكس';
  }
  return 'غير محددة';
}

String _extractFirstUrl(String text) {
  final match = RegExp(
    r'((https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}([\/?#][^\s]*)?)',
    caseSensitive: false,
  ).firstMatch(text);
  return match?.group(0)?.trim() ?? '';
}

bool _looksLikePackageName(String value) {
  final trimmed = value.trim();
  return RegExp(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$').hasMatch(trimmed);
}
