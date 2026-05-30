import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_result.dart';
import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';
import '../utils/analysis_share_helper.dart';
import '../utils/text_mapper.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/apg_ui.dart';
import '../widgets/circular_score_meter.dart';
import '../widgets/feedback_report_sheet.dart';
import 'evaluation_details_screen.dart';
import '../widgets/motion.dart';

class _ReasonSection {
  final String title;
  final List<String> items;

  const _ReasonSection(this.title, this.items);
}

class _UrlChip {
  final String label;
  final IconData icon;
  final Color color;

  const _UrlChip({
    required this.label,
    required this.icon,
    required this.color,
  });
}

class ResultDetailsScreen extends StatelessWidget {
  final AnalysisHistoryItem item;
  final VoidCallback? onDelete;
  final String? sourceTag;

  const ResultDetailsScreen({
    super.key,
    required this.item,
    this.onDelete,
    this.sourceTag,
  });

  Color get _color => TextMapper.riskColor(item.result.finalLabel);
  bool get _isHigh => item.result.finalLabel.toLowerCase() == 'phishing';
  bool get _isSafe => item.result.finalLabel.toLowerCase() == 'safe';

  String _title(BuildContext context) {
    final l10n = context.l10n;
    if (_isHigh) return l10n.highRiskTitle;
    if (_isSafe) return l10n.safeResultTitle;
    return l10n.suspiciousResultTitle;
  }

  String _description(BuildContext context) {
    if (_isHigh) return 'توجد مؤشرات قوية على تصيد أو احتيال.';
    if (_isSafe) return 'لا توجد مؤشرات خطيرة واضحة.';
    return 'تحتاج الرسالة إلى تحقق قبل التفاعل معها.';
  }

  IconData get _icon {
    if (_isHigh) return Icons.gpp_bad_rounded;
    if (_isSafe) return Icons.verified_user_rounded;
    return Icons.warning_amber_rounded;
  }

  bool _looksLikePackageName(String value) {
    return RegExp(
      r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$',
    ).hasMatch(value.trim());
  }

  String _displaySender(BuildContext context) {
    final value = item.sender.trim();
    if (value.isEmpty ||
        value.toLowerCase() == 'unknown' ||
        _looksLikePackageName(value)) {
      return context.l10n.unknownLabel;
    }
    return value;
  }

  String _displayEntity(BuildContext context) {
    final value = item.displayEntity.trim();
    if (value.isEmpty || _looksLikePackageName(value)) {
      return context.l10n.unspecifiedLabel;
    }
    if (_hasEntityImpersonationCue) {
      return '$value — ${context.l10n.possibleImpersonation}';
    }
    return value;
  }

  EntitySummary get _entitySummary => item.result.entitySummary;

  String get _entityClaimedDisplay {
    final claimed = _entitySummary.claimed?.displayName.trim() ?? '';
    if (claimed.isNotEmpty) return claimed;
    final value = item.displayEntity.trim();
    if (value.isEmpty || _looksLikePackageName(value)) return '';
    return value;
  }

  String get _entityDomainDisplay {
    final domainEntity = _entitySummary.domain?.displayName.trim() ?? '';
    if (domainEntity.isNotEmpty) return domainEntity;
    final value = item.result.domainEntity.trim();
    if (value.isEmpty || _looksLikePackageName(value)) return '';
    return value;
  }

  String get _entityTypeDisplay {
    final type = _entitySummary.claimed?.type.trim() ?? '';
    if (type.isEmpty) return '';
    return type.replaceAll('_', ' ');
  }

  String get _entitySummaryDomain {
    final value = _entitySummary.linkDomain.trim();
    if (value.isNotEmpty) {
      final parsed = _extractDomain(value);
      return parsed.isEmpty ? value : parsed;
    }
    return _detectedDomain;
  }

  bool get _hasEntitySummaryCard {
    return _entitySummary.hasUsefulData ||
        _entityClaimedDisplay.isNotEmpty ||
        _entityDomainDisplay.isNotEmpty ||
        item.result.entityConflict;
  }

  String get _displayUrl {
    final url = item.url.trim();
    if (url.isNotEmpty) return url;
    final text = item.rawText.trim();
    final urlPattern = RegExp(
      r'^(?:https?:\/\/|www\.)\S+$',
      caseSensitive: false,
    );
    return urlPattern.hasMatch(text) ? text : '';
  }

  bool get _hasUrl => _displayUrl.isNotEmpty;

  String get _detectedDomain => _extractDomain(_displayUrl);

  String _extractDomain(String value) {
    var text = value.trim();
    if (text.isEmpty) return '';
    final hasScheme = RegExp(
      r'^[a-z][a-z0-9+.-]*://',
      caseSensitive: false,
    ).hasMatch(text);
    final uri = Uri.tryParse(hasScheme ? text : 'https://$text');
    var host = uri?.host ?? '';
    if (host.isEmpty) {
      host = text.split(RegExp(r'[/?#]')).first;
    }
    host = host.split('@').last.split(':').first.toLowerCase();
    if (host.startsWith('www.')) host = host.substring(4);
    return host;
  }

  bool get _isUrlOnly {
    final modality = item.result.modality?.trim().toLowerCase();
    if (modality == 'url_only') return true;
    final text = item.rawText.trim();
    if (text.isEmpty) return _hasUrl;
    final urlPattern = RegExp(
      r'^(?:https?:\/\/|www\.)\S+$',
      caseSensitive: false,
    );
    return urlPattern.hasMatch(text);
  }

  String get _displayChannel {
    final value = item.displayChannel.trim();
    if (value.isEmpty || _looksLikePackageName(value)) return 'يدوي';
    return value;
  }

  bool get _isNotificationChannel {
    final value = _displayChannel.toLowerCase();
    return value == 'notification' ||
        value == 'إشعار تطبيق' ||
        value == 'واتساب' ||
        value == 'تيليجرام' ||
        value == 'sms' ||
        value == 'email';
  }

  String get _intelligenceText {
    final signals = item.result.matchedSignals.map(_signalText).join(' ');
    return '${item.result.messageIntent ?? ''} ${item.result.reasons.join(' ')} $signals ${item.rawText} ${item.url}'
        .toLowerCase();
  }

  bool get _hasCredentialOrOtpRisk => [
    'otp',
    'credential',
    'password',
    'cvv',
    'card_data',
    'verification code',
    'رمز',
    'كلمة المرور',
    'بطاقة',
  ].any((value) => _intelligenceText.contains(value));

  bool get _hasBankingOrPaymentContext => [
    'bank',
    'banking',
    'payment',
    'card',
    'cvv',
    'iban',
    'financial',
    'بنك',
    'دفع',
    'بطاقة',
    'حساب',
  ].any((value) => _intelligenceText.contains(value));

  bool get _hasClearImpersonationSignal => [
    'brand_impersonation',
    'url_misleading_brand_in_url',
    'entity_conflict',
    'impersonation',
  ].any((value) => _intelligenceText.contains(value));

  bool get _hasSuspiciousEntityLink =>
      _hasUrl &&
      _displayEntityBase != 'غير محددة' &&
      (_hasClearImpersonationSignal ||
          item.result.entityConflict ||
          item.result.finalLabel.toLowerCase() == 'phishing' ||
          item.result.finalLabel.toLowerCase() == 'suspicious');

  bool get _hasEntityImpersonationCue =>
      _hasUrl &&
      _displayEntityBase != 'غير محددة' &&
      (_hasClearImpersonationSignal || item.result.entityConflict);

  bool get _hasSuspiciousUrl {
    if (!_hasUrl) return false;
    if (_hasEntityImpersonationCue || _hasSuspiciousEntityLink) return true;
    final urlLayers = item.result.layers.where(
      (layer) => layer.keyName.toLowerCase() == 'url',
    );
    if (urlLayers.any((layer) => layer.score >= 55)) return true;
    return [
      'malicious_url',
      'suspicious_url',
      'url_virustotal_malicious',
      'url_virustotal_suspicious',
      'suspicious_tld',
      'punycode',
      'shortener',
    ].any((value) => _intelligenceText.contains(value));
  }

  bool get _hasUrlShortener =>
      _intelligenceText.contains('shortener') ||
      _intelligenceText.contains('short_url') ||
      _intelligenceText.contains('url_shortener') ||
      _isKnownShortenerDomain(_detectedDomain);

  bool _isKnownShortenerDomain(String domain) => const [
    'bit.ly',
    'tinyurl.com',
    'goo.gl',
    't.co',
    'ow.ly',
    'rb.gy',
    'cutt.ly',
    'is.gd',
    'short.io',
    'tiny.cc',
    'lnkd.in',
    'buff.ly',
  ].contains(domain);

  bool get _hasSuspiciousTld =>
      _intelligenceText.contains('suspicious_tld') ||
      _intelligenceText.contains('punycode');

  bool get _hasComplexUrlStructure {
    final url = _displayUrl.trim();
    if (url.isEmpty) return false;
    final hasScheme = RegExp(
      r'^[a-z][a-z0-9+.-]*://',
      caseSensitive: false,
    ).hasMatch(url);
    final uri = Uri.tryParse(hasScheme ? url : 'https://$url');
    final pathSegments =
        uri?.pathSegments
            .where((segment) => segment.trim().isNotEmpty)
            .length ??
        0;
    final queryItems = uri?.queryParameters.length ?? 0;
    return pathSegments >= 2 || queryItems >= 2 || url.contains('@');
  }

  List<_UrlChip> get _urlSignalChips {
    if (!_hasUrl) return [];
    final chips = <_UrlChip>[];
    final url = _displayUrl.toLowerCase();
    final intel = _intelligenceText;

    if (_hasClearImpersonationSignal || item.result.entityConflict) {
      chips.add(
        const _UrlChip(
          label: 'انتحال جهة',
          icon: Icons.person_off_rounded,
          color: AppTokens.danger,
        ),
      );
    }
    if (_hasSuspiciousTld) {
      chips.add(
        const _UrlChip(
          label: 'نطاق مريب',
          icon: Icons.warning_amber_rounded,
          color: AppTokens.danger,
        ),
      );
    }
    if (url.contains('verify') || url.contains('verification')) {
      chips.add(
        const _UrlChip(
          label: 'تحقق',
          icon: Icons.verified_user_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (url.contains('login') || url.contains('signin')) {
      chips.add(
        const _UrlChip(
          label: 'تسجيل دخول',
          icon: Icons.login_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (url.contains('update') ||
        url.contains('account') ||
        intel.contains('account_update')) {
      chips.add(
        const _UrlChip(
          label: 'تحديث حساب',
          icon: Icons.manage_accounts_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (url.contains('pay') || intel.contains('payment')) {
      chips.add(
        const _UrlChip(
          label: 'دفع',
          icon: Icons.payment_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (intel.contains('bank') || intel.contains('بنك')) {
      chips.add(
        const _UrlChip(
          label: 'بنك',
          icon: Icons.account_balance_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (url.contains('auth') ||
        url.contains('secure') ||
        url.contains('confirm') ||
        url.contains('password')) {
      chips.add(
        const _UrlChip(
          label: 'تحقق إضافي',
          icon: Icons.manage_search_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (_hasUrlShortener) {
      chips.add(
        const _UrlChip(
          label: 'رابط مختصر',
          icon: Icons.link_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    if (chips.isEmpty && _hasSuspiciousUrl) {
      chips.add(
        const _UrlChip(
          label: 'تحقق إضافي',
          icon: Icons.search_rounded,
          color: AppTokens.warning,
        ),
      );
    }
    return chips.take(6).toList();
  }

  String get _displayEntityBase {
    final value = item.displayEntity.trim();
    if (value.isEmpty || _looksLikePackageName(value)) return 'غير محددة';
    return value;
  }

  String get _riskConfidenceLabel {
    final score = item.result.finalScore.clamp(0, 100);
    if (score <= 25) return 'منخفض جدًا';
    if (score <= 50) return 'منخفض';
    if (score <= 70) return 'متوسط';
    if (score <= 85) return 'مرتفع';
    return 'مرتفع جدًا';
  }

  String _confidenceLabel(double confidence) {
    final percent = confidence > 1
        ? confidence.round()
        : (confidence * 100).round();
    if (percent <= 35) return 'ثقة منخفضة';
    if (percent <= 65) return 'ثقة متوسطة';
    return 'ثقة عالية';
  }

  String _confidenceText(double? confidence) {
    if (confidence == null || confidence <= 0) return '';
    final percent = confidence > 1
        ? confidence.round()
        : (confidence * 100).round();
    return '${_confidenceLabel(confidence)} • $percent%';
  }

  int? _heroConfidencePercent() {
    final confidence = item.result.confidence;
    if (confidence <= 0) return null;
    final percent = confidence > 1
        ? confidence.round()
        : (confidence * 100).round();
    return percent.clamp(1, 100).toInt();
  }

  Widget _confidenceBadge(BuildContext context) {
    final percent = _heroConfidencePercent();
    if (percent == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context).withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.48),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.insights_rounded,
            size: 14,
            color: AppTokens.mutedText(context),
          ),
          const SizedBox(width: 6),
          Text(
            'الثقة $percent%',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w900,
              height: 1.1,
            ),
          ),
        ],
      ),
    );
  }

  String get _severityStripText {
    if (_hasEntityImpersonationCue || _hasClearImpersonationSignal) {
      return 'يوجد انتحال لجهة معروفة.';
    }
    if (_hasSuspiciousUrl) return 'تم رصد رابط غير موثوق.';
    if (_hasCredentialOrOtpRisk || _hasBankingOrPaymentContext) {
      return 'الرسالة تطلب إجراءً حساسًا.';
    }
    if (_isSafe) return 'لا توجد مؤشرات تصيد مباشرة.';
    return 'تحتاج الرسالة إلى تحقق إضافي.';
  }

  Future<void> _copyDetails(BuildContext context) async {
    await Clipboard.setData(
      ClipboardData(text: AnalysisShareHelper.buildShareText(context, item)),
    );
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(context.l10n.detailsCopied)));
  }

  Future<void> _shareDetails(BuildContext context) async {
    await AnalysisShareHelper.shareAnalysis(context, item);
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(context.l10n.shareOpened)));
  }

  Future<void> _copyMessage(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: item.rawText.trim()));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(context.l10n.messageCopied)));
  }

  Future<void> _copyUrl(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: _displayUrl));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(context.l10n.urlCopied)));
  }

  Future<void> _deleteItem(BuildContext context) async {
    if (onDelete == null) return;
    final l10n = context.l10n;
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(l10n.confirmDeleteHistoryItemTitle),
            content: Text(l10n.deleteFromHistoryContent),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(l10n.cancel),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(l10n.delete),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;
    onDelete!.call();
    if (context.mounted) {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(context.l10n.historyDeleted)));
    }
  }

  double get _pulseAlpha {
    if (_isHigh) return 0.42;
    if (_isSafe) return 0.20;
    return 0.30;
  }

  double get _pulseExpand {
    if (_isHigh) return 44;
    if (_isSafe) return 28;
    return 36;
  }

  Widget _hero(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.all(22),
      gradient: AppTokens.riskGradient(item.result.finalLabel),
      border: Border.all(
        color: _color.withValues(alpha: _isHigh ? 0.72 : 0.28),
        width: _isHigh ? 1.8 : 1.2,
      ),
      glow: _isHigh,
      child: Column(
        children: [
          // Risk badge + title
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusBadge(
                label: TextMapper.label(context, item.result.finalLabel),
                color: _color,
                icon: _icon,
              ),
              _confidenceBadge(context),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            _title(context),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w900,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _description(context),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 22),
          // Large score core — pulse for ALL risk levels
          ProtectionPulseRing(
            color: _color,
            size: 148,
            maxAlpha: _pulseAlpha,
            maxExpand: _pulseExpand,
            child: CircularScoreMeter(
              score: item.result.finalScore,
              color: _color,
              size: 148,
              caption: context.l10n.score,
            ),
          ),
          const SizedBox(height: 18),
          // APG Risk Engine verdict row
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withValues(alpha: 0.10)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.biotech_rounded,
                  color: AppTokens.brandCyan,
                  size: 15,
                ),
                const SizedBox(width: 7),
                Text(
                  'APG Risk Engine',
                  style: TextStyle(
                    color: AppTokens.brandCyan,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(width: 10),
                Container(
                  width: 1,
                  height: 12,
                  color: Colors.white.withValues(alpha: 0.20),
                ),
                const SizedBox(width: 10),
                Flexible(
                  child: Text(
                    _severityStripText,
                    maxLines: 2,
                    textAlign: TextAlign.right,
                    style: TextStyle(
                      color: _color,
                      fontWeight: FontWeight.w900,
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (sourceTag != null) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: AppTokens.brandCyan.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppTokens.brandCyan.withValues(alpha: 0.22),
                ),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.qr_code_rounded,
                    size: 14,
                    color: AppTokens.brandCyan,
                  ),
                  const SizedBox(width: 7),
                  Flexible(
                    child: Text(
                      'مصدر التحليل: تم استخراج المحتوى من رمز QR',
                      style: TextStyle(
                        color: AppTokens.brandCyan,
                        fontWeight: FontWeight.w900,
                        fontSize: 11.5,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _messageInfo(BuildContext context) {
    final l10n = context.l10n;
    return Column(
      children: [
        Row(
          children: [
            MetricCard(
              title: l10n.channel,
              value: TextMapper.channel(context, _displayChannel),
              icon: Icons.sms_rounded,
              color: AppTokens.brandCyan,
            ),
            const SizedBox(width: 10),
            MetricCard(
              title: l10n.claimedEntity,
              value: _displayEntity(context),
              icon: Icons.apartment_rounded,
              color: _hasEntityImpersonationCue
                  ? AppTokens.warning
                  : AppTokens.success,
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            MetricCard(
              title: l10n.sender,
              value: _displaySender(context),
              icon: Icons.person_rounded,
              color: AppTokens.warning,
            ),
            const SizedBox(width: 10),
            MetricCard(
              title: l10n.url,
              value: _hasUrl ? l10n.urlPresent : l10n.urlAbsent,
              icon: Icons.link_rounded,
              color: _hasUrl ? AppTokens.warning : AppTokens.neutral,
            ),
          ],
        ),
        if (item.result.entityConflict) ...[
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTokens.warning.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppTokens.warning.withValues(alpha: 0.24),
              ),
            ),
            child: Text(
              l10n.entityConflictWarning,
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppTokens.warning,
                height: 1.5,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _investigationContextCard(BuildContext context) {
    final domain = _detectedDomain;
    final scheme = _displayUrl.trim().toLowerCase().startsWith('https://')
        ? 'HTTPS'
        : (_hasUrl ? 'HTTP / غير مؤكد' : 'غير متاح');
    final schemeColor = scheme == 'HTTPS'
        ? AppTokens.success
        : (_hasUrl ? AppTokens.warning : AppTokens.neutral);

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'سياق الرسالة والرابط',
            subtitle: 'المصدر والرابط الذي بنى عليه APG التحقيق.',
            icon: Icons.travel_explore_rounded,
          ),
          const SizedBox(height: 14),
          if (_hasUrl) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: AppTokens.surfaceAlt(context).withValues(alpha: 0.68),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: _urlStatusColor.withValues(alpha: 0.24),
                ),
              ),
              child: Text(
                _displayUrl,
                textDirection: TextDirection.ltr,
                textAlign: TextAlign.left,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTokens.brandCyan,
                  height: 1.45,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _contextMiniCard(
                    context,
                    title: 'النطاق',
                    value: domain.isEmpty ? 'تعذر التحقق' : domain,
                    icon: Icons.domain_rounded,
                    color: _urlStatusColor,
                    ltrValue: domain.isNotEmpty,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _contextMiniCard(
                    context,
                    title: 'حالة الاتصال',
                    value: scheme,
                    icon: scheme == 'HTTPS'
                        ? Icons.lock_rounded
                        : Icons.lock_open_rounded,
                    color: schemeColor,
                  ),
                ),
              ],
            ),
          ] else ...[
            _contextNotice(
              context,
              icon: Icons.link_off_rounded,
              color: AppTokens.neutral,
              text:
                  'لم يتم العثور على رابط داخل الرسالة، لذلك ركز التحقيق على النص والمرسل والمؤشرات المتاحة.',
            ),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'المرسل',
                  value: _displaySender(context),
                  icon: Icons.person_rounded,
                  color: AppTokens.warning,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'القناة',
                  value: TextMapper.channel(context, _displayChannel),
                  icon: _isNotificationChannel
                      ? Icons.notifications_active_rounded
                      : Icons.edit_note_rounded,
                  color: AppTokens.brandCyan,
                ),
              ),
            ],
          ),
          if (_displayEntityBase != 'غير محددة') ...[
            const SizedBox(height: 10),
            _contextNotice(
              context,
              icon: item.result.entityConflict
                  ? Icons.account_tree_rounded
                  : Icons.apartment_rounded,
              color: item.result.entityConflict
                  ? AppTokens.warning
                  : AppTokens.brandCyan,
              text: item.result.entityConflict
                  ? 'الجهة المذكورة لا تبدو متسقة تماماً مع الرابط أو المرسل.'
                  : 'الجهة المذكورة: $_displayEntityBase',
            ),
          ],
        ],
      ),
    );
  }

  Widget _entityIntelligenceCard(BuildContext context) {
    final claimed = _entityClaimedDisplay;
    final domainEntity = _entityDomainDisplay;
    final entityType = _entityTypeDisplay;
    final domain = _entitySummaryDomain;
    final hasMismatch = _entitySummary.mismatch || item.result.entityConflict;
    final hasOfficialMatch = _entitySummary.officialDomainMatch;
    final statusText = hasOfficialMatch
        ? 'متطابق'
        : (domain.isEmpty ? 'لم يتم التحقق' : 'غير متطابق');
    final conflictText = hasMismatch ? 'يوجد تعارض' : 'لا يوجد تعارض';
    final note = _entitySummary.displayMessageAr.trim().isNotEmpty
        ? _entitySummary.displayMessageAr.trim()
        : (claimed.isEmpty
              ? 'لم يتم التعرف على جهة محددة.'
              : hasMismatch
              ? 'الجهة المذكورة لا تبدو متطابقة مع نطاق الرابط.'
              : 'تم التعرف على الجهة المذكورة دون مؤشرات تعارض واضحة.');
    final statusColor = hasMismatch
        ? AppTokens.warning
        : (hasOfficialMatch ? AppTokens.success : AppTokens.neutral);

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'تحليل الجهة',
            subtitle: 'مطابقة الجهة المذكورة مع المرسل والرابط الرسمي.',
            icon: Icons.account_balance_rounded,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'الجهة المدّعاة',
                  value: claimed.isEmpty
                      ? 'لم يتم التعرف على جهة محددة'
                      : claimed,
                  icon: Icons.apartment_rounded,
                  color: hasMismatch ? AppTokens.warning : AppTokens.brandCyan,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'نوع الجهة',
                  value: entityType.isEmpty ? 'غير محدد' : entityType,
                  icon: Icons.category_rounded,
                  color: AppTokens.neutral,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'النطاق المكتشف',
                  value: domain.isEmpty ? 'غير متاح' : domain,
                  icon: Icons.language_rounded,
                  color: statusColor,
                  ltrValue: domain.isNotEmpty,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _contextMiniCard(
                  context,
                  title: 'حالة النطاق الرسمي',
                  value: statusText,
                  icon: hasOfficialMatch
                      ? Icons.verified_rounded
                      : Icons.report_problem_rounded,
                  color: statusColor,
                ),
              ),
            ],
          ),
          if (domainEntity.isNotEmpty) ...[
            const SizedBox(height: 10),
            _contextNotice(
              context,
              icon: Icons.link_rounded,
              color: AppTokens.brandCyan,
              text: 'الجهة المرتبطة بالرابط: $domainEntity',
            ),
          ],
          const SizedBox(height: 10),
          _contextNotice(
            context,
            icon: hasMismatch
                ? Icons.account_tree_rounded
                : Icons.check_circle_rounded,
            color: statusColor,
            text: '$conflictText — $note',
          ),
        ],
      ),
    );
  }

  Widget _contextMiniCard(
    BuildContext context, {
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    bool ltrValue = false,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 19),
          const SizedBox(height: 8),
          Text(
            value,
            textDirection: ltrValue ? TextDirection.ltr : null,
            textAlign: ltrValue ? TextAlign.left : TextAlign.start,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w900,
              height: 1.35,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            title,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }

  Widget _contextNotice(
    BuildContext context, {
    required IconData icon,
    required Color color,
    required String text,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              text,
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                height: 1.5,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Icon(icon, color: color, size: 19),
        ],
      ),
    );
  }

  List<(IconData, Color, String)> _recommendationSteps(BuildContext context) {
    final steps = <(IconData, Color, String)>[];
    if (_isHigh) {
      if (_hasUrl || _hasSuspiciousUrl) {
        steps.add((
          Icons.link_off_rounded,
          AppTokens.danger,
          'لا تفتح الرابط المرسل بأي حال.',
        ));
      }
      if (_hasCredentialOrOtpRisk) {
        steps.add((
          Icons.lock_rounded,
          AppTokens.danger,
          'لا تشارك أي رمز تحقق أو بيانات دخول.',
        ));
      }
      if (_hasBankingOrPaymentContext) {
        steps.add((
          Icons.account_balance_rounded,
          AppTokens.warning,
          'راجع العملية من تطبيق البنك الرسمي مباشرةً.',
        ));
      }
      steps.add((
        Icons.verified_user_rounded,
        AppTokens.brandCyan,
        'استخدم التطبيق أو الموقع الرسمي للتحقق.',
      ));
      steps.add((
        Icons.block_rounded,
        AppTokens.warning,
        'فكّر في حظر المرسل أو الإبلاغ عنه.',
      ));
    } else if (_isSafe) {
      steps.add((
        Icons.check_circle_rounded,
        AppTokens.success,
        'يمكنك المتابعة بهدوء.',
      ));
      steps.add((
        Icons.open_in_browser_rounded,
        AppTokens.brandCyan,
        'للإجراءات الحساسة، استخدم القناة الرسمية دائمًا.',
      ));
    } else {
      steps.add((
        Icons.pause_circle_rounded,
        AppTokens.warning,
        'لا تتخذ أي إجراء الآن قبل التحقق.',
      ));
      if (_hasUrl) {
        steps.add((
          Icons.search_rounded,
          AppTokens.brandCyan,
          'تحقق من النطاق أو افتح الموقع الرسمي يدويًا.',
        ));
      }
      if (_hasCredentialOrOtpRisk) {
        steps.add((
          Icons.lock_rounded,
          AppTokens.warning,
          'تأكد قبل مشاركة أي رمز أو بيانات.',
        ));
      }
      steps.add((
        Icons.shield_rounded,
        AppTokens.brandCyan,
        'تحقق عبر قناة رسمية قبل المتابعة.',
      ));
    }
    return steps;
  }

  Widget _actionStep(
    BuildContext context,
    int index,
    (IconData, Color, String) step,
  ) {
    return FadeSlideIn(
      delay: Duration(milliseconds: 50 + (index * 55)),
      beginOffset: const Offset(0, 5),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Text(
                step.$3,
                textAlign: TextAlign.right,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  height: 1.55,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: step.$2.withValues(alpha: 0.12),
                shape: BoxShape.circle,
                border: Border.all(color: step.$2.withValues(alpha: 0.22)),
              ),
              child: Icon(step.$1, color: step.$2, size: 16),
            ),
          ],
        ),
      ),
    );
  }

  Widget _recommendationCard(BuildContext context) {
    final steps = _recommendationSteps(context);
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      border: Border.all(color: _color.withValues(alpha: 0.22)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: context.l10n.finalRecommendation,
            icon: Icons.task_alt_rounded,
          ),
          const SizedBox(height: 14),
          ...steps.asMap().entries.map(
            (entry) => _actionStep(context, entry.key, entry.value),
          ),
        ],
      ),
    );
  }

  String _signalText(Map<String, dynamic> signal) {
    final parts = <String>[];

    void collect(dynamic value) {
      if (value == null) return;
      if (value is Map) {
        value.values.forEach(collect);
      } else if (value is Iterable) {
        value.forEach(collect);
      } else {
        parts.add(value.toString().toLowerCase());
      }
    }

    collect(signal);
    return parts.join(' ');
  }

  String _mainClassificationReason(BuildContext context) {
    final signals = item.result.matchedSignals.map(_signalText).toList();
    bool hasSignal(String value) => signals.any((s) => s.contains(value));
    bool hasAny(List<String> values) =>
        signals.any((s) => values.any((value) => s.contains(value)));

    if (hasSignal('behavioral_account_takeover_url')) {
      return 'تم اكتشاف نمط تصيد يستهدف الاستيلاء على الحساب.';
    }
    if (hasSignal('behavioral_payment_phishing')) {
      return 'تم اكتشاف نمط تصيد مرتبط بالدفع أو البطاقة.';
    }
    if (hasSignal('url_misleading_brand_in_url')) {
      return 'أقوى مؤشر مرتبط بموثوقية الرابط والنطاق.';
    }
    if (hasAny(['credential', 'otp', 'password', 'cvv'])) {
      return 'الرسالة تطلب بيانات حساسة أو رمز تحقق.';
    }
    if (hasSignal('suspicious_urgent_account')) {
      return 'الرسالة تستخدم استعجالاً أو تهديداً لدفعك لاتخاذ إجراء.';
    }
    if (hasAny(['safe_guardrail', 'security_advice'])) {
      return 'الرسالة تبدو توعوية وتركز على الحماية من مشاركة البيانات.';
    }
    if (item.result.reasons.isNotEmpty) {
      return TextMapper.reason(context, item.result.reasons.first);
    }
    return 'تم تقييم الرسالة بناءً على المؤشرات المتاحة في النص والمرسل والرابط.';
  }

  Widget _mainReasonCard(BuildContext context) => AppSurfaceCard(
    padding: const EdgeInsets.all(18),
    border: Border.all(color: _color.withValues(alpha: 0.24)),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: context.l10n.mainClassificationReason,
          icon: _isSafe ? Icons.verified_rounded : Icons.report_problem_rounded,
        ),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(13),
          decoration: BoxDecoration(
            color: _color.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _color.withValues(alpha: 0.20)),
          ),
          child: Text(
            _mainClassificationReason(context),
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTokens.textPrimary(context),
              height: 1.6,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'مستوى الثقة بالخطورة: $_riskConfidenceLabel',
          textAlign: TextAlign.right,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AppTokens.mutedText(context),
            height: 1.45,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    ),
  );

  List<String> _reasons(BuildContext context) {
    final base = item.result.reasons
        .map((e) => TextMapper.reason(context, e))
        .where((e) => e.trim().isNotEmpty)
        .toList();
    final senderWasProvided =
        item.sender.trim().isNotEmpty && !_looksLikePackageName(item.sender);
    if (!_isSafe && senderWasProvided && item.sourceTrust == 'unknown') {
      base.add('هوية المرسل تحتاج تحققًا إضافيًا');
    }
    if (item.selectedIndicators.contains('تطلب بيانات بنكية') ||
        item.selectedIndicators.contains('تطلب رمز تحقق OTP')) {
      base.add('الرسالة تطلب بيانات حساسة');
    }
    if (item.selectedIndicators.contains('تستخدم استعجال أو تهديد')) {
      base.add('وجود صياغة استعجالية');
    }
    if (!_isSafe && !_hasUrl && !_hasCredentialOrOtpRisk) {
      base.add('لم يتم العثور على رابط داخل الرسالة');
    }
    if (_hasEntityImpersonationCue) {
      base.add('الثقة بالجهة المذكورة تحتاج تحققًا إضافيًا');
    }
    return base.isEmpty
        ? ['تم تقييم الرسالة بناءً على النص والمرسل والرابط والمؤشرات المتاحة.']
        : base.toSet().toList();
  }

  String _compactReason(String reason) {
    final text = reason.toLowerCase();
    if (text.contains('url_misleading_brand_in_url') ||
        text.contains('brand') ||
        text.contains('نطاق الرابط لا يطابق') ||
        text.contains('لا يبدو تابع')) {
      return 'الرابط يستخدم اسم جهة معروفة لكنه لا يتبع نطاقها الرسمي.';
    }
    if (text.contains('suspicious_urgent_account') ||
        text.contains('suspension') ||
        text.contains('urgent') ||
        text.contains('استعجال') ||
        text.contains('تهديد')) {
      return 'الرسالة تستخدم تهديدًا أو استعجالًا لدفعك لاتخاذ إجراء.';
    }
    if (text.contains('credential') ||
        text.contains('otp') ||
        text.contains('password') ||
        text.contains('cvv') ||
        text.contains('رمز') ||
        text.contains('بيانات حساسة')) {
      return 'تطلب الرسالة مشاركة رمز أو بيانات حساسة.';
    }
    if (text.contains('safe_guardrail') ||
        text.contains('security_advice') ||
        text.contains('توعوية') ||
        text.contains('تحذر')) {
      return 'المحتوى توعوي ويركز على حماية البيانات.';
    }
    if (text.contains('الرابط غير موجود') || text.contains('no url')) {
      return 'لم يتم العثور على رابط داخل الرسالة.';
    }
    if (text.contains('هوية المرسل')) {
      return 'هوية المرسل تحتاج تحققًا إضافيًا.';
    }
    if (text.contains('الجهة المذكورة')) {
      return 'الثقة بالجهة المذكورة تحتاج تحققًا إضافيًا.';
    }
    return reason.replaceAll('.', '').trim();
  }

  List<String> _smartReasons(BuildContext context) {
    final reasons = <String>[..._reasons(context).map(_compactReason)];
    if (_hasSuspiciousEntityLink) {
      reasons.add('الرابط يستخدم اسم جهة معروفة لكنه لا يتبع نطاقها الرسمي.');
    }
    if (_hasCredentialOrOtpRisk) {
      reasons.add('تطلب الرسالة مشاركة رمز أو بيانات حساسة.');
    }
    if (_intelligenceText.contains('threat') ||
        _intelligenceText.contains('urgency') ||
        _intelligenceText.contains('تعليق') ||
        _intelligenceText.contains('إغلاق')) {
      reasons.add('الرسالة تستخدم تهديدًا أو استعجالًا لدفعك لاتخاذ إجراء.');
    }
    if (_isSafe &&
        (_intelligenceText.contains('security_advice') ||
            _intelligenceText.contains('safe_guardrail'))) {
      reasons.add('المحتوى توعوي ويركز على حماية البيانات.');
    }
    final seen = <String>{};
    return reasons
        .where((reason) => reason.trim().isNotEmpty)
        .where((reason) => seen.add(reason.trim()))
        .take(7)
        .toList();
  }

  List<_ReasonSection> _reasonSections(BuildContext context) {
    final grouped = <String, List<String>>{
      'الرابط': <String>[],
      'محتوى الرسالة': <String>[],
      'المرسل والجهة': <String>[],
      'مؤشرات إضافية': <String>[],
    };

    for (final reason in _smartReasons(context)) {
      final text = reason.toLowerCase();
      if (text.contains('رابط') ||
          text.contains('url') ||
          text.contains('نطاق') ||
          text.contains('domain')) {
        grouped['الرابط']!.add(reason);
      } else if (text.contains('مرسل') ||
          text.contains('جهة') ||
          text.contains('هوية') ||
          text.contains('sender') ||
          text.contains('entity')) {
        grouped['المرسل والجهة']!.add(reason);
      } else if (text.contains('رسالة') ||
          text.contains('النص') ||
          text.contains('محتوى') ||
          text.contains('بيانات') ||
          text.contains('رمز') ||
          text.contains('استعجال') ||
          text.contains('تهديد') ||
          text.contains('text') ||
          text.contains('credential') ||
          text.contains('otp')) {
        grouped['محتوى الرسالة']!.add(reason);
      } else {
        grouped['مؤشرات إضافية']!.add(reason);
      }
    }

    return grouped.entries
        .where((entry) => entry.value.isNotEmpty)
        .map((entry) => _ReasonSection(entry.key, entry.value))
        .toList();
  }

  Widget _reasonsCard(BuildContext context) => AppSurfaceCard(
    padding: const EdgeInsets.all(18),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: context.l10n.reasons,
          icon: Icons.rule_folder_rounded,
        ),
        const SizedBox(height: 12),
        ..._reasonSections(context).asMap().entries.map(
          (entry) => StaggeredItem(
            index: entry.key,
            child: Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context).withValues(alpha: 0.58),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: AppTokens.outline(context).withValues(alpha: 0.60),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      entry.value.title,
                      textAlign: TextAlign.right,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: _color,
                        height: 1.35,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 8),
                    ...entry.value.items.map(
                      (reason) => Padding(
                        padding: const EdgeInsets.only(bottom: 7),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              Icons.check_circle_rounded,
                              color: _color,
                              size: 18,
                            ),
                            const SizedBox(width: 9),
                            Expanded(
                              child: Text(
                                reason,
                                textAlign: TextAlign.right,
                                style: Theme.of(context).textTheme.bodyMedium
                                    ?.copyWith(
                                      height: 1.5,
                                      fontWeight: FontWeight.w700,
                                    ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );

  List<(String, IconData, Color, List<String>)> _evidenceGroups(
    BuildContext context,
  ) {
    final urlItems = <String>[];
    final contentItems = <String>[];
    final behaviorItems = <String>[];
    final sandboxItems = <String>[];
    final senderItems = <String>[];

    void add(List<String> target, String value) {
      final text = value.trim();
      if (text.isNotEmpty && !target.contains(text)) target.add(text);
    }

    for (final reason in _smartReasons(context)) {
      final text = reason.toLowerCase();
      if (text.contains('رابط') ||
          text.contains('url') ||
          text.contains('نطاق') ||
          text.contains('domain')) {
        add(urlItems, reason);
      } else if (text.contains('مرسل') ||
          text.contains('جهة') ||
          text.contains('هوية') ||
          text.contains('sender') ||
          text.contains('entity')) {
        add(senderItems, reason);
      } else if (text.contains('استعجال') ||
          text.contains('تهديد') ||
          text.contains('urgent') ||
          text.contains('threat')) {
        add(behaviorItems, reason);
      } else {
        add(contentItems, reason);
      }
    }

    if (_hasUrl) {
      add(
        urlItems,
        _hasSuspiciousUrl
            ? 'الرابط يحتاج تحققاً إضافياً قبل فتحه.'
            : 'تم العثور على رابط وتم إدخاله ضمن التحقيق.',
      );
    }
    if (_hasCredentialOrOtpRisk) {
      add(contentItems, 'ظهرت مؤشرات مرتبطة بطلب رمز تحقق أو بيانات حساسة.');
    }
    if (_hasBankingOrPaymentContext) {
      add(
        contentItems,
        'السياق مرتبط بدفع أو حساب مالي، لذلك يحتاج حذراً أعلى.',
      );
    }
    if (_intelligenceText.contains('delayed') ||
        _intelligenceText.contains('redirect')) {
      add(
        behaviorItems,
        'يوجد سلوك يحتاج مراجعة مثل إعادة توجيه أو تغير بعد التحميل.',
      );
    }
    if (item.result.entityConflict || _hasEntityImpersonationCue) {
      add(senderItems, 'الجهة أو المرسل لا يبدوان متسقين بالكامل مع الرابط.');
    } else if (_displaySender(context) != context.l10n.unknownLabel) {
      add(senderItems, 'تم إدخال المرسل ضمن سياق التحقيق.');
    }
    if (_hasDynamicSignals) {
      for (final signal in _dynamicSignals.take(3)) {
        add(
          sandboxItems,
          _dynSignalArabicLabel(signal['id']?.toString() ?? ''),
        );
      }
    }

    final groups = <(String, IconData, Color, List<String>)>[];
    if (urlItems.isNotEmpty) {
      groups.add(('رابط / URL', Icons.link_rounded, _urlStatusColor, urlItems));
    }
    if (contentItems.isNotEmpty) {
      groups.add((
        'محتوى الرسالة',
        Icons.article_rounded,
        _hasCredentialOrOtpRisk ? AppTokens.warning : _color,
        contentItems,
      ));
    }
    if (behaviorItems.isNotEmpty) {
      groups.add((
        'السلوك / Behavioral',
        Icons.route_rounded,
        AppTokens.warning,
        behaviorItems,
      ));
    }
    if (sandboxItems.isNotEmpty) {
      groups.add((
        'صندوق العزل الديناميكي',
        Icons.biotech_rounded,
        AppTokens.brandCyan,
        sandboxItems,
      ));
    }
    if (senderItems.isNotEmpty) {
      groups.add((
        'الجهة / Sender',
        Icons.person_search_rounded,
        item.result.entityConflict ? AppTokens.warning : AppTokens.brandCyan,
        senderItems,
      ));
    }
    return groups;
  }

  Widget _evidenceGroupsCard(BuildContext context) {
    final groups = _evidenceGroups(context);
    if (groups.isEmpty) return _reasonsCard(context);

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionHeader(
            title: 'الأدلة المكتشفة',
            subtitle: 'أهم المؤشرات مرتبة كقصة تحقيق قابلة للقراءة.',
            icon: Icons.rule_folder_rounded,
          ),
          const SizedBox(height: 14),
          ...groups.asMap().entries.map((entry) {
            final group = entry.value;
            return StaggeredItem(
              index: entry.key,
              step: const Duration(milliseconds: 55),
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _evidenceGroupTile(
                  context,
                  title: group.$1,
                  icon: group.$2,
                  color: group.$3,
                  items: group.$4.take(3).toList(),
                ),
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _evidenceGroupTile(
    BuildContext context, {
    required String title,
    required IconData icon,
    required Color color,
    required List<String> items,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Icon(icon, color: color, size: 20),
            ],
          ),
          const SizedBox(height: 10),
          ...items.map(
            (evidence) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      evidence,
                      textAlign: TextAlign.right,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        height: 1.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 9),
                  Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.only(top: 8),
                    decoration: BoxDecoration(
                      color: color,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _sourceCard(BuildContext context) => AppSurfaceCard(
    padding: const EdgeInsets.all(18),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: SectionHeader(
                title: context.l10n.originalMessage,
                icon: Icons.message_rounded,
              ),
            ),
            TextButton.icon(
              onPressed: () => _copyMessage(context),
              icon: const Icon(Icons.copy_rounded, size: 18),
              label: Text(context.l10n.copyMessageText),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          _isUrlOnly
              ? 'محتوى الرسالة: غير قابل للتقييم'
              : item.rawText.trim().isEmpty
              ? 'لا يوجد نص متاح.'
              : item.rawText.trim(),
          textAlign: TextAlign.right,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.6),
        ),
        if (item.notes.trim().isNotEmpty) ...[
          const SizedBox(height: 12),
          Text(
            'ملاحظات: ${item.notes}',
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.5,
            ),
          ),
        ],
      ],
    ),
  );

  Widget _linkCard(BuildContext context) {
    final linkCopy = _linkIntelligenceCopy;
    final chips = _urlSignalChips;
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: SectionHeader(
                  title: context.l10n.detectedLink,
                  icon: Icons.link_rounded,
                ),
              ),
              if (_hasUrl) ...[
                const SizedBox(width: 8),
                _urlStatusBadge(context),
              ],
            ],
          ),
          if (_hasUrl) ...[
            const SizedBox(height: 12),
            // URL display
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppTokens.surfaceAlt(context).withValues(alpha: 0.70),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color:
                      (_hasSuspiciousUrl
                              ? _urlStatusColor
                              : AppTokens.outline(context))
                          .withValues(alpha: _hasSuspiciousUrl ? 0.35 : 0.65),
                ),
              ),
              child: Text(
                _displayUrl,
                textDirection: TextDirection.ltr,
                textAlign: TextAlign.left,
                style: const TextStyle(
                  color: AppTokens.brandCyan,
                  fontWeight: FontWeight.w800,
                  height: 1.45,
                ),
              ),
            ),
            // Intelligence signal chips — warnings first
            if (chips.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: chips
                    .map(
                      (chip) => Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 9,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          color: chip.color.withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(
                            color: chip.color.withValues(alpha: 0.25),
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(chip.icon, size: 13, color: chip.color),
                            const SizedBox(width: 5),
                            Text(
                              chip.label,
                              style: TextStyle(
                                color: chip.color,
                                fontWeight: FontWeight.w900,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                    .toList(),
              ),
            ],
            const SizedBox(height: 12),
            // Domain analysis — trust hierarchy
            _domainCheck(context),
            // URL structure explainability blocks
            ..._urlStructureBlocks(context),
            const SizedBox(height: 10),
            // Secondary summary — less prominent
            Text(
              linkCopy,
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.mutedText(context),
                height: 1.55,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () => _copyUrl(context),
              icon: const Icon(Icons.copy_rounded),
              label: Text(context.l10n.copyLink),
            ),
          ] else
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(
                linkCopy,
                textAlign: TextAlign.right,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppTokens.mutedText(context),
                  height: 1.55,
                ),
              ),
            ),
        ],
      ),
    );
  }

  String get _urlStatusLabel {
    if (!_hasUrl) {
      return '';
    }
    if (_hasSuspiciousUrl) {
      return _isHigh ? 'خطر' : 'يحتاج تحقق';
    }
    return 'موثوق';
  }

  Color get _urlStatusColor {
    if (!_hasUrl) return AppTokens.neutral;
    if (_hasSuspiciousUrl) {
      return _isHigh ? AppTokens.danger : AppTokens.warning;
    }
    return AppTokens.success;
  }

  Widget _urlStatusBadge(BuildContext context) {
    final color = _urlStatusColor;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.30)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _hasSuspiciousUrl
                ? Icons.warning_amber_rounded
                : Icons.verified_rounded,
            size: 16,
            color: color,
          ),
          const SizedBox(width: 6),
          Text(
            _urlStatusLabel,
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w900,
              height: 1.2,
            ),
          ),
        ],
      ),
    );
  }

  Widget _domainCheck(BuildContext context) {
    final domain = _detectedDomain;
    final entity = _displayEntityBase;
    final showEntity = entity != 'غير محددة';
    final hasConflict = _hasEntityImpersonationCue || _hasSuspiciousEntityLink;
    final isSafeOfficial = !_hasSuspiciousUrl && _isSafe;

    final Color borderColor;
    final Color bgColor;
    if (hasConflict) {
      borderColor = AppTokens.warning.withValues(alpha: 0.32);
      bgColor = AppTokens.warning.withValues(alpha: 0.06);
    } else if (isSafeOfficial) {
      borderColor = AppTokens.success.withValues(alpha: 0.28);
      bgColor = AppTokens.success.withValues(alpha: 0.05);
    } else {
      borderColor = AppTokens.outline(context).withValues(alpha: 0.60);
      bgColor = AppTokens.surfaceAlt(context).withValues(alpha: 0.52);
    }

    final String trustLabel;
    final Color trustColor;
    if (hasConflict) {
      trustLabel = 'مريب';
      trustColor = AppTokens.warning;
    } else if (isSafeOfficial) {
      trustLabel = 'رسمي';
      trustColor = AppTokens.success;
    } else if (_hasSuspiciousUrl) {
      trustLabel = 'يحتاج تحقق';
      trustColor = AppTokens.warning;
    } else {
      trustLabel = 'غير محدد';
      trustColor = AppTokens.neutral;
    }

    final String trustDescription;
    if (hasConflict) {
      trustDescription = 'الرابط لا يبدو تابعًا للجهة المذكورة';
    } else if (_hasUrlShortener) {
      trustDescription = 'الرابط يستخدم خدمة اختصار';
    } else if (isSafeOfficial) {
      trustDescription = 'النطاق يبدو رسميًا';
    } else if (_hasSuspiciousUrl) {
      trustDescription = 'النطاق يحتاج تحققًا إضافيًا';
    } else {
      trustDescription = 'لم يتم اكتشاف مؤشرات انتحال واضحة';
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'تحليل النطاق',
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                    height: 1.35,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                decoration: BoxDecoration(
                  color: trustColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: trustColor.withValues(alpha: 0.22)),
                ),
                child: Text(
                  trustLabel,
                  style: TextStyle(
                    color: trustColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _domainCheckRow(
            context,
            label: 'النطاق المكتشف',
            value: domain.isEmpty ? 'تعذر التحقق' : domain,
            ltrValue: domain.isNotEmpty,
          ),
          if (showEntity) ...[
            const SizedBox(height: 6),
            _domainCheckRow(context, label: 'الجهة المذكورة', value: entity),
          ],
          const SizedBox(height: 6),
          _domainCheckRow(
            context,
            label: 'علاقة الثقة',
            value: trustDescription,
          ),
          if (hasConflict ||
              _hasUrlShortener ||
              _hasSuspiciousUrl ||
              isSafeOfficial) ...[
            const SizedBox(height: 10),
            _domainTrustRow(
              context,
              hasConflict: hasConflict,
              isSafeOfficial: isSafeOfficial,
            ),
          ],
        ],
      ),
    );
  }

  Widget _domainCheckRow(
    BuildContext context, {
    required String label,
    required String value,
    bool ltrValue = false,
  }) {
    final valueColor = ltrValue
        ? AppTokens.brandCyan
        : AppTokens.mutedText(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Text(
            value,
            textDirection: ltrValue ? TextDirection.ltr : TextDirection.rtl,
            textAlign: ltrValue ? TextAlign.left : TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: valueColor,
              height: 1.45,
              fontWeight: ltrValue ? FontWeight.w900 : FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          label,
          textAlign: TextAlign.right,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            height: 1.45,
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }

  Widget _domainTrustRow(
    BuildContext context, {
    required bool hasConflict,
    required bool isSafeOfficial,
  }) {
    final Color color;
    final IconData icon;
    final String message;

    if (hasConflict) {
      color = AppTokens.warning;
      icon = Icons.link_off_rounded;
      message = 'الرابط لا يبدو تابعًا للجهة المذكورة';
    } else if (_hasUrlShortener) {
      color = AppTokens.warning;
      icon = Icons.link_rounded;
      message = 'الرابط يستخدم خدمة اختصار';
    } else if (isSafeOfficial) {
      color = AppTokens.success;
      icon = Icons.check_circle_rounded;
      message = 'النطاق يبدو رسميًا';
    } else {
      color = AppTokens.neutral;
      icon = Icons.info_outline_rounded;
      message = 'النطاق يحتاج تحققًا إضافيًا';
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              message,
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w800,
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Icon(icon, color: color, size: 16),
        ],
      ),
    );
  }

  List<Widget> _urlStructureBlocks(BuildContext context) {
    final blocks = <Widget>[];
    final url = _displayUrl.toLowerCase();

    final keywords = <String>[];
    for (final kw in [
      'login',
      'verify',
      'update',
      'secure',
      'pay',
      'confirm',
      'account',
      'password',
    ]) {
      if (url.contains(kw)) keywords.add(kw);
    }
    if (_hasClearImpersonationSignal || item.result.entityConflict) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.person_off_rounded,
          color: AppTokens.danger,
          title: 'انتحال جهة معروفة',
          desc: 'يستخدم الرابط اسم جهة رسمية لكنه لا يتبع نطاقها الحقيقي.',
        ),
      );
    }

    if (_hasUrlShortener) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.link_rounded,
          color: AppTokens.warning,
          title: 'خدمة اختصار روابط',
          desc: 'الرابط يستخدم خدمة اختصار مما يصعّب التحقق من وجهته الحقيقية.',
        ),
      );
    }

    if (_hasSuspiciousTld) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.warning_amber_rounded,
          color: AppTokens.danger,
          title: 'امتداد نطاق مريب',
          desc: 'امتداد النطاق المستخدم غير شائع أو مرتبط بنشاط مشبوه.',
        ),
      );
    }

    if (keywords.isNotEmpty) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.key_rounded,
          color: AppTokens.warning,
          title: 'كلمات مفتاحية في الرابط',
          desc: 'يحتوي الرابط على كلمات حساسة: ${keywords.join(' · ')}',
        ),
      );
    }

    if (_hasComplexUrlStructure) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.account_tree_rounded,
          color: _hasSuspiciousUrl ? AppTokens.warning : AppTokens.brandCyan,
          title: 'بنية الرابط',
          desc: _hasSuspiciousUrl
              ? 'يحتوي الرابط على مسارات أو معاملات تحتاج مراجعة قبل فتحه.'
              : 'بنية الرابط لا تظهر وحدها مؤشر انتحال واضح.',
        ),
      );
    }

    if (!_hasSuspiciousUrl && _isSafe && _hasUrl) {
      blocks.add(
        _structureBlock(
          context,
          icon: Icons.verified_rounded,
          color: AppTokens.success,
          title: 'لم يتم اكتشاف مؤشرات انتحال واضحة',
          desc: 'النطاق يبدو رسميًا ولم تُرصد إشارات مشبوهة في بنية الرابط.',
        ),
      );
    }

    if (blocks.isEmpty) return [];
    return [
      const SizedBox(height: 8),
      ...blocks.map(
        (block) =>
            Padding(padding: const EdgeInsets.only(bottom: 7), child: block),
      ),
    ];
  }

  Widget _structureBlock(
    BuildContext context, {
    required IconData icon,
    required Color color,
    required String title,
    required String desc,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  title,
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  desc,
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTokens.mutedText(context),
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(icon, color: color, size: 17),
          ),
        ],
      ),
    );
  }

  String get _linkIntelligenceCopy {
    if (!_hasUrl) return 'لم يتم العثور على رابط داخل الرسالة.';
    if (_hasSuspiciousEntityLink || _hasClearImpersonationSignal) {
      return 'اسم الجهة داخل الرابط لا يكفي لإثبات موثوقية النطاق.';
    }
    final urlLayers = item.result.layers
        .where((layer) => layer.keyName.toLowerCase() == 'url')
        .toList();
    if (urlLayers.isEmpty || urlLayers.any((layer) => layer.score <= 0)) {
      return 'تم العثور على رابط، وتحتاج موثوقيته إلى تحقق إضافي.';
    }
    return 'تم العثور على رابط وتم فحصه ضمن التحليل.';
  }

  Widget _analysisInfoCard(BuildContext context) => AppSurfaceCard(
    padding: const EdgeInsets.all(18),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: context.l10n.analysisInfo,
          icon: Icons.info_rounded,
        ),
        const SizedBox(height: 12),
        _infoLine(
          context,
          'التاريخ',
          TextMapper.formatDateTime(context, item.createdAt),
        ),
        _infoLine(
          context,
          'نوع الرسالة',
          TextMapper.channel(context, _displayChannel),
        ),
        _infoLine(context, 'المصدر', _displaySender(context)),
        _infoLine(
          context,
          'طريقة التحليل',
          _isNotificationChannel
              ? 'تلقائي من مراقبة الإشعارات'
              : 'يدوي من شاشة التحليل',
        ),
        _infoLine(
          context,
          'جاءت من مراقبة الإشعارات',
          _isNotificationChannel ? 'نعم' : 'لا',
        ),
        _infoLine(context, 'الحفظ في السجل', 'أضيفت النتيجة إلى السجل'),
      ],
    ),
  );

  Widget _infoLine(BuildContext context, String label, String value) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 4,
          child: Text(
            label,
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.45,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          flex: 5,
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              height: 1.45,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ],
    ),
  );

  Widget _actionsBar(BuildContext context) => Wrap(
    spacing: 9,
    runSpacing: 9,
    children: [
      OutlinedButton.icon(
        onPressed: () => _copyDetails(context),
        icon: const Icon(Icons.copy_rounded),
        label: Text(context.l10n.copy),
      ),
      OutlinedButton.icon(
        onPressed: () => _shareDetails(context),
        icon: const Icon(Icons.share_rounded),
        label: Text(context.l10n.share),
      ),
      if (onDelete != null)
        FilledButton.tonalIcon(
          onPressed: () => _deleteItem(context),
          icon: const Icon(Icons.delete_outline_rounded),
          label: Text(context.l10n.deleteFromHistory),
        ),
    ],
  );

  String _intentLabel(String? intent) {
    switch (intent) {
      case 'otp_code':
        return 'رمز تحقق';
      case 'advertisement':
        return 'إعلان';
      case 'transactional':
        return 'معاملة';
      case 'service_notice':
        return 'إشعار خدمة';
      case 'security_advice':
        return 'توعية أمنية';
      case 'survey_feedback':
        return 'استطلاع / تقييم';
      case 'payment_notice':
        return 'إشعار دفع';
      case 'credential_phishing':
        return 'تصيد بيانات';
      case 'financial_phishing':
        return 'تصيد مالي';
      case 'suspicious_link':
        return 'رابط غير موثوق';
      case 'normal':
        return 'عادية';
      case 'unknown':
        return 'غير محدد';
      default:
        return 'غير محدد';
    }
  }

  List<String> _messageTypeLabels() {
    final intent = item.result.messageIntent?.trim().toLowerCase() ?? '';
    final signalText = item.result.matchedSignals.map(_signalText).join(' ');
    final reasonsText = item.result.reasons.join(' ');
    final haystack =
        '$intent $signalText $reasonsText ${item.rawText} ${item.url}'
            .toLowerCase();
    final labels = <String>[];

    bool hasAny(List<String> values) =>
        values.any((value) => haystack.contains(value));

    void add(String label) {
      if (!labels.contains(label)) labels.add(label);
    }

    if (_hasSuspiciousUrl || _hasSuspiciousEntityLink) add('رابط تصيد');
    if (intent == 'otp_code' || hasAny(['otp', 'verification code', 'رمز'])) {
      add('OTP');
    }
    if (hasAny(['account_update', 'update', 'verify', 'confirm', 'تحديث'])) {
      add('تحديث حساب');
    }
    if (hasAny(['payment', 'invoice', 'bill', 'فاتورة', 'دفع'])) {
      add('دفع/فاتورة');
    }
    if (intent == 'financial_phishing' ||
        hasAny(['bank_account_takeover', 'banking', 'bank', 'iban', 'بنك'])) {
      add('بنك');
    }
    if (hasAny(['delivery', 'shipping', 'parcel', 'توصيل', 'شحنة'])) {
      add('توصيل');
    }
    if (intent == 'advertisement' || hasAny(['advertisement', 'إعلان'])) {
      add('إعلان');
    }
    if (hasAny(['credential', 'password', 'cvv', 'card_data'])) {
      add('تصيد');
    }
    if (labels.isEmpty && _hasUrl) add('رابط');
    if (labels.isEmpty) add(_intentLabel(item.result.messageIntent));
    if (labels.first == 'غير محدد') return ['تعذر التحقق'];
    return labels.take(4).toList();
  }

  Widget _messageIntentCard(BuildContext context) {
    final labels = _messageTypeLabels();
    final label = labels.first;
    final secondary = labels.skip(1).toList();
    final confidenceText = _confidenceText(item.result.intentConfidence);
    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: context.l10n.messageType,
            icon: Icons.category_rounded,
          ),
          const SizedBox(height: 10),
          Text(
            label,
            textAlign: TextAlign.right,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.w900,
              height: 1.35,
            ),
          ),
          if (confidenceText.isNotEmpty) ...[
            const SizedBox(height: 8),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: StatusBadge(
                label: confidenceText,
                color: _color,
                icon: Icons.insights_rounded,
              ),
            ),
          ],
          if (secondary.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: secondary
                  .map(
                    (label) => StatusBadge(
                      label: label,
                      color: AppTokens.brandCyan,
                      icon: Icons.sell_rounded,
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget? _virusTotalCard(BuildContext context) {
    final signals = item.result.matchedSignals;
    Map<String, dynamic>? vtSignal;
    for (final s in signals) {
      if (s['provider']?.toString().toLowerCase() == 'virustotal') {
        vtSignal = s;
        break;
      }
    }
    if (vtSignal == null) return null;

    int readSigInt(dynamic v) {
      if (v is int) return v;
      if (v is num) return v.toInt();
      return int.tryParse('$v') ?? 0;
    }

    final malicious = readSigInt(vtSignal['malicious_count']);
    final suspicious = readSigInt(vtSignal['suspicious_count']);

    final Color vtColor;
    final String vtMessage;
    if (malicious > 0) {
      vtColor = AppTokens.danger;
      vtMessage = 'تم رصد الرابط كخطر بواسطة $malicious محركات أمنية';
    } else if (suspicious > 0) {
      vtColor = AppTokens.warning;
      vtMessage = 'تم رصد الرابط كمشبوه بواسطة $suspicious محركات أمنية';
    } else {
      vtColor = AppTokens.success;
      vtMessage = 'لم تظهر مؤشرات خطورة في VirusTotal';
    }

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      border: Border.all(color: vtColor.withValues(alpha: 0.28)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: context.l10n.virusTotalScan,
            icon: Icons.security_rounded,
          ),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: vtColor.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: vtColor.withValues(alpha: 0.22)),
            ),
            child: Text(
              vtMessage,
              textAlign: TextAlign.right,
              style: TextStyle(color: vtColor, fontWeight: FontWeight.w800),
            ),
          ),
          if (malicious > 0 || suspicious > 0) ...[
            const SizedBox(height: 8),
            Text(
              'خطر: $malicious  |  مشبوه: $suspicious',
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.mutedText(context),
                height: 1.45,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }

  List<Map<String, dynamic>> get _dynamicSignals => item.result.matchedSignals
      .where((s) => (s['id']?.toString() ?? '').startsWith('dyn_'))
      .toList();

  bool get _hasDynamicSignals => _dynamicSignals.isNotEmpty;

  String _dynSignalArabicLabel(String id) {
    switch (id) {
      case 'dyn_password_field_detected':
        return 'رُصد حقل إدخال كلمة المرور في الصفحة';
      case 'dyn_login_form_detected':
        return 'رُصد نموذج تسجيل دخول في الصفحة';
      case 'dyn_otp_field_detected':
        return 'رُصد حقل إدخال رمز التحقق (OTP) في الصفحة';
      case 'dyn_redirect_chain_observed':
        return 'رُصدت سلسلة إعادة توجيه قبل الوصول للصفحة النهائية';
      case 'dyn_final_domain_changed':
        return 'وجهة الرابط النهائية تختلف عن العنوان الظاهر في البداية';
      case 'dyn_suspicious_external_requests':
        return 'الصفحة تُرسل طلبات لجهات خارجية غير معتادة';
      case 'dyn_multi_signal_phishing_surface':
        return 'تجمّع أكثر من مؤشر تصيد في نفس الصفحة';
      case 'dyn_delayed_redirect_detected':
        return 'رُصد إعادة توجيه مؤجّلة تحدث بعد تحميل الصفحة';
      case 'dyn_sensitive_form_appeared_after_delay':
        return 'ظهر نموذج حساس بعد تأخير في تحميل الصفحة';
      case 'dyn_title_changed_after_load':
        return 'عنوان الصفحة تغيّر بعد اكتمال التحميل';
      case 'dyn_multi_stage_navigation':
        return 'رُصد تنقل متعدد المراحل يُشير لصفحة تصيد متطورة';
      default:
        return id.replaceAll('dyn_', '').replaceAll('_', ' ');
    }
  }

  IconData _dynSignalIcon(String id) {
    if (id.contains('password') || id.contains('login') || id.contains('otp')) {
      return Icons.lock_outline_rounded;
    }
    if (id.contains('redirect') ||
        id.contains('domain') ||
        id.contains('navigation')) {
      return Icons.swap_horiz_rounded;
    }
    if (id.contains('external') || id.contains('request')) {
      return Icons.cloud_off_rounded;
    }
    if (id.contains('delayed') || id.contains('after')) {
      return Icons.timer_outlined;
    }
    return Icons.find_in_page_rounded;
  }

  Widget _dynamicSandboxSection(BuildContext context) {
    final signals = const <Map<String, dynamic>>[];
    final timelineSteps = _dynamicTimelineSteps();
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      border: Border.all(color: AppTokens.brandCyan.withValues(alpha: 0.30)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.biotech_rounded,
                color: AppTokens.brandCyan,
                size: 20,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'تحليل الرابط الديناميكي',
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                    color: AppTokens.brandCyan,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'تم فتح الرابط في بيئة آمنة ومعزولة لمراقبة سلوكه الفعلي.',
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.5,
            ),
          ),
          const SizedBox(height: 14),
          ...timelineSteps.asMap().entries.map(
            (entry) => StaggeredItem(
              index: entry.key,
              step: const Duration(milliseconds: 70),
              child: _sandboxTimelineStep(
                context,
                text: entry.value.$1,
                icon: entry.value.$2,
                color: entry.value.$3,
                isLast: entry.key == timelineSteps.length - 1,
              ),
            ),
          ),
          if (signals.isNotEmpty) const SizedBox(height: 8),
          ...signals.asMap().entries.map((entry) {
            final id = entry.value['id']?.toString() ?? '';
            final label = _dynSignalArabicLabel(id);
            final icon = _dynSignalIcon(id);
            final isHighSeverity =
                entry.value['severity']?.toString() == 'high' ||
                id.contains('password') ||
                id.contains('otp') ||
                id.contains('final_domain') ||
                id.contains('multi_signal');
            final color = isHighSeverity ? AppTokens.danger : AppTokens.warning;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.07),
                  borderRadius: BorderRadius.circular(13),
                  border: Border.all(color: color.withValues(alpha: 0.22)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        label,
                        textAlign: TextAlign.right,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          height: 1.45,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Icon(icon, color: color, size: 16),
                    ),
                  ],
                ),
              ),
            );
          }),
          const SizedBox(height: 4),
          Text(
            'هذه المؤشرات استشارية ومبنية على سلوك الصفحة لحظة التحليل.',
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.5,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  List<(String, IconData, Color)> _dynamicTimelineSteps() {
    final ids = _dynamicSignals
        .map((signal) => signal['id']?.toString() ?? '')
        .where((id) => id.trim().isNotEmpty)
        .toList();
    bool has(String value) => ids.any((id) => id.contains(value));
    bool hasAny(List<String> values) =>
        ids.any((id) => values.any((value) => id.contains(value)));

    final steps = <(String, IconData, Color)>[
      (
        'تم فتح الرابط في بيئة آمنة ومعزولة.',
        Icons.shield_rounded,
        AppTokens.brandCyan,
      ),
    ];
    if (hasAny(['redirect', 'domain', 'navigation'])) {
      steps.add((
        'تم فحص إعادة التوجيه والوجهة النهائية للرابط.',
        Icons.swap_horiz_rounded,
        AppTokens.warning,
      ));
    }
    if (has('login')) {
      steps.add((
        'تم فحص وجود نماذج تسجيل الدخول.',
        Icons.login_rounded,
        AppTokens.warning,
      ));
    }
    if (hasAny(['password', 'otp'])) {
      steps.add((
        'تم رصد حقول قد تطلب كلمة مرور أو رمز OTP.',
        Icons.lock_rounded,
        AppTokens.danger,
      ));
    }
    if (hasAny(['external', 'request'])) {
      steps.add((
        'تم رصد الطلبات الخارجية التي ترسلها الصفحة.',
        Icons.cloud_sync_rounded,
        AppTokens.warning,
      ));
    }
    if (hasAny(['delayed', 'after', 'title_changed'])) {
      steps.add((
        'تم فحص السلوك المؤجل بعد تحميل الصفحة.',
        Icons.timer_outlined,
        AppTokens.warning,
      ));
    }
    if (has('multi_signal')) {
      steps.add((
        'اجتمعت عدة مؤشرات تصيد داخل الصفحة نفسها.',
        Icons.warning_amber_rounded,
        AppTokens.danger,
      ));
    }
    if (steps.length == 1) {
      steps.addAll(
        ids
            .take(3)
            .map(
              (id) => (
                _dynSignalArabicLabel(id),
                _dynSignalIcon(id),
                AppTokens.warning,
              ),
            ),
      );
    }
    return steps;
  }

  Widget _sandboxTimelineStep(
    BuildContext context, {
    required String text,
    required IconData icon,
    required Color color,
    required bool isLast,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.07),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: color.withValues(alpha: 0.20)),
            ),
            child: Text(
              text,
              textAlign: TextAlign.right,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                height: 1.5,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Column(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                shape: BoxShape.circle,
                border: Border.all(color: color.withValues(alpha: 0.24)),
              ),
              child: Icon(icon, color: color, size: 17),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 24,
                color: color.withValues(alpha: 0.22),
              ),
          ],
        ),
      ],
    );
  }

  Widget _feedbackInline(BuildContext context) {
    final l10n = context.l10n;
    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  l10n.feedbackQuestion,
                  textAlign: TextAlign.right,
                  style: Theme.of(
                    context,
                  ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 4),
                Text(
                  l10n.feedbackSubtitle,
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTokens.mutedText(context),
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          OutlinedButton(
            onPressed: () => FeedbackReportSheet.show(context, item),
            child: Text(l10n.sendFeedback),
          ),
        ],
      ),
    );
  }

  Widget _technicalMethodologyCard(BuildContext context) {
    final vtCard = _virusTotalCard(context);
    return AppSurfaceCard(
      padding: EdgeInsets.zero,
      child: ExpansionTile(
        initiallyExpanded: false,
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        leading: const Icon(
          Icons.account_tree_rounded,
          color: AppTokens.brandCyan,
        ),
        title: const Text(
          'منهجية التقييم',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        subtitle: const Text(
          'يوضح هذا القسم كيف جمع APG المؤشرات لتكوين النتيجة.',
        ),
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(
              Icons.account_tree_rounded,
              color: AppTokens.brandCyan,
            ),
            title: Text(
              'طبقات التقييم',
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
            subtitle: const Text(
              'تفصيل مساهمة النص والرابط والمرسل والجهة في النتيجة.',
            ),
            trailing: const Icon(Icons.arrow_back_ios_new_rounded, size: 18),
            onTap: () => Navigator.of(
              context,
            ).push(apgSlideFadeRoute(EvaluationDetailsScreen(item: item))),
          ),
          const SizedBox(height: 12),
          _messageIntentCard(context),
          const SizedBox(height: 12),
          _messageInfo(context),
          const SizedBox(height: 12),
          _linkCard(context),
          if (vtCard != null) ...[const SizedBox(height: 12), vtCard],
          const SizedBox(height: 12),
          _sourceCard(context),
          const SizedBox(height: 12),
          _analysisInfoCard(context),
        ],
      ),
    );
  }

  // ignore: unused_element
  Widget _storyHero(BuildContext context) {
    final confidence = _heroConfidencePercent();
    return AppSurfaceCard(
      padding: const EdgeInsets.all(22),
      gradient: LinearGradient(
        colors: [
          AppTokens.surface(context).withValues(alpha: 0.94),
          _color.withValues(alpha: 0.06),
        ],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
      border: Border.all(color: _color.withValues(alpha: 0.24)),
      child: Column(
        children: [
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusBadge(
                label: TextMapper.label(context, item.result.finalLabel),
                color: _color,
                icon: _icon,
              ),
              if (confidence != null)
                StatusBadge(
                  label: 'الثقة $confidence%',
                  color: AppTokens.brandCyan,
                  icon: Icons.insights_rounded,
                ),
            ],
          ),
          const SizedBox(height: 16),
          ProtectionPulseRing(
            color: _color,
            size: 148,
            maxAlpha: _isHigh ? 0.16 : 0.10,
            maxExpand: 22,
            child: CircularScoreMeter(
              score: item.result.finalScore,
              color: _color,
              size: 148,
              caption: '/100',
            ),
          ),
          const SizedBox(height: 18),
          Text(
            _title(context),
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _humanVerdictSentence,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.55,
              fontWeight: FontWeight.w400,
            ),
          ),
          if (sourceTag != null) ...[
            const SizedBox(height: 12),
            _softInfoPill(
              context,
              icon: Icons.qr_code_rounded,
              text: 'تم استخراج المحتوى من رمز QR ثم تحليله.',
              color: AppTokens.brandCyan,
            ),
          ],
        ],
      ),
    );
  }

  String get _humanVerdictSentence {
    if (_isHigh) {
      return 'APG وجد مؤشرات قوية تجعل الرسالة خطيرة، لذلك يفضل عدم التفاعل معها.';
    }
    if (_isSafe) {
      return 'لم تظهر مؤشرات خطيرة واضحة، ومع ذلك يبقى التحقق المباشر أفضل عند وجود بيانات حساسة.';
    }
    return 'النتيجة ليست حاسمة بالكامل، لذلك تحتاج الرسالة إلى تحقق قبل الضغط أو مشاركة البيانات.';
  }

  // ignore: unused_element
  Widget _storyFlowCard(BuildContext context) {
    final steps = <(String, IconData, Color, String)>[
      (
        'الرسالة',
        Icons.message_outlined,
        AppTokens.brandCyan,
        _isUrlOnly
            ? 'تم التعامل معها كرابط مباشر.'
            : 'تمت قراءة النص والسياق العام.',
      ),
      (
        'المؤشرات',
        Icons.rule_folder_outlined,
        _color,
        _mainClassificationReason(context),
      ),
      (
        'الروابط',
        _hasUrl ? Icons.link_rounded : Icons.link_off_rounded,
        _hasUrl ? _urlStatusColor : AppTokens.neutral,
        _hasUrl
            ? _linkIntelligenceCopy
            : 'لم يتم العثور على رابط داخل الرسالة.',
      ),
      (
        'القرار',
        _icon,
        _color,
        'النتيجة النهائية ${item.result.finalScore}/100 بناءً على المؤشرات المتاحة.',
      ),
      ('التوصية', Icons.task_alt_rounded, _color, _primaryRecommendationText),
    ];

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'مسار التحقيق',
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 14),
          ...steps.asMap().entries.map(
            (entry) => StaggeredItem(
              index: entry.key,
              step: const Duration(milliseconds: 70),
              child: _storyStep(
                context,
                title: entry.value.$1,
                icon: entry.value.$2,
                color: entry.value.$3,
                text: entry.value.$4,
                isLast: entry.key == steps.length - 1,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _storyStep(
    BuildContext context, {
    required String title,
    required IconData icon,
    required Color color,
    required String text,
    required bool isLast,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  textAlign: TextAlign.right,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w700,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  text,
                  textAlign: TextAlign.right,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppTokens.mutedText(context),
                    height: 1.5,
                    fontWeight: FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Column(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.10),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: color, size: 17),
            ),
            if (!isLast)
              Container(
                width: 1.5,
                height: 36,
                color: AppTokens.outline(context).withValues(alpha: 0.45),
              ),
          ],
        ),
      ],
    );
  }

  String get _primaryRecommendationText {
    if (_isHigh) return 'لا تضغط على الرابط ولا تشارك أي رمز أو بيانات.';
    if (_isSafe) return 'لا توجد مؤشرات خطيرة، ويمكنك المتابعة بحذر.';
    return 'تحقق من الجهة والرابط قبل أي تفاعل.';
  }

  // ignore: unused_element
  Widget _whyTrustCard(BuildContext context) {
    final items = [
      ('تحليل نص عربي', Icons.translate_rounded),
      ('تحليل روابط', Icons.link_rounded),
      ('تحليل سياق', Icons.hub_outlined),
      ('قواعد تحقق', Icons.verified_outlined),
    ];

    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      color: AppTokens.surface(context).withValues(alpha: 0.74),
      border: Border.all(
        color: AppTokens.outline(context).withValues(alpha: 0.48),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'لماذا تثق بـ APG؟',
            textAlign: TextAlign.right,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w800,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 12),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                children: [
                  Icon(item.$2, color: AppTokens.brandCyan, size: 18),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      item.$1,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        height: 1.4,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                  const Icon(
                    Icons.check_rounded,
                    color: AppTokens.success,
                    size: 18,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _softInfoPill(
    BuildContext context, {
    required IconData icon,
    required String text,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.16)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 7),
          Flexible(
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w500,
                height: 1.25,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (kDebugMode) {
      debugPrint(
        'APG_SCORE_TRACE screen=result_details itemId=${item.id} '
        'analysisId=${item.result.remoteId} score=${item.result.finalScore}',
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(context.l10n.analysisDetails)),
      body: AppBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              20,
              16,
              20,
              AppTokens.bottomNavContentPadding,
            ),
            children: [
              FadeSlideIn(
                beginOffset: const Offset(0, 12),
                child: _hero(context),
              ),
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 70),
                child: _mainReasonCard(context),
              ),
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 120),
                child: _investigationContextCard(context),
              ),
              if (_hasEntitySummaryCard) ...[
                const SizedBox(height: 14),
                FadeSlideIn(
                  delay: const Duration(milliseconds: 145),
                  child: _entityIntelligenceCard(context),
                ),
              ],
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 170),
                child: _evidenceGroupsCard(context),
              ),
              if (_hasDynamicSignals) ...[
                const SizedBox(height: 14),
                FadeSlideIn(
                  delay: const Duration(milliseconds: 220),
                  child: _dynamicSandboxSection(context),
                ),
              ],
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 270),
                child: _recommendationCard(context),
              ),
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 320),
                child: _technicalMethodologyCard(context),
              ),
              const SizedBox(height: 14),
              _actionsBar(context),
              const SizedBox(height: 14),
              _feedbackInline(context),
            ],
          ),
        ),
      ),
    );
  }
}
