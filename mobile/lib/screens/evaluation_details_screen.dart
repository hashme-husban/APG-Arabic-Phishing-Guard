import 'package:flutter/material.dart';
import '../models/analysis_history_item.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import '../widgets/app_background.dart';
import '../widgets/apg_ui.dart';
import '../widgets/risk_factor_card.dart';

class EvaluationDetailsScreen extends StatelessWidget {
  final AnalysisHistoryItem item;
  const EvaluationDetailsScreen({super.key, required this.item});

  Color _colorForScore(int score) {
    if (score >= 70) return AppTokens.danger;
    if (score >= 31) return AppTokens.warning;
    return AppTokens.success;
  }

  String _statusForScore(int score) {
    if (score >= 70) return 'مرتفع';
    if (score >= 31) return 'متوسط';
    return 'منخفض';
  }

  int _layerScore(String key, int fallback) {
    for (final layer in item.result.layers) {
      if (layer.keyName.toLowerCase() == key) return layer.score;
    }
    return fallback;
  }

  bool _textIsOnlyUrl(String text) {
    return RegExp(
      r'^(?:https?:\/\/|www\.)\S+$',
      caseSensitive: false,
    ).hasMatch(text.trim());
  }

  @override
  Widget build(BuildContext context) {
    final rawText = item.rawText.trim();
    final hasUrl = item.url.trim().isNotEmpty || _textIsOnlyUrl(rawText);
    final hasText = rawText.isNotEmpty && !_textIsOnlyUrl(rawText);
    final textUnevaluable =
        item.result.modality?.trim().toLowerCase() == 'url_only' || !hasText;

    // Sender is unevaluable when the value is blank or looks like a package name (auto-captured)
    final senderMissing =
        item.sender.trim().isEmpty ||
        RegExp(
          r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$',
        ).hasMatch(item.sender.trim());
    final senderScore = _layerScore(
      'sender',
      item.sourceTrust == 'unknown'
          ? 81
          : item.sourceTrust == 'known'
          ? 12
          : 48,
    );

    final policyScore = _layerScore(
      'policy',
      item.claimedEntityInput.trim().isEmpty ? 28 : 38,
    );

    final textScore = _layerScore('text', item.result.finalScore);

    final urlScore = hasUrl ? _layerScore('url', item.result.finalScore) : -1;
    final indicatorsScore = item.selectedIndicators.isEmpty
        ? 0
        : (item.selectedIndicators.length * 12).clamp(18, 92).toInt();

    return Scaffold(
      appBar: AppBar(title: const Text('منهجية التقييم')),
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
              const ScreenHeader(
                title: 'منهجية التقييم',
                subtitle: 'يوضح هذا القسم كيف جمع APG المؤشرات لتكوين النتيجة.',
                icon: Icons.account_tree_rounded,
              ),
              const SizedBox(height: 14),
              RiskFactorCard(
                title: 'هوية المرسل',
                scoreText: senderMissing
                    ? 'غير قابلة للتقييم'
                    : '$senderScore/100',
                status: senderMissing
                    ? 'غير قابلة للتقييم'
                    : _statusForScore(senderScore),
                color: senderMissing
                    ? AppTokens.neutral
                    : _colorForScore(senderScore),
                icon: Icons.person_rounded,
                description: senderMissing
                    ? 'هوية المرسل غير متاحة أو مجهولة، ولا يمكن تقييمها.'
                    : (senderScore >= 70
                          ? 'اسم المرسل لا يبدو موثوقًا أو يحتاج تحققًا.'
                          : 'هوية المرسل لا تحتوي مؤشرات خطيرة واضحة.'),
              ),
              RiskFactorCard(
                title: 'موثوقية الجهة المذكورة',
                scoreText: '$policyScore/100',
                status: _statusForScore(policyScore),
                color: _colorForScore(policyScore),
                icon: Icons.apartment_rounded,
                description:
                    'يقيس هذا العامل مدى اتساق الجهة المذكورة مع هوية المرسل أو الرابط.',
              ),
              RiskFactorCard(
                title: 'محتوى الرسالة',
                scoreText: textUnevaluable
                    ? 'غير قابل للتقييم'
                    : '$textScore/100',
                status: textUnevaluable
                    ? 'غير قابل للتقييم'
                    : _statusForScore(textScore),
                color: textUnevaluable
                    ? AppTokens.neutral
                    : _colorForScore(textScore),
                icon: Icons.article_rounded,
                description: textUnevaluable
                    ? 'محتوى الرسالة: غير قابل للتقييم — تم إدخال رابط فقط دون نص.'
                    : (TextMapper.summary(context, item.result.summary).isEmpty
                          ? 'تم فحص النص بحثًا عن طلبات حساسة أو صياغة استعجالية.'
                          : TextMapper.summary(context, item.result.summary)),
              ),
              RiskFactorCard(
                title: 'سلامة الرابط',
                scoreText: hasUrl ? '$urlScore/100' : 'غير قابل للتقييم',
                status: hasUrl ? _statusForScore(urlScore) : 'غير قابل للتقييم',
                color: hasUrl ? _colorForScore(urlScore) : AppTokens.neutral,
                icon: Icons.link_rounded,
                description: hasUrl
                    ? 'تم إدخال رابط وفحصه ضمن مؤشرات الخطورة.'
                    : 'سلامة الرابط: غير قابل للتقييم — لم يتم إدخال رابط.',
              ),
              RiskFactorCard(
                title: 'المؤشرات الإضافية',
                scoreText: item.selectedIndicators.isEmpty
                    ? 'غير موجود'
                    : '$indicatorsScore/100',
                status: item.selectedIndicators.isEmpty
                    ? 'غير موجود'
                    : _statusForScore(indicatorsScore),
                color: item.selectedIndicators.isEmpty
                    ? AppTokens.neutral
                    : _colorForScore(indicatorsScore),
                icon: Icons.notifications_active_rounded,
                description: item.selectedIndicators.isEmpty
                    ? 'لم يفعّل المستخدم مؤشرات إضافية في التحليل الكامل.'
                    : item.selectedIndicators.join('، '),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
