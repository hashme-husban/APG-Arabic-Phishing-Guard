import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../theme/app_tokens.dart';
import 'apg_ui.dart';

class AppReportIssueSheet extends StatefulWidget {
  const AppReportIssueSheet({super.key});

  static Future<void> show(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: AppTokens.isDark(context)
          ? const Color(0xFF04111C)
          : Theme.of(context).scaffoldBackgroundColor,
      builder: (_) => const AppReportIssueSheet(),
    );
  }

  @override
  State<AppReportIssueSheet> createState() => _AppReportIssueSheetState();
}

class _AppReportIssueSheetState extends State<AppReportIssueSheet> {
  final TextEditingController _noteController = TextEditingController();
  String _selected = 'safe_marked_suspicious';

  List<Map<String, String>> get _options => const [
    {
      'id': 'safe_marked_suspicious',
      'ar': 'كانت آمنة لكن صُنفت مشبوهة',
      'en': 'It was safe but marked suspicious',
    },
    {
      'id': 'fraud_marked_safe',
      'ar': 'كانت احتيالية لكن صُنفت آمنة',
      'en': 'It was fraudulent but marked safe',
    },
    {
      'id': 'bad_score',
      'ar': 'درجة الخطورة غير مناسبة',
      'en': 'The risk score is not suitable',
    },
    {
      'id': 'unclear_reason',
      'ar': 'سبب التحليل غير واضح',
      'en': 'The analysis reason is unclear',
    },
    {'id': 'other', 'ar': 'أخرى', 'en': 'Other'},
  ];

  void _submit() {
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(
            context.isArabic
                ? 'تم إرسال ملاحظتك بنجاح. شكرًا لمساعدتك في تحسين APG.'
                : 'Your feedback was sent successfully. Thank you for helping improve APG.',
          ),
        ),
      );
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    final isArabic = context.isArabic;
    return Directionality(
      textDirection: isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Padding(
        padding: EdgeInsets.fromLTRB(18, 6, 18, bottom + 22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionHeader(
              title: isArabic
                  ? 'الإبلاغ عن نتيجة غير دقيقة'
                  : 'Report an inaccurate result',
              subtitle: isArabic
                  ? 'ساعدنا في تحسين APG. هل تعتقد أن الرسالة تم تصنيفها بشكل خاطئ؟'
                  : 'Help improve APG. Do you think this message was classified incorrectly?',
              icon: Icons.flag_rounded,
            ),
            const SizedBox(height: 16),
            ..._options.map((option) {
              final selected = _selected == option['id'];
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: InkWell(
                  borderRadius: BorderRadius.circular(18),
                  onTap: () => setState(() => _selected = option['id']!),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: selected
                          ? AppTokens.brand.withValues(alpha: 0.18)
                          : AppTokens.surfaceAlt(
                              context,
                            ).withValues(alpha: 0.72),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: selected
                            ? AppTokens.brandCyan.withValues(alpha: 0.35)
                            : AppTokens.outline(
                                context,
                              ).withValues(alpha: 0.65),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          selected
                              ? Icons.radio_button_checked_rounded
                              : Icons.radio_button_off_rounded,
                          color: selected
                              ? AppTokens.brandCyan
                              : AppTokens.mutedText(context),
                          size: 20,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            isArabic ? option['ar']! : option['en']!,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }),
            const SizedBox(height: 8),
            TextField(
              controller: _noteController,
              minLines: 2,
              maxLines: 4,
              textAlign: isArabic ? TextAlign.right : TextAlign.left,
              decoration: InputDecoration(
                hintText: isArabic
                    ? 'أضف ملاحظة قصيرة (اختياري)'
                    : 'Add a short note (optional)',
                prefixIcon: const Icon(Icons.edit_note_rounded),
              ),
            ),
            const SizedBox(height: 16),
            PrimaryButton(
              label: isArabic ? 'إرسال الملاحظة' : 'Send feedback',
              icon: Icons.send_rounded,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }
}
