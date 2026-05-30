import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../models/analysis_history_item.dart';
import '../services/apg_api_service.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import '../widgets/apg_ui.dart';

class QuickScanSheet extends StatefulWidget {
  final VoidCallback onOpenFullAnalyze;
  const QuickScanSheet({super.key, required this.onOpenFullAnalyze});
  @override
  State<QuickScanSheet> createState() => _QuickScanSheetState();
}

class _QuickScanSheetState extends State<QuickScanSheet> {
  final TextEditingController _inputController = TextEditingController();
  static const ApgApiService _api = ApgApiService();
  bool _isLoading = false;
  String? _errorMessage;

  bool get _canAnalyze => _inputController.text.trim().isNotEmpty;

  @override
  void initState() {
    super.initState();
    _inputController.addListener(() {
      if (mounted) setState(() {});
    });
  }

  bool _looksLikeUrl(String value) {
    final text = value.trim().toLowerCase();
    return text.startsWith('http://') ||
        text.startsWith('https://') ||
        text.startsWith('www.') ||
        (text.contains('.') && !text.contains(' '));
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData('text/plain');
    final text = data?.text?.trim() ?? '';
    if (text.isEmpty) return;
    setState(() {
      _inputController.text = text;
      _errorMessage = null;
    });
  }

  Future<void> _runQuickScan() async {
    FocusScope.of(context).unfocus();
    final input = _inputController.text.trim();
    if (input.isEmpty) {
      setState(() => _errorMessage = 'الصق الرسالة أو الرابط أولًا.');
      return;
    }
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final isUrl = _looksLikeUrl(input);
      final result = await _api.analyze(
        rawText: isUrl ? '' : input,
        url: isUrl ? input : '',
        channel: isUrl ? 'url' : 'quick',
      );
      final item = AnalysisHistoryItem(
        id: DateTime.now().microsecondsSinceEpoch.toString(),
        sender: 'تحليل سريع',
        rawText: isUrl ? '' : input,
        url: isUrl ? input : '',
        result: result,
        createdAt: DateTime.now(),
        channel: isUrl ? 'url' : 'quick',
        sourceTrust: 'system',
        linkOpened: isUrl ? 'unknown' : 'no_link',
      );
      if (!mounted) return;
      Navigator.of(context).pop(item);
    } catch (e) {
      setState(
        () => _errorMessage = TextMapper.error(
          context,
          e.toString().replaceFirst('Exception: ', ''),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _inputController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Padding(
        padding: EdgeInsets.fromLTRB(16, 8, 16, bottomInset + 16),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppTokens.surface(context),
            borderRadius: BorderRadius.circular(AppTokens.radiusLg),
            border: Border.all(
              color: AppTokens.outline(context).withValues(alpha: 0.80),
            ),
            boxShadow: AppTokens.cardShadow(context),
          ),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Expanded(
                      child: SectionHeader(
                        title: 'تحليل سريع',
                        subtitle: 'الصق رسالة أو رابطًا وسيحلله APG فورًا.',
                        icon: Icons.bolt_rounded,
                      ),
                    ),
                    TextButton(
                      onPressed: _isLoading ? null : widget.onOpenFullAnalyze,
                      child: const Text('فتح التحليل'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _inputController,
                  enabled: !_isLoading,
                  minLines: 5,
                  maxLines: 8,
                  maxLength: 1000,
                  textAlign: TextAlign.right,
                  decoration: const InputDecoration(
                    hintText: 'الصق الرسالة أو الرابط هنا...',
                    prefixIcon: Padding(
                      padding: EdgeInsetsDirectional.only(start: 10, top: 10),
                      child: Icon(Icons.message_rounded),
                    ),
                    alignLabelWithHint: true,
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _isLoading ? null : _paste,
                  icon: const Icon(Icons.content_paste_rounded, size: 17),
                  label: const Text('لصق من الحافظة'),
                ),
                if (_errorMessage != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    _errorMessage!,
                    style: const TextStyle(
                      color: AppTokens.danger,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                PrimaryButton(
                  label: _isLoading ? 'جارِ التحليل...' : 'تحليل الآن',
                  icon: Icons.bolt_rounded,
                  loading: _isLoading,
                  onPressed: (!_isLoading && _canAnalyze)
                      ? _runQuickScan
                      : null,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
