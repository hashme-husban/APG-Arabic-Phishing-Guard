import 'analysis_result.dart';

class AnalysisHistoryItem {
  final String id;
  final String sender;
  final String rawText;
  final String url;
  final AnalysisResult result;
  final DateTime createdAt;
  final String channel;
  final String claimedEntityInput;
  final String claimedEntityName;
  final String senderEntityName;
  final String domainEntityName;
  final bool entityConflict;
  final String? messageIntent;
  final double? intentConfidence;
  final String? modality;
  final List<Map<String, dynamic>> matchedSignals;
  final List<String> selectedIndicators;
  final String sourceTrust;
  final String linkOpened;
  final String notes;

  AnalysisHistoryItem({
    required this.id,
    required String sender,
    required this.rawText,
    required this.url,
    required this.result,
    required this.createdAt,
    this.channel = 'sms',
    String claimedEntityInput = '',
    String? claimedEntityName,
    String? senderEntityName,
    String? domainEntityName,
    bool? entityConflict,
    String? messageIntent,
    double? intentConfidence,
    String? modality,
    List<Map<String, dynamic>>? matchedSignals,
    this.selectedIndicators = const <String>[],
    this.sourceTrust = 'unsure',
    this.linkOpened = 'no_link',
    this.notes = '',
  }) : sender = _sanitizeSender(sender),
       claimedEntityInput = _sanitizeEntity(claimedEntityInput),
       claimedEntityName = _sanitizeEntity(
         claimedEntityName ?? result.claimedEntity,
       ),
       senderEntityName = _sanitizeEntity(
         senderEntityName ?? result.senderEntity,
       ),
       domainEntityName = _sanitizeEntity(
         domainEntityName ?? result.domainEntity,
       ),
       entityConflict = entityConflict ?? result.entityConflict,
       messageIntent = _emptyToNull(messageIntent ?? result.messageIntent),
       intentConfidence = intentConfidence ?? result.intentConfidence,
       modality = _emptyToNull(modality ?? result.modality),
       matchedSignals = matchedSignals ?? result.matchedSignals;

  String get previewText {
    final text = rawText.trim().isNotEmpty ? rawText.trim() : url.trim();
    if (text.isEmpty) return '';
    if (text.length <= 90) return text;
    return '${text.substring(0, 90)}...';
  }

  String get displayChannel {
    final source = channel.trim().toLowerCase();
    final resultChannel = result.channel.trim().toLowerCase();
    if (source.isNotEmpty && source != 'unknown') return source;
    if (resultChannel.isNotEmpty && resultChannel != 'unknown') {
      return resultChannel;
    }
    return 'manual';
  }

  String get displayEntity {
    if (claimedEntityInput.trim().isNotEmpty) {
      return _sanitizeEntity(claimedEntityInput);
    }
    final claimedEntity = _sanitizeEntity(result.claimedEntity);
    if (claimedEntity.isNotEmpty) return claimedEntity;
    if (claimedEntityName.isNotEmpty) return claimedEntityName;
    final domainEntity = _sanitizeEntity(result.domainEntity);
    if (domainEntity.isNotEmpty) return domainEntity;
    return domainEntityName;
  }

  factory AnalysisHistoryItem.fromMap(Map<String, dynamic> map) {
    final indicatorsRaw =
        map['selectedIndicators'] ?? map['indicators'] ?? <dynamic>[];
    final parsedResult = AnalysisResult.fromMap(
      Map<String, dynamic>.from(map['result'] ?? <String, dynamic>{}),
    );
    final claimedEntityName = _sanitizeEntity(
      _entityName(
        map['claimedEntityName'] ??
            map['claimed_entity_name'] ??
            map['claimed_entity'],
      ),
    );
    final senderEntityName = _sanitizeEntity(
      _entityName(
        map['senderEntityName'] ??
            map['sender_entity_name'] ??
            map['sender_entity'],
      ),
    );
    final domainEntityName = _sanitizeEntity(
      _entityName(
        map['domainEntityName'] ??
            map['domain_entity_name'] ??
            map['domain_entity'],
      ),
    );
    final messageIntent = _emptyToNull(
      (map['messageIntent'] ?? map['message_intent'] ?? '').toString(),
    );
    final modality = _emptyToNull((map['modality'] ?? '').toString());
    final matchedSignals = _readSignalList(
      map['matchedSignals'] ?? map['matched_signals'],
    );
    final restoredResult = parsedResult.copyWith(
      claimedEntity: parsedResult.claimedEntity.trim().isNotEmpty
          ? parsedResult.claimedEntity
          : claimedEntityName,
      senderEntity: parsedResult.senderEntity.trim().isNotEmpty
          ? parsedResult.senderEntity
          : senderEntityName,
      domainEntity: parsedResult.domainEntity.trim().isNotEmpty
          ? parsedResult.domainEntity
          : domainEntityName,
      entityConflict:
          parsedResult.entityConflict ||
          _readBool(map['entityConflict'] ?? map['entity_conflict']),
      messageIntent: parsedResult.messageIntent ?? messageIntent,
      intentConfidence:
          parsedResult.intentConfidence ??
          _readNullableDouble(
            map['intentConfidence'] ?? map['intent_confidence'],
          ),
      modality: parsedResult.modality ?? modality,
      matchedSignals: parsedResult.matchedSignals.isNotEmpty
          ? parsedResult.matchedSignals
          : matchedSignals,
    );
    return AnalysisHistoryItem(
      id: (map['id'] ?? '').toString(),
      sender: (map['sender'] ?? '').toString(),
      rawText: (map['rawText'] ?? '').toString(),
      url: (map['url'] ?? '').toString(),
      result: restoredResult,
      createdAt: DateTime.tryParse('${map['createdAt']}') ?? DateTime.now(),
      channel: (map['channel'] ?? map['messageType'] ?? 'sms').toString(),
      claimedEntityInput:
          (map['claimedEntityInput'] ?? map['claimedEntity'] ?? '').toString(),
      claimedEntityName: claimedEntityName,
      senderEntityName: senderEntityName,
      domainEntityName: domainEntityName,
      entityConflict: restoredResult.entityConflict,
      messageIntent: restoredResult.messageIntent,
      intentConfidence: restoredResult.intentConfidence,
      modality: restoredResult.modality,
      matchedSignals: restoredResult.matchedSignals,
      selectedIndicators: indicatorsRaw is List
          ? indicatorsRaw.map((e) => e.toString()).toList()
          : <String>[],
      sourceTrust: (map['sourceTrust'] ?? 'unsure').toString(),
      linkOpened: (map['linkOpened'] ?? 'no_link').toString(),
      notes: (map['notes'] ?? '').toString(),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'sender': sender,
      'rawText': rawText,
      'url': url,
      'result': result.toMap(),
      'createdAt': createdAt.toIso8601String(),
      'channel': channel,
      'claimedEntityInput': claimedEntityInput,
      'claimedEntityName': claimedEntityName,
      'senderEntityName': senderEntityName,
      'domainEntityName': domainEntityName,
      'entityConflict': entityConflict,
      if (messageIntent != null) 'messageIntent': messageIntent,
      if (intentConfidence != null) 'intentConfidence': intentConfidence,
      if (modality != null) 'modality': modality,
      'matchedSignals': matchedSignals,
      'selectedIndicators': selectedIndicators,
      'sourceTrust': sourceTrust,
      'linkOpened': linkOpened,
      'notes': notes,
    };
  }
}

String _sanitizeSender(String value) {
  final trimmed = value.trim();
  if (trimmed.isEmpty || _looksLikePackageName(trimmed)) return '';
  return trimmed;
}

String _sanitizeEntity(String value) {
  final trimmed = value.trim();
  if (trimmed.isEmpty || _looksLikePackageName(trimmed)) return '';
  return trimmed;
}

bool _looksLikePackageName(String value) {
  return RegExp(
    r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$',
  ).hasMatch(value.trim());
}

String? _emptyToNull(String? value) {
  final trimmed = value?.trim() ?? '';
  return trimmed.isEmpty ? null : trimmed;
}

bool _readBool(dynamic value) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  final text = value?.toString().trim().toLowerCase() ?? '';
  return text == 'true' || text == '1' || text == 'yes';
}

double? _readNullableDouble(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

List<Map<String, dynamic>> _readSignalList(dynamic value) {
  if (value is List) {
    return value
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
  }
  return <Map<String, dynamic>>[];
}

String _entityName(dynamic value) {
  if (value is Map) {
    final map = Map<String, dynamic>.from(value);
    return (map['entity_name'] ?? map['entityName'] ?? map['name'] ?? '')
        .toString();
  }
  return (value ?? '').toString();
}
