import 'package:flutter/widgets.dart';
import 'package:share_plus/share_plus.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import 'text_mapper.dart';

class AnalysisShareHelper {
  static String buildShareText(BuildContext context, AnalysisHistoryItem item) {
    final l10n = context.l10n;
    final result = item.result;
    final buffer = StringBuffer();
    final rawText = item.rawText.trim();
    final textOnlyUrl = RegExp(
      r'^(?:https?:\/\/|www\.)\S+$',
      caseSensitive: false,
    ).hasMatch(rawText);
    final displayUrl = item.url.trim().isNotEmpty
        ? item.url.trim()
        : (textOnlyUrl ? rawText : '');
    final isUrlOnly =
        result.modality?.trim().toLowerCase() == 'url_only' || textOnlyUrl;

    buffer.writeln(l10n.analysisDetails);
    buffer.writeln(
      '${l10n.label}: ${TextMapper.label(context, result.finalLabel)}',
    );
    buffer.writeln('${l10n.score}: ${result.finalScore}/100');
    buffer.writeln(
      '${l10n.confidence}: ${(result.confidence * 100).toStringAsFixed(1)}%',
    );

    final entityName = result.claimedEntity.trim().isNotEmpty
        ? result.claimedEntity.trim()
        : result.domainEntity.trim();
    if (entityName.isNotEmpty) {
      buffer.writeln('${l10n.claimedEntity}: $entityName');
    }

    buffer.writeln(
      '${l10n.channel}: ${TextMapper.channel(context, item.displayChannel)}',
    );

    if (item.sender.trim().isNotEmpty) {
      buffer.writeln('${l10n.sender}: ${item.sender}');
    }

    if (isUrlOnly) {
      buffer.writeln('${l10n.messageText}: محتوى الرسالة: غير قابل للتقييم');
    } else if (rawText.isNotEmpty) {
      buffer.writeln('${l10n.messageText}: $rawText');
    }

    if (displayUrl.isNotEmpty) {
      buffer.writeln('${l10n.url}: $displayUrl');
    } else {
      buffer.writeln('${l10n.url}: سلامة الرابط: غير قابل للتقييم');
    }

    if (result.reasons.isNotEmpty) {
      buffer.writeln('\n${l10n.reasons}:');
      for (final itemReason in result.reasons) {
        buffer.writeln('- ${TextMapper.reason(context, itemReason)}');
      }
    }

    if (result.actionItems.isNotEmpty) {
      buffer.writeln('\n${l10n.recommendedActions}:');
      for (final action in result.actionItems) {
        buffer.writeln('- ${TextMapper.action(context, action)}');
      }
    }

    final recommendation = _recommendationText(
      context,
      result.finalLabel,
      result.recommendation,
    );
    if (recommendation.trim().isNotEmpty) {
      buffer.writeln('\n${l10n.finalRecommendation}: $recommendation');
    }

    return buffer.toString().trim();
  }

  static String _recommendationText(
    BuildContext context,
    String label,
    String value,
  ) {
    if (value.trim().isNotEmpty) {
      return TextMapper.recommendation(context, value);
    }
    final isArabic = context.isArabic;
    switch (label.toLowerCase()) {
      case 'phishing':
        return isArabic
            ? 'لا تتفاعل مع هذه الرسالة. لا تضغط على الروابط ولا تشارك أي رمز أو بيانات.'
            : 'Do not interact with this message. Do not open links or share any codes or credentials.';
      case 'suspicious':
        return isArabic
            ? 'تحقق من الطلب عبر قناة رسمية قبل اتخاذ أي إجراء.'
            : 'Verify the request through an official channel before taking action.';
      default:
        return isArabic
            ? 'لا يظهر تهديد واضح الآن، لكن استخدم القنوات الرسمية للإجراءات الحساسة.'
            : 'No immediate threat is visible, but use official channels for sensitive actions.';
    }
  }

  static Future<void> shareAnalysis(
    BuildContext context,
    AnalysisHistoryItem item,
  ) async {
    final text = buildShareText(context, item);

    await SharePlus.instance.share(
      ShareParams(
        text: text,
        title: context.l10n.appTitle,
        subject: context.l10n.shareSubject,
      ),
    );
  }
}
