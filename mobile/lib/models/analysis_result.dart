class LayerBreakdownItem {
  final String keyName;
  final String status;
  final int score;

  LayerBreakdownItem({
    required this.keyName,
    required this.status,
    required this.score,
  });

  factory LayerBreakdownItem.fromEntry(String key, Map<String, dynamic> json) {
    return LayerBreakdownItem(
      keyName: key,
      status: (json['status'] ?? '').toString(),
      score: _readInt(json['score']),
    );
  }

  factory LayerBreakdownItem.fromMap(Map<String, dynamic> map) {
    return LayerBreakdownItem(
      keyName: (map['keyName'] ?? map['key_name'] ?? map['layer'] ?? '')
          .toString(),
      status: (map['status'] ?? '').toString(),
      score: _readInt(map['score']),
    );
  }

  Map<String, dynamic> toMap() {
    return {'keyName': keyName, 'status': status, 'score': score};
  }
}

class EntityReference {
  final String id;
  final String name;
  final String arabicName;
  final String type;

  const EntityReference({
    this.id = '',
    this.name = '',
    this.arabicName = '',
    this.type = '',
  });

  bool get hasUsefulData =>
      id.trim().isNotEmpty ||
      name.trim().isNotEmpty ||
      arabicName.trim().isNotEmpty ||
      type.trim().isNotEmpty;

  String get displayName {
    if (arabicName.trim().isNotEmpty) return arabicName.trim();
    if (name.trim().isNotEmpty) return name.trim();
    return id.trim();
  }

  factory EntityReference.fromJson(dynamic value) {
    if (value is! Map) return const EntityReference();
    final map = Map<String, dynamic>.from(value);
    return EntityReference(
      id: _firstString(map, ['id', 'entity_id', 'entityId']),
      name: _firstString(map, ['name', 'entity_name', 'entityName']),
      arabicName: _firstString(map, [
        'arabic_name',
        'arabicName',
        'primary_arabic_name',
      ]),
      type: _firstString(map, ['type', 'entity_type', 'entityType']),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      if (id.isNotEmpty) 'id': id,
      if (name.isNotEmpty) 'name': name,
      if (arabicName.isNotEmpty) 'arabicName': arabicName,
      if (type.isNotEmpty) 'type': type,
    };
  }
}

class EntitySummary {
  final EntityReference? claimed;
  final EntityReference? sender;
  final EntityReference? domain;
  final List<EntityReference> domainCandidates;
  final bool officialDomainMatch;
  final bool mismatch;
  final String mismatchType;
  final String linkDomain;
  final List<String> policyViolations;
  final String displayMessageAr;

  const EntitySummary({
    this.claimed,
    this.sender,
    this.domain,
    this.domainCandidates = const [],
    this.officialDomainMatch = false,
    this.mismatch = false,
    this.mismatchType = '',
    this.linkDomain = '',
    this.policyViolations = const [],
    this.displayMessageAr = '',
  });

  bool get hasUsefulData =>
      (claimed?.hasUsefulData ?? false) ||
      (sender?.hasUsefulData ?? false) ||
      (domain?.hasUsefulData ?? false) ||
      domainCandidates.any((e) => e.hasUsefulData) ||
      displayMessageAr.trim().isNotEmpty ||
      mismatch ||
      officialDomainMatch ||
      policyViolations.isNotEmpty;

  factory EntitySummary.fromJson(dynamic value) {
    if (value is! Map) return const EntitySummary();
    final map = Map<String, dynamic>.from(value);
    return EntitySummary(
      claimed: _nullableEntityReference(map['claimed']),
      sender: _nullableEntityReference(map['sender']),
      domain: _nullableEntityReference(map['domain']),
      domainCandidates: _readEntityReferenceList(
        map['domain_candidates'] ?? map['domainCandidates'],
      ),
      officialDomainMatch: _readBool(
        map['official_domain_match'] ?? map['officialDomainMatch'],
      ),
      mismatch: _readBool(map['mismatch']),
      mismatchType: _firstString(map, ['mismatch_type', 'mismatchType']),
      linkDomain: _firstString(map, ['link_domain', 'linkDomain']),
      policyViolations: _readStringList(
        map['policy_violations'] ?? map['policyViolations'],
      ),
      displayMessageAr: _firstString(map, [
        'display_message_ar',
        'displayMessageAr',
      ]),
    );
  }

  factory EntitySummary.fallback({
    required String claimedEntity,
    required String senderEntity,
    required String domainEntity,
    required bool entityConflict,
    required String linkDomain,
  }) {
    final claimed = claimedEntity.trim().isEmpty
        ? null
        : EntityReference(name: claimedEntity.trim());
    final sender = senderEntity.trim().isEmpty
        ? null
        : EntityReference(name: senderEntity.trim());
    final domain = domainEntity.trim().isEmpty
        ? null
        : EntityReference(name: domainEntity.trim());
    final summary = EntitySummary(
      claimed: claimed,
      sender: sender,
      domain: domain,
      linkDomain: linkDomain.trim(),
      mismatch: entityConflict,
      mismatchType: entityConflict ? 'entity_conflict' : '',
      displayMessageAr: entityConflict
          ? 'الجهة المذكورة لا تبدو متطابقة مع الرابط أو المرسل.'
          : '',
    );
    return summary.hasUsefulData ? summary : const EntitySummary();
  }

  Map<String, dynamic> toMap() {
    return {
      if (claimed != null) 'claimed': claimed!.toMap(),
      if (sender != null) 'sender': sender!.toMap(),
      if (domain != null) 'domain': domain!.toMap(),
      if (domainCandidates.isNotEmpty)
        'domainCandidates': domainCandidates.map((e) => e.toMap()).toList(),
      'officialDomainMatch': officialDomainMatch,
      'mismatch': mismatch,
      if (mismatchType.isNotEmpty) 'mismatchType': mismatchType,
      if (linkDomain.isNotEmpty) 'linkDomain': linkDomain,
      if (policyViolations.isNotEmpty) 'policyViolations': policyViolations,
      if (displayMessageAr.isNotEmpty) 'displayMessageAr': displayMessageAr,
    };
  }
}

class AnalysisResult {
  final String finalLabel;
  final int finalScore;
  final double confidence;
  final String headline;
  final String summary;
  final String recommendation;
  final String claimedEntity;
  final String senderEntity;
  final String domainEntity;
  final bool entityConflict;
  final EntitySummary entitySummary;
  final String channel;
  final String remoteId;
  final String maskedText;
  final String detectedUrl;
  final String createdAtIso;
  final List<String> reasons;
  final List<String> actionItems;
  final List<LayerBreakdownItem> layers;
  final String? messageIntent;
  final double? intentConfidence;
  final String? modality;
  final List<Map<String, dynamic>> matchedSignals;

  AnalysisResult({
    required this.finalLabel,
    required this.finalScore,
    required this.confidence,
    required this.headline,
    required this.summary,
    required this.recommendation,
    required this.claimedEntity,
    this.senderEntity = '',
    this.domainEntity = '',
    this.entityConflict = false,
    this.entitySummary = const EntitySummary(),
    required this.channel,
    this.remoteId = '',
    this.maskedText = '',
    this.detectedUrl = '',
    this.createdAtIso = '',
    required this.reasons,
    required this.actionItems,
    required this.layers,
    this.messageIntent,
    this.intentConfidence,
    this.modality,
    this.matchedSignals = const [],
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    // The backend can return one of three shapes depending on response_view:
    // 1) direct public result
    // 2) { public_result: {...}, mobile_result: {...}, debug_result: {...} }
    // 3) compact mobile result with label/score/top_reasons only
    final source = _selectResultBlock(json);
    final mobile = _asMap(json['mobile_result']);
    final public = _asMap(json['public_result']);

    final label = _normalizeLabel(
      _firstString(source, [
            'final_label',
            'finalLabel',
            'label',
            'classification',
          ])
          .ifEmpty(
            _firstString(mobile, [
              'final_label',
              'finalLabel',
              'label',
              'classification',
            ]),
          )
          .ifEmpty(
            _firstString(public, [
              'final_label',
              'finalLabel',
              'label',
              'classification',
            ]),
          ),
    );

    final score = _readInt(
      source['final_score'] ??
          source['finalScore'] ??
          source['risk_score'] ??
          source['score'] ??
          mobile['final_score'] ??
          mobile['finalScore'] ??
          mobile['risk_score'] ??
          mobile['score'] ??
          public['final_score'] ??
          public['risk_score'] ??
          public['score'],
    );

    final parsedReasons = _readStringList(
      source['reasons'] ??
          source['top_reasons'] ??
          mobile['top_reasons'] ??
          public['reasons'],
    );
    final parsedActions = _readStringList(
      source['action_items'] ??
          source['actionItems'] ??
          mobile['action_items'] ??
          public['action_items'],
    );

    final summary =
        _firstString(source, ['summary', 'short_summary', 'shortSummary'])
            .ifEmpty(
              _firstString(mobile, [
                'summary',
                'short_summary',
                'shortSummary',
              ]),
            )
            .ifEmpty(_fallbackSummary(label));

    final headline = _firstString(source, ['headline'])
        .ifEmpty(_firstString(mobile, ['headline']))
        .ifEmpty(_fallbackHeadline(label));

    final recommendation = _firstString(source, ['recommendation'])
        .ifEmpty(_firstString(public, ['recommendation']))
        .ifEmpty(_firstString(mobile, ['recommendation']))
        .ifEmpty(parsedActions.isNotEmpty ? parsedActions.first : '')
        .ifEmpty(_fallbackRecommendation(label));

    final rawIntent = _firstString(source, ['message_intent'])
        .ifEmpty(_firstString(source, ['messageIntent']))
        .ifEmpty(_firstString(mobile, ['message_intent']))
        .ifEmpty(_firstString(mobile, ['messageIntent']))
        .ifEmpty(_firstString(json, ['message_intent', 'messageIntent']));
    final rawModality = _firstString(source, ['modality'])
        .ifEmpty(_firstString(mobile, ['modality']))
        .ifEmpty(_firstString(json, ['modality']));
    final rawIntentConf =
        source['intent_confidence'] ??
        source['intentConfidence'] ??
        mobile['intent_confidence'] ??
        mobile['intentConfidence'] ??
        json['intentConfidence'] ??
        json['intent_confidence'];
    final claimedEntity =
        _entityName(source['claimed_entity'] ?? source['claimedEntity'])
            .ifEmpty(
              _entityName(public['claimed_entity'] ?? public['claimedEntity']),
            )
            .ifEmpty(
              _entityName(mobile['claimed_entity'] ?? mobile['claimedEntity']),
            )
            .ifEmpty(
              _entityName(json['claimed_entity'] ?? json['claimedEntity']),
            );
    final senderEntity =
        _entityName(source['sender_entity'] ?? source['senderEntity'])
            .ifEmpty(
              _entityName(public['sender_entity'] ?? public['senderEntity']),
            )
            .ifEmpty(
              _entityName(mobile['sender_entity'] ?? mobile['senderEntity']),
            )
            .ifEmpty(
              _entityName(json['sender_entity'] ?? json['senderEntity']),
            );
    final domainEntity =
        _entityName(source['domain_entity'] ?? source['domainEntity'])
            .ifEmpty(
              _entityName(public['domain_entity'] ?? public['domainEntity']),
            )
            .ifEmpty(
              _entityName(mobile['domain_entity'] ?? mobile['domainEntity']),
            )
            .ifEmpty(
              _entityName(json['domain_entity'] ?? json['domainEntity']),
            );
    final entityConflict = _readBool(
      source['entity_conflict'] ??
          source['entityConflict'] ??
          public['entity_conflict'] ??
          public['entityConflict'] ??
          mobile['entity_conflict'] ??
          mobile['entityConflict'] ??
          json['entity_conflict'] ??
          json['entityConflict'],
    );
    final detectedUrl = _firstString(source, [
      'detected_url',
      'detectedUrl',
    ]).ifEmpty(_firstString(json, ['detected_url', 'detectedUrl']));
    final parsedEntitySummary = EntitySummary.fromJson(
      source['entity_summary'] ??
          source['entitySummary'] ??
          public['entity_summary'] ??
          public['entitySummary'] ??
          mobile['entity_summary'] ??
          mobile['entitySummary'] ??
          json['entity_summary'] ??
          json['entitySummary'],
    );
    final entitySummary = parsedEntitySummary.hasUsefulData
        ? parsedEntitySummary
        : EntitySummary.fallback(
            claimedEntity: claimedEntity,
            senderEntity: senderEntity,
            domainEntity: domainEntity,
            entityConflict: entityConflict,
            linkDomain: detectedUrl,
          );

    return AnalysisResult(
      finalLabel: label.isEmpty ? 'suspicious' : label,
      finalScore: score,
      confidence: _readDouble(
        source['confidence'] ?? mobile['confidence'] ?? public['confidence'],
      ),
      headline: headline,
      summary: summary,
      recommendation: recommendation,
      claimedEntity: claimedEntity,
      senderEntity: senderEntity,
      domainEntity: domainEntity,
      entityConflict: entityConflict,
      entitySummary: entitySummary,
      channel: _firstString(source, [
        'channel',
        'source',
      ]).ifEmpty(_firstString(public, ['channel', 'source'])),
      remoteId: _firstString(source, [
        'id',
        'analysis_id',
      ]).ifEmpty(_firstString(json, ['id', 'analysis_id'])),
      maskedText: _firstString(source, [
        'masked_text',
        'maskedText',
      ]).ifEmpty(_firstString(json, ['masked_text', 'maskedText'])),
      detectedUrl: detectedUrl,
      createdAtIso: _firstString(source, [
        'created_at',
        'createdAt',
      ]).ifEmpty(_firstString(json, ['created_at', 'createdAt'])),
      reasons: parsedReasons,
      actionItems: parsedActions.isNotEmpty
          ? parsedActions
          : _fallbackActions(label),
      layers: _parseLayers(
        source['layer_breakdown'] ??
            public['layer_breakdown'] ??
            source['layers'],
      ),
      messageIntent: rawIntent.isEmpty ? null : rawIntent,
      intentConfidence: rawIntentConf == null
          ? null
          : _readDouble(rawIntentConf),
      modality: rawModality.isEmpty ? null : rawModality,
      matchedSignals: _readSignalList(
        source['matched_signals'] ??
            json['matched_signals'] ??
            json['matchedSignals'],
      ),
    );
  }

  factory AnalysisResult.fromMap(Map<String, dynamic> map) {
    return AnalysisResult.fromJson(map);
  }

  AnalysisResult copyWith({
    String? finalLabel,
    int? finalScore,
    double? confidence,
    String? headline,
    String? summary,
    String? recommendation,
    String? claimedEntity,
    String? senderEntity,
    String? domainEntity,
    bool? entityConflict,
    EntitySummary? entitySummary,
    String? channel,
    String? remoteId,
    String? maskedText,
    String? detectedUrl,
    String? createdAtIso,
    List<String>? reasons,
    List<String>? actionItems,
    List<LayerBreakdownItem>? layers,
    String? messageIntent,
    double? intentConfidence,
    String? modality,
    List<Map<String, dynamic>>? matchedSignals,
  }) {
    return AnalysisResult(
      finalLabel: finalLabel ?? this.finalLabel,
      finalScore: finalScore ?? this.finalScore,
      confidence: confidence ?? this.confidence,
      headline: headline ?? this.headline,
      summary: summary ?? this.summary,
      recommendation: recommendation ?? this.recommendation,
      claimedEntity: claimedEntity ?? this.claimedEntity,
      senderEntity: senderEntity ?? this.senderEntity,
      domainEntity: domainEntity ?? this.domainEntity,
      entityConflict: entityConflict ?? this.entityConflict,
      entitySummary: entitySummary ?? this.entitySummary,
      channel: channel ?? this.channel,
      remoteId: remoteId ?? this.remoteId,
      maskedText: maskedText ?? this.maskedText,
      detectedUrl: detectedUrl ?? this.detectedUrl,
      createdAtIso: createdAtIso ?? this.createdAtIso,
      reasons: reasons ?? this.reasons,
      actionItems: actionItems ?? this.actionItems,
      layers: layers ?? this.layers,
      messageIntent: messageIntent ?? this.messageIntent,
      intentConfidence: intentConfidence ?? this.intentConfidence,
      modality: modality ?? this.modality,
      matchedSignals: matchedSignals ?? this.matchedSignals,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'finalLabel': finalLabel,
      'finalScore': finalScore,
      'confidence': confidence,
      'headline': headline,
      'summary': summary,
      'recommendation': recommendation,
      'claimedEntity': claimedEntity,
      'senderEntity': senderEntity,
      'domainEntity': domainEntity,
      'entityConflict': entityConflict,
      if (entitySummary.hasUsefulData) 'entitySummary': entitySummary.toMap(),
      'channel': channel,
      'remoteId': remoteId,
      'maskedText': maskedText,
      'detectedUrl': detectedUrl,
      'createdAtIso': createdAtIso,
      'reasons': reasons,
      'actionItems': actionItems,
      'layers': layers.map((e) => e.toMap()).toList(),
      if (messageIntent != null) 'messageIntent': messageIntent,
      if (intentConfidence != null) 'intentConfidence': intentConfidence,
      if (modality != null) 'modality': modality,
      'matchedSignals': matchedSignals,
    };
  }
}

Map<String, dynamic> _selectResultBlock(Map<String, dynamic> json) {
  final public = _asMap(json['public_result']);
  if (public.isNotEmpty) return public;

  final output = _asMap(json['output']);
  final outputPublic = _asMap(output['public_result']);
  if (outputPublic.isNotEmpty) return outputPublic;

  final mobile = _asMap(json['mobile_result']);
  if (mobile.isNotEmpty) return mobile;

  return json;
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return <String, dynamic>{};
}

List<LayerBreakdownItem> _parseLayers(dynamic rawLayerBreakdown) {
  final layerOrder = <String>['sender', 'policy', 'text', 'url'];
  final parsedLayers = <LayerBreakdownItem>[];

  if (rawLayerBreakdown is Map) {
    final entries = rawLayerBreakdown.entries.toList()
      ..sort((a, b) {
        final aIndex = layerOrder.indexOf(a.key.toString());
        final bIndex = layerOrder.indexOf(b.key.toString());
        final safeA = aIndex == -1 ? 999 : aIndex;
        final safeB = bIndex == -1 ? 999 : bIndex;
        return safeA.compareTo(safeB);
      });

    for (final entry in entries) {
      final value = entry.value;
      if (value is Map) {
        parsedLayers.add(
          LayerBreakdownItem.fromEntry(
            entry.key.toString(),
            Map<String, dynamic>.from(value),
          ),
        );
      }
    }
  }

  if (rawLayerBreakdown is List) {
    for (final rawLayer in rawLayerBreakdown) {
      if (rawLayer is Map) {
        parsedLayers.add(
          LayerBreakdownItem.fromMap(Map<String, dynamic>.from(rawLayer)),
        );
      }
    }
  }

  return parsedLayers;
}

String _firstString(Map<String, dynamic> map, List<String> keys) {
  for (final key in keys) {
    final value = map[key];
    if (value != null) {
      final text = value.toString().trim();
      if (text.isNotEmpty) return text;
    }
  }
  return '';
}

int _readInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse('$value') ?? 0;
}

double _readDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? 0.0;
}

bool _readBool(dynamic value) {
  if (value is bool) return value;
  if (value is num) return value != 0;
  final text = value?.toString().trim().toLowerCase() ?? '';
  return text == 'true' || text == '1' || text == 'yes';
}

String _entityName(dynamic value) {
  if (value is Map) {
    final map = Map<String, dynamic>.from(value);
    return _firstString(map, ['entity_name', 'entityName', 'name']);
  }
  return value?.toString().trim() ?? '';
}

EntityReference? _nullableEntityReference(dynamic value) {
  final ref = EntityReference.fromJson(value);
  return ref.hasUsefulData ? ref : null;
}

List<EntityReference> _readEntityReferenceList(dynamic value) {
  if (value is List) {
    return value
        .map(EntityReference.fromJson)
        .where((entity) => entity.hasUsefulData)
        .toList();
  }
  return <EntityReference>[];
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

List<String> _readStringList(dynamic value) {
  if (value is List) {
    return value
        .map((e) => e.toString())
        .where((e) => e.trim().isNotEmpty)
        .toList();
  }
  return <String>[];
}

String _normalizeLabel(String value) {
  final normalized = value.trim().toLowerCase();
  if (normalized == 'legit' || normalized == 'benign' || normalized == 'ham') {
    return 'safe';
  }
  if (normalized == 'malicious' ||
      normalized == 'scam' ||
      normalized == 'dangerous' ||
      normalized == 'high_risk' ||
      normalized == 'high-risk') {
    return 'phishing';
  }
  if (normalized == 'warning' ||
      normalized == 'medium_risk' ||
      normalized == 'medium-risk') {
    return 'suspicious';
  }
  return normalized;
}

String _fallbackHeadline(String label) {
  switch (label) {
    case 'phishing':
      return 'High phishing risk detected';
    case 'safe':
      return 'No strong phishing evidence detected';
    default:
      return 'Suspicious message detected';
  }
}

String _fallbackSummary(String label) {
  switch (label) {
    case 'phishing':
      return 'The message shows strong phishing indicators across multiple layers.';
    case 'safe':
      return 'No strong phishing indicators were found, but sensitive actions should still use official channels.';
    default:
      return 'The message is not clearly safe and should be verified before any action.';
  }
}

String _fallbackRecommendation(String label) {
  switch (label) {
    case 'phishing':
      return 'Do not click the link, do not reply with OTPs or credentials, and verify the request through the official website or app.';
    case 'safe':
      return 'No strong phishing evidence was found. For sensitive actions, it is still safer to use the official website or app directly.';
    default:
      return 'Do not take action yet. Verify the message through an official channel before opening links or sharing any sensitive data.';
  }
}

List<String> _fallbackActions(String label) {
  switch (label) {
    case 'phishing':
      return <String>[
        'Do not click the link',
        'Do not reply with OTPs or credentials',
        'Verify through the official website or app',
      ];
    case 'safe':
      return <String>[
        'Use the official website or app for sensitive actions',
        'Stay cautious with future messages',
      ];
    default:
      return <String>[
        'Do not take action yet',
        'Verify through an official channel',
        'Avoid opening links until verified',
      ];
  }
}

extension _EmptyStringX on String {
  String ifEmpty(String fallback) => trim().isEmpty ? fallback : this;
}
