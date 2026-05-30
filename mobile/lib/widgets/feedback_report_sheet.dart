import 'package:flutter/material.dart';
import '../models/analysis_history_item.dart';
import '../services/local_storage_service.dart';
import '../services/reports_service.dart';
import '../theme/app_tokens.dart';
import 'apg_ui.dart';

class FeedbackReportSheet extends StatefulWidget {
  final AnalysisHistoryItem item;

  const FeedbackReportSheet({super.key, required this.item});

  static Future<void> show(
    BuildContext context,
    AnalysisHistoryItem item,
  ) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: Colors.transparent,
      barrierColor: Colors.black54,
      builder: (_) => FeedbackReportSheet(item: item),
    );
  }

  @override
  State<FeedbackReportSheet> createState() => _FeedbackReportSheetState();
}

class _FeedbackReportSheetState extends State<FeedbackReportSheet> {
  final TextEditingController _noteController = TextEditingController();
  String _selectedReason = 'كانت آمنة لكن صُنفت مشبوهة';
  bool _isSubmitting = false;

  final List<String> _reasons = const [
    'كانت آمنة لكن صُنفت مشبوهة',
    'كانت خطيرة لكن صُنفت آمنة',
    'درجة الخطورة غير مناسبة',
    'سبب التحليل غير واضح',
    'أخرى',
  ];

  Future<void> _submit() async {
    if (_isSubmitting) return;
    final analysisId = _serverAnalysisId();
    if (analysisId.isEmpty) {
      _showSnack(
        'هذه النتيجة غير محفوظة في الخادم. حلّل الرسالة مرة أخرى بعد تسجيل الدخول.',
      );
      return;
    }

    setState(() => _isSubmitting = true);
    final note = _noteController.text.trim();
    final message = note.isNotEmpty ? note : _selectedReason;
    final report = <String, dynamic>{
      'id': DateTime.now().microsecondsSinceEpoch.toString(),
      'resultId': analysisId,
      'messageText': widget.item.rawText,
      'currentLabel': widget.item.result.finalLabel,
      'riskScore': widget.item.result.finalScore,
      'reason': _selectedReason,
      'reportType': _reportTypeForReason(_selectedReason),
      'note': note,
      'sender': widget.item.sender,
      'url': widget.item.url,
      'createdAt': DateTime.now().toIso8601String(),
      'syncStatus': 'pending',
    };

    try {
      await const ReportsService().create(
        analysisId: analysisId,
        reportType: _reportTypeForReason(_selectedReason),
        message: message,
      );
      report['syncStatus'] = 'sent';
      await LocalStorageService.instance.saveFeedbackReport(report);
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(content: Text('تم إرسال البلاغ للأدمن بنجاح.')),
        );
    } catch (error) {
      report['syncStatus'] = 'failed';
      report['error'] = error.toString();
      await LocalStorageService.instance.saveFeedbackReport(report);
      if (!mounted) return;
      _showSnack(
        'تعذر إرسال البلاغ للخادم. تأكد من تشغيل الباك إند ثم حاول مرة أخرى.',
      );
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  String _serverAnalysisId() {
    final remoteId = widget.item.result.remoteId.trim();
    if (remoteId.isNotEmpty) {
      final parsed = int.tryParse(remoteId);
      return parsed != null && parsed > 0 ? remoteId : '';
    }
    // Local-only records used timestamp-like numeric IDs. Do not submit those
    // as server analysis IDs because the backend cannot link the report.
    if (widget.item.sourceTrust != 'server') return '';
    final id = widget.item.id.trim();
    final parsed = int.tryParse(id);
    return parsed != null && parsed > 0 ? id : '';
  }

  String _reportTypeForReason(String reason) {
    switch (reason) {
      case 'كانت آمنة لكن صُنفت مشبوهة':
      case 'كانت خطيرة لكن صُنفت آمنة':
        return 'wrong_classification';
      case 'درجة الخطورة غير مناسبة':
        return 'inaccurate_result';
      case 'سبب التحليل غير واضح':
        return 'app_issue';
      default:
        return 'manual_phishing_report';
    }
  }

  void _showSnack(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Padding(
        padding: EdgeInsets.fromLTRB(18, 8, 18, bottom + 18),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: AppTokens.surfaceGradient(context),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: AppTokens.outline(context).withValues(alpha: 0.85),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.28),
                blurRadius: 26,
                offset: const Offset(0, 14),
              ),
            ],
          ),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(
                  title: 'الإبلاغ عن نتيجة غير دقيقة',
                  subtitle:
                      'ساعدنا في تحسين APG. هل تعتقد أن الرسالة تم تصنيفها بشكل خاطئ؟',
                  icon: Icons.feedback_rounded,
                ),
                const SizedBox(height: 16),
                ..._reasons.map(
                  (reason) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: () => setState(() => _selectedReason = reason),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 11,
                        ),
                        decoration: BoxDecoration(
                          color: _selectedReason == reason
                              ? AppTokens.brand.withValues(alpha: 0.18)
                              : AppTokens.surfaceAlt(
                                  context,
                                ).withValues(alpha: 0.70),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: _selectedReason == reason
                                ? AppTokens.brandAlt.withValues(alpha: 0.45)
                                : AppTokens.outline(
                                    context,
                                  ).withValues(alpha: 0.55),
                          ),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              _selectedReason == reason
                                  ? Icons.radio_button_checked_rounded
                                  : Icons.radio_button_off_rounded,
                              color: _selectedReason == reason
                                  ? AppTokens.brandCyan
                                  : AppTokens.mutedText(context),
                              size: 20,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                reason,
                                textAlign: TextAlign.right,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  height: 1.45,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _noteController,
                  minLines: 3,
                  maxLines: 5,
                  textAlign: TextAlign.right,
                  textDirection: TextDirection.rtl,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(height: 1.5),
                  decoration: const InputDecoration(
                    labelText: 'أضف ملاحظة قصيرة',
                    hintText: 'اختياري',
                    prefixIcon: Icon(Icons.edit_note_rounded),
                    alignLabelWithHint: true,
                  ),
                ),
                const SizedBox(height: 16),
                PrimaryButton(
                  label: _isSubmitting
                      ? 'جارِ إرسال البلاغ...'
                      : 'إرسال البلاغ',
                  icon: Icons.send_rounded,
                  loading: _isSubmitting,
                  onPressed: _isSubmitting ? null : _submit,
                ),
                const SizedBox(height: 10),
                OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('إلغاء'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
