import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_result.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import 'app_surface_card.dart';

class RecommendationCard extends StatelessWidget {
  final AnalysisResult result;

  const RecommendationCard({super.key, required this.result});

  String _fallbackRecommendation(BuildContext context) {
    final value = result.recommendation.trim();
    if (value.isNotEmpty) return TextMapper.recommendation(context, value);

    final label = result.finalLabel.toLowerCase();
    final isArabic = context.isArabic;
    if (label == 'phishing') {
      return isArabic
          ? 'لا تتفاعل مع هذه الرسالة. لا تضغط على الروابط ولا تشارك أي رمز أو بيانات، وتحقق فقط من التطبيق أو الموقع الرسمي.'
          : 'Do not interact with this message. Do not open links or share codes, and verify only through the official app or website.';
    }
    if (label == 'suspicious') {
      return isArabic
          ? 'توقف قبل اتخاذ أي إجراء. تحقق من الطلب عبر قناة رسمية، خصوصًا قبل فتح الروابط أو مشاركة أي معلومات.'
          : 'Pause before acting. Verify the request through an official channel, especially before opening links or sharing information.';
    }
    return isArabic
        ? 'لا يظهر تهديد واضح الآن. استمر بالحذر المعتاد، واستخدم القنوات الرسمية لأي إجراء حساس.'
        : 'No immediate threat is visible. Continue using normal caution and use official channels for sensitive actions.';
  }

  IconData _iconForLabel() {
    switch (result.finalLabel.toLowerCase()) {
      case 'phishing':
        return Icons.gpp_bad_rounded;
      case 'suspicious':
        return Icons.report_problem_rounded;
      case 'safe':
        return Icons.verified_user_rounded;
      default:
        return Icons.tips_and_updates_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = TextMapper.riskColor(result.finalLabel);
    final text = _fallbackRecommendation(context);

    return AppSurfaceCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(_iconForLabel(), color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  context.l10n.finalRecommendation,
                  style: Theme.of(
                    context,
                  ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppTokens.riskGradient(result.finalLabel),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: color.withValues(alpha: 0.26)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.check_circle_rounded, color: color, size: 22),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    text,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                      height: 1.65,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
