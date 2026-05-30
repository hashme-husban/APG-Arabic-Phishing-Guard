import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import '../l10n/l10n_extensions.dart';
import '../models/analysis_history_item.dart';
import '../services/apg_api_service.dart';
import '../services/image_intelligence_service.dart';
import '../theme/app_tokens.dart';
import '../utils/text_mapper.dart';
import '../widgets/analyze_form_card.dart';
import '../widgets/page_intro_header.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/apg_ui.dart';
import '../widgets/analysis_scanning_experience.dart';
import '../widgets/circular_score_meter.dart';
import '../widgets/motion.dart';
import 'result_details_screen.dart';

class AnalyzeScreen extends StatefulWidget {
  final ValueChanged<AnalysisHistoryItem>? onAnalysisSaved;

  const AnalyzeScreen({super.key, this.onAnalysisSaved});

  @override
  State<AnalyzeScreen> createState() => _AnalyzeScreenState();
}

class _AnalyzeScreenState extends State<AnalyzeScreen> {
  final TextEditingController _senderController = TextEditingController();
  final TextEditingController _messageController = TextEditingController();
  final TextEditingController _urlController = TextEditingController();
  static const ApgApiService _api = ApgApiService();

  bool _isLoading = false;
  bool _isUrlAnalysis = false;
  String? _errorMessage;
  String? _errorTitle;
  String _selectedChannel = 'unknown';
  AnalysisHistoryItem? _lastResult;

  // QR scan state
  File? _selectedImage;
  bool _isExtractingQr = false;
  String? _imageStatusMsg;
  String? _qrContent;
  String? _analysisSourceTag; // 'qr_image' | null

  static const int _maxInputLength = 1000;

  bool get _canAnalyze =>
      _messageController.text.trim().isNotEmpty ||
      _urlController.text.trim().isNotEmpty;

  bool get _inputTooLong =>
      _messageController.text.trim().length > _maxInputLength;

  bool _looksLikeUrl(String value) {
    final text = value.trim().toLowerCase();
    return text.startsWith('http://') ||
        text.startsWith('https://') ||
        text.startsWith('www.') ||
        (text.contains('.') && !text.contains(' '));
  }

  bool _containsUrl(String value) => _extractUrlsFromText(value).isNotEmpty;

  List<String> _extractUrlsFromText(String value) {
    return ImageIntelligenceService.extractUrlsFromText(value);
  }

  bool _isClearlyBrokenUrl(String value) {
    final text = value.trim();
    if (!(text.startsWith('http://') || text.startsWith('https://'))) {
      return false;
    }
    final uri = Uri.tryParse(text);
    return uri == null || uri.host.trim().isEmpty || !uri.host.contains('.');
  }

  @override
  void initState() {
    super.initState();
    _messageController.addListener(_handleInputChanged);
  }

  void _handleInputChanged() {
    if (!mounted) return;
    setState(() {
      if (_errorMessage != null) {
        _errorMessage = null;
        _errorTitle = null;
      }
    });
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  void _setError(String message, {String? title}) {
    if (!mounted) return;
    setState(() {
      _errorTitle = title ?? context.l10n.analyzeFailedTitle;
      _errorMessage = message;
    });
  }

  String _friendlyAnalyzeError(Object error) {
    final l10n = context.l10n;
    final raw = error.toString().replaceFirst('Exception: ', '').trim();
    final text = raw.toLowerCase();
    if (text.contains('401') ||
        text.contains('unauthorized') ||
        raw.contains('انتهت الجلسة') ||
        raw.contains('سجّل الدخول')) {
      return l10n.sessionExpiredError;
    }
    if (text.contains('timeout') ||
        text.contains('timed out') ||
        raw.contains('انتهت المهلة')) {
      return l10n.connectionError;
    }
    if (text.contains('socket') ||
        text.contains('clientexception') ||
        text.contains('connection') ||
        text.contains('network') ||
        raw.contains('تعذر الاتصال بالخادم')) {
      return l10n.connectionError;
    }
    if (text.contains('400') ||
        raw.contains('الصق الرسالة') ||
        raw.contains('غير صالحة')) {
      return l10n.emptyInputError;
    }
    if (text.contains('500') ||
        text.contains('503') ||
        raw.contains('الخادم') ||
        raw.contains('فشل التحليل')) {
      return l10n.connectionError;
    }
    return TextMapper.error(context, raw);
  }

  Future<void> _copyResult(AnalysisHistoryItem item) async {
    final l10n = context.l10n;
    final text = [
      'APG: ${TextMapper.label(context, item.result.finalLabel)}',
      l10n.riskScoreLabel(item.result.finalScore),
      if (item.previewText.trim().isNotEmpty) item.previewText.trim(),
      if (item.url.trim().isNotEmpty) item.url.trim(),
      TextMapper.recommendation(context, item.result.recommendation),
    ].join('\n');
    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) return;
    _showSnack(l10n.resultCopied);
  }

  Future<void> _pasteMessageFromClipboard() async {
    final l10n = context.l10n;
    final data = await Clipboard.getData('text/plain');
    if (!mounted) return;
    final text = data?.text?.trim() ?? '';
    if (text.isEmpty) return _showSnack(l10n.clipboardEmpty);
    setState(() {
      _messageController.text = text;
      _errorMessage = null;
      _errorTitle = null;
    });
    _showSnack(l10n.textPasted);
  }

  Future<void> _pasteUrlFromClipboard() async {
    final l10n = context.l10n;
    final data = await Clipboard.getData('text/plain');
    if (!mounted) return;
    final text = data?.text?.trim() ?? '';
    if (text.isEmpty) return _showSnack(l10n.clipboardEmpty);
    setState(() {
      _messageController.text = text;
      _selectedChannel = 'url';
      _errorMessage = null;
      _errorTitle = null;
    });
    _showSnack(l10n.urlPasted);
  }

  Future<void> _analyzeMessage() async {
    if (_isLoading) return;
    FocusScope.of(context).unfocus();
    final input = _messageController.text.trim();
    final sender = _senderController.text.trim();
    final explicitUrl = _urlController.text.trim();
    final isUrlOnly = explicitUrl.isEmpty && _looksLikeUrl(input);
    final rawText = isUrlOnly ? '' : input;
    final url = explicitUrl.isNotEmpty ? explicitUrl : (isUrlOnly ? input : '');
    final analysisUrls = <String>[if (url.isNotEmpty) url];

    final l10n = context.l10n;
    if (input.isEmpty && url.isEmpty) {
      _setError(l10n.emptyInputError, title: l10n.noContentTitle);
      HapticFeedback.lightImpact();
      return;
    }
    if (_inputTooLong) {
      _setError(
        l10n.textTooLongMessage(_maxInputLength),
        title: l10n.textTooLongTitle,
      );
      HapticFeedback.lightImpact();
      return;
    }
    if (_isClearlyBrokenUrl(input) || _isClearlyBrokenUrl(url)) {
      _setError(l10n.emptyInputError, title: l10n.invalidUrlTitle);
      HapticFeedback.lightImpact();
      return;
    }

    HapticFeedback.selectionClick();
    setState(() {
      _isLoading = true;
      _isUrlAnalysis =
          url.isNotEmpty || _looksLikeUrl(input) || _containsUrl(input);
      _errorMessage = null;
      _errorTitle = null;
      _lastResult = null;
    });

    try {
      final result = await _api.analyze(
        sender: sender,
        rawText: rawText,
        url: url,
        urls: analysisUrls,
        channel: _selectedChannel,
      );
      final createdAt =
          DateTime.tryParse(result.createdAtIso) ?? DateTime.now();
      final remoteId = result.remoteId.trim();
      final serverText = result.maskedText.trim();
      final serverUrl = result.detectedUrl.trim();
      final item = AnalysisHistoryItem(
        id: remoteId.isNotEmpty
            ? remoteId
            : DateTime.now().microsecondsSinceEpoch.toString(),
        sender: sender,
        rawText: serverText.isNotEmpty ? serverText : rawText,
        url: serverUrl.isNotEmpty ? serverUrl : url,
        result: result,
        createdAt: createdAt,
        channel: (result.channel.trim().isNotEmpty
            ? result.channel
            : (url.isNotEmpty && rawText.isEmpty ? 'url' : _selectedChannel)),
        selectedIndicators: const <String>[],
        sourceTrust: remoteId.isNotEmpty ? 'server' : 'local',
        linkOpened: (serverUrl.isNotEmpty || url.isNotEmpty)
            ? 'unknown'
            : 'no_link',
        notes: '',
      );
      widget.onAnalysisSaved?.call(item);
      if (!mounted) return;
      setState(() => _lastResult = item);
      HapticFeedback.mediumImpact();
    } catch (e) {
      if (!mounted) return;
      _setError(_friendlyAnalyzeError(e));
      HapticFeedback.heavyImpact();
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _clearAll() {
    setState(() {
      _senderController.clear();
      _messageController.clear();
      _urlController.clear();
      _selectedChannel = 'unknown';
      _errorMessage = null;
      _errorTitle = null;
      _lastResult = null;
      _selectedImage = null;
      _isExtractingQr = false;
      _imageStatusMsg = null;
      _qrContent = null;
      _analysisSourceTag = null;
    });
    _showSnack(context.l10n.fieldsCleared);
  }

  Future<void> _pickImageFromGallery() async {
    await _pickFromSource(ImageSource.gallery);
  }

  Future<void> _pickImageFromCamera() async {
    await _pickFromSource(ImageSource.camera);
  }

  Future<void> _pickFromSource(ImageSource source) async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: source, imageQuality: 85);
      if (!mounted) return;
      if (picked == null) return;
      await _processPickedImage(File(picked.path));
    } catch (e) {
      if (!mounted) return;
      _showSnack(
        source == ImageSource.camera ? 'تعذر فتح الكاميرا' : 'تعذر فتح المعرض',
      );
    }
  }

  Future<void> _processPickedImage(File file) async {
    if (!mounted) return;
    setState(() {
      _selectedImage = file;
      _isExtractingQr = true;
      _imageStatusMsg = null;
      _qrContent = null;
      _analysisSourceTag = null;
      _errorMessage = null;
      _errorTitle = null;
      _lastResult = null;
    });
    try {
      final result = await ImageIntelligenceService().processImage(file);
      if (!mounted) return;
      if (result.error != null) {
        setState(() {
          _isExtractingQr = false;
          _imageStatusMsg = 'تعذر فحص الصورة';
        });
        return;
      }
      if (result.hasQr && result.qrValues.isNotEmpty) {
        final qr = result.qrValues.first;
        setState(() {
          _isExtractingQr = false;
          _qrContent = qr;
          _imageStatusMsg = null;
          _analysisSourceTag = 'qr_image';
          _messageController.text = qr;
          _urlController.clear();
          _isUrlAnalysis = _looksLikeUrl(qr);
        });
        await Future.delayed(const Duration(milliseconds: 380));
        if (mounted && !_isLoading) _analyzeMessage();
      } else {
        // No QR code detected in this image
        if (mounted) {
          setState(() {
            _isExtractingQr = false;
            _imageStatusMsg = 'لم يُعثر على رمز QR في الصورة';
            _analysisSourceTag = null;
          });
        }
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isExtractingQr = false;
        _imageStatusMsg = 'تعذر فحص الصورة';
      });
    }
  }

  void _clearImage() {
    setState(() {
      _selectedImage = null;
      _isExtractingQr = false;
      _imageStatusMsg = null;
      _qrContent = null;
      _analysisSourceTag = null;
    });
  }

  Widget _resultCard(BuildContext context, AnalysisHistoryItem item) {
    final color = TextMapper.riskColor(item.result.finalLabel);
    final label = TextMapper.label(context, item.result.finalLabel);
    final isHigh =
        item.result.finalLabel.toLowerCase() == 'phishing' ||
        item.result.finalScore >= 61;
    final isSafe =
        item.result.finalLabel.toLowerCase() == 'safe' ||
        item.result.finalScore <= 30;
    final reasons = item.result.reasons
        .map((e) => TextMapper.reason(context, e))
        .where((e) => e.trim().isNotEmpty)
        .toList();
    final actions = item.result.actionItems
        .map((e) => TextMapper.action(context, e))
        .where((e) => e.trim().isNotEmpty)
        .toList();
    final summary = TextMapper.summary(context, item.result.summary);
    final shortSummary = _shortResultSentence(
      context,
      isHigh: isHigh,
      isSafe: isSafe,
    );
    final mainReason = reasons.isNotEmpty
        ? reasons.first
        : (summary.trim().isNotEmpty
              ? summary
              : TextMapper.recommendation(context, item.result.recommendation));
    final indicators = _resultIndicators(context, item).take(5).toList();
    final contextChips = _resultContextChips(context, item);
    final primaryAction = actions.isNotEmpty
        ? actions.first
        : TextMapper.recommendation(context, item.result.recommendation);
    final confidencePercent = _resultConfidencePercent(item.result.confidence);

    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: const Duration(milliseconds: 420),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) => Opacity(
        opacity: value,
        child: Transform.translate(
          offset: Offset(0, 18 * (1 - value)),
          child: child,
        ),
      ),
      child: AppSurfaceCard(
        padding: const EdgeInsets.all(0),
        gradient: AppTokens.riskGradient(item.result.finalLabel),
        border: Border.all(
          color: color.withValues(alpha: isHigh ? 0.42 : 0.24),
        ),
        glow: isHigh,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_analysisSourceTag == 'qr_image')
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 14, 18, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 7,
                  ),
                  decoration: BoxDecoration(
                    color: AppTokens.brandCyan.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: AppTokens.brandCyan.withValues(alpha: 0.24),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.qr_code_rounded,
                        size: 13,
                        color: AppTokens.brandCyan,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'مصدر التحليل: رمز QR من صورة',
                        style: TextStyle(
                          color: AppTokens.brandCyan,
                          fontWeight: FontWeight.w900,
                          fontSize: 11.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  ProtectionPulseRing(
                    color: color,
                    size: 86,
                    maxExpand: isHigh ? 30 : 22,
                    maxAlpha: isHigh ? 0.28 : 0.16,
                    child: CircularScoreMeter(
                      score: item.result.finalScore,
                      color: color,
                      size: 86,
                      caption: context.l10n.score,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            StatusBadge(
                              label: label,
                              color: color,
                              icon: _resultIcon(item.result.finalLabel),
                            ),
                            if (confidencePercent != null)
                              _mutedBadge(
                                context,
                                '${context.isArabic ? 'الثقة' : 'Confidence'} $confidencePercent%',
                                Icons.insights_rounded,
                              ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text(
                          _resultHeadline(
                            context,
                            isHigh: isHigh,
                            isSafe: isSafe,
                          ),
                          textAlign: TextAlign.start,
                          style: Theme.of(context).textTheme.titleLarge
                              ?.copyWith(
                                fontWeight: FontWeight.w900,
                                height: 1.25,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          shortSummary,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: AppTokens.mutedText(context),
                                height: 1.45,
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTokens.surfaceAlt(context).withValues(alpha: 0.62),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: color.withValues(alpha: 0.18)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            context.isArabic ? 'السبب الرئيسي' : 'Main reason',
                            style: Theme.of(context).textTheme.labelLarge
                                ?.copyWith(
                                  color: color,
                                  fontWeight: FontWeight.w900,
                                ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            mainReason,
                            maxLines: 3,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(
                                  height: 1.5,
                                  fontWeight: FontWeight.w800,
                                ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    Icon(
                      isSafe
                          ? Icons.verified_rounded
                          : Icons.report_problem_rounded,
                      color: color,
                      size: 22,
                    ),
                  ],
                ),
              ),
            ),
            if (contextChips.isNotEmpty) ...[
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                child: Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: contextChips
                      .map((chip) => _mutedBadge(context, chip.$1, chip.$2))
                      .toList(),
                ),
              ),
            ],
            if (indicators.isNotEmpty) ...[
              const SizedBox(height: 14),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: indicators.asMap().entries.map((entry) {
                    final indicator = entry.value;
                    return StaggeredItem(
                      index: entry.key,
                      child: _indicatorPill(
                        context,
                        indicator.$1,
                        indicator.$2,
                        indicator.$3,
                      ),
                    );
                  }).toList(),
                ),
              ),
            ],
            const SizedBox(height: 14),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Text(
                context.isArabic ? 'الإجراء الموصى به' : 'Recommended action',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                  height: 1.25,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: color.withValues(alpha: 0.22)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      isHigh ? Icons.block_rounded : Icons.task_alt_rounded,
                      color: color,
                      size: 20,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        primaryAction,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppTokens.textPrimary(context),
                          fontWeight: FontWeight.w900,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 11,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: AppTokens.success.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: AppTokens.success.withValues(alpha: 0.20),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.bookmark_added_rounded,
                      color: AppTokens.success,
                      size: 16,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      context.l10n.savedToHistory,
                      style: const TextStyle(
                        color: AppTokens.success,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  FilledButton.icon(
                    onPressed: () => Navigator.of(context).push(
                      apgSlideFadeRoute(
                        ResultDetailsScreen(
                          item: item,
                          sourceTag: _analysisSourceTag,
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.manage_search_rounded),
                    label: Text(context.l10n.openDetails),
                  ),
                  const SizedBox(height: 9),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => _copyResult(item),
                          icon: const Icon(Icons.copy_rounded),
                          label: Text(context.l10n.copyResultLabel),
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: TextButton.icon(
                          onPressed: _clearAll,
                          icon: const Icon(Icons.refresh_rounded),
                          label: Text(context.l10n.analyzeAnother),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ignore: unused_element
  Widget _resultStoryCard(BuildContext context, AnalysisHistoryItem item) {
    final color = TextMapper.riskColor(item.result.finalLabel);
    final label = TextMapper.label(context, item.result.finalLabel);
    final isHigh =
        item.result.finalLabel.toLowerCase() == 'phishing' ||
        item.result.finalScore >= 61;
    final isSafe =
        item.result.finalLabel.toLowerCase() == 'safe' ||
        item.result.finalScore <= 30;
    final confidencePercent = _resultConfidencePercent(item.result.confidence);
    final steps = _investigationSteps(context, item);
    final actionItems = item.result.actionItems
        .map((e) => TextMapper.action(context, e))
        .where((e) => e.trim().isNotEmpty)
        .toList();
    final action = actionItems.isEmpty ? null : actionItems.first;

    return FadeSlideIn(
      beginOffset: const Offset(0, 14),
      duration: const Duration(milliseconds: 420),
      child: AppSurfaceCard(
        padding: const EdgeInsets.all(18),
        gradient: LinearGradient(
          colors: [
            AppTokens.surface(context).withValues(alpha: 0.94),
            color.withValues(alpha: 0.055),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: color.withValues(alpha: 0.22)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_analysisSourceTag == 'qr_image') ...[
              Align(
                alignment: AlignmentDirectional.centerStart,
                child: _mutedBadge(
                  context,
                  'مصدر التحليل: رمز QR من صورة',
                  Icons.qr_code_rounded,
                ),
              ),
              const SizedBox(height: 12),
            ],
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                ProtectionPulseRing(
                  color: color,
                  size: 92,
                  maxExpand: 18,
                  maxAlpha: isHigh ? 0.16 : 0.10,
                  child: CircularScoreMeter(
                    score: item.result.finalScore,
                    color: color,
                    size: 92,
                    strokeWidth: 8,
                    caption: '/100',
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          StatusBadge(
                            label: label,
                            color: color,
                            icon: _resultIcon(item.result.finalLabel),
                          ),
                          if (confidencePercent != null)
                            _mutedBadge(
                              context,
                              '${context.isArabic ? 'الثقة' : 'Confidence'} $confidencePercent%',
                              Icons.insights_rounded,
                            ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        _resultHeadline(
                          context,
                          isHigh: isHigh,
                          isSafe: isSafe,
                        ),
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                          height: 1.25,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        _shortResultSentence(
                          context,
                          isHigh: isHigh,
                          isSafe: isSafe,
                        ),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppTokens.mutedText(context),
                          height: 1.45,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              'كيف وصل APG لهذه النتيجة؟',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 12),
            ...steps.asMap().entries.map(
              (entry) => StaggeredItem(
                index: entry.key,
                step: const Duration(milliseconds: 55),
                child: _investigationStepRow(
                  context,
                  label: entry.value.$1,
                  icon: entry.value.$2,
                  impact: entry.value.$3,
                  color: entry.value.$4,
                ),
              ),
            ),
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.09),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: color.withValues(alpha: 0.18)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    isHigh ? Icons.block_rounded : Icons.task_alt_rounded,
                    color: color,
                    size: 20,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'التوصية النهائية',
                          style: Theme.of(context).textTheme.labelLarge
                              ?.copyWith(
                                color: color,
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          action ??
                              _recommendationText(
                                context,
                                isHigh: isHigh,
                                isSafe: isSafe,
                              ),
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                height: 1.5,
                                fontWeight: FontWeight.w500,
                              ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).push(
                apgSlideFadeRoute(
                  ResultDetailsScreen(
                    item: item,
                    sourceTag: _analysisSourceTag,
                  ),
                ),
              ),
              icon: const Icon(Icons.manage_search_rounded),
              label: const Text('عرض التفاصيل'),
            ),
            const SizedBox(height: 9),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _copyResult(item),
                    icon: const Icon(Icons.copy_rounded),
                    label: const Text('نسخ النتيجة'),
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: TextButton.icon(
                    onPressed: _clearAll,
                    icon: const Icon(Icons.refresh_rounded),
                    label: Text(context.l10n.analyzeAnother),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  List<(String, IconData, String, Color)> _investigationSteps(
    BuildContext context,
    AnalysisHistoryItem item,
  ) {
    final score = item.result.finalScore.clamp(0, 100);
    final hasUrl =
        item.url.trim().isNotEmpty || item.result.detectedUrl.trim().isNotEmpty;
    final hasEntity = item.displayEntity.trim().isNotEmpty;
    final reasonText = item.result.reasons.join(' ').toLowerCase();
    final behaviorRisk =
        reasonText.contains('urgent') ||
        reasonText.contains('threat') ||
        reasonText.contains('استعجال') ||
        item.result.entityConflict;
    return [
      (
        'تحليل النص',
        Icons.article_outlined,
        score <= 30
            ? 'هادئ'
            : score <= 65
            ? 'متوسط'
            : 'مرتفع',
        score <= 30
            ? AppTokens.success
            : score <= 65
            ? AppTokens.warning
            : AppTokens.danger,
      ),
      (
        'تحليل الرابط',
        hasUrl ? Icons.link_rounded : Icons.link_off_rounded,
        hasUrl ? 'تم فحصه' : 'لا يوجد رابط',
        hasUrl ? AppTokens.warning : AppTokens.neutral,
      ),
      (
        'تحليل الجهة',
        hasEntity ? Icons.apartment_rounded : Icons.domain_disabled_rounded,
        item.result.entityConflict
            ? 'تحتاج تحقق'
            : hasEntity
            ? 'مراجعة'
            : 'تعذر التحقق',
        item.result.entityConflict ? AppTokens.warning : AppTokens.brandCyan,
      ),
      (
        'تقييم السلوك',
        Icons.route_rounded,
        behaviorRisk ? 'مؤثر' : 'طبيعي',
        behaviorRisk ? AppTokens.warning : AppTokens.success,
      ),
      (
        'القرار النهائي',
        _resultIcon(item.result.finalLabel),
        '${item.result.finalScore}/100',
        TextMapper.riskColor(item.result.finalLabel),
      ),
    ];
  }

  Widget _investigationStepRow(
    BuildContext context, {
    required String label,
    required IconData icon,
    required String impact,
    required Color color,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 16, color: color),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w500,
                height: 1.35,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            impact,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  String _recommendationText(
    BuildContext context, {
    required bool isHigh,
    required bool isSafe,
  }) {
    if (isHigh) return 'لا تضغط على الرابط ولا تشارك أي رمز أو بيانات.';
    if (isSafe) return 'لا توجد مؤشرات خطيرة، ويمكنك المتابعة بحذر.';
    return 'يمكنك المتابعة بحذر بعد التحقق من الجهة والرابط.';
  }

  String _resultHeadline(
    BuildContext context, {
    required bool isHigh,
    required bool isSafe,
  }) {
    if (isHigh) {
      return context.isArabic
          ? 'نتيجة تحقيق عالية الخطورة'
          : 'High-risk investigation result';
    }
    if (isSafe) {
      return context.isArabic
          ? 'لم تظهر مؤشرات تصيد قوية'
          : 'No strong phishing indicators';
    }
    return context.isArabic
        ? 'نتيجة تحتاج تحقق قبل التصرف'
        : 'Result needs verification before acting';
  }

  String _shortResultSentence(
    BuildContext context, {
    required bool isHigh,
    required bool isSafe,
  }) {
    if (isHigh) {
      return context.isArabic
          ? 'توجد مؤشرات قوية على تصيد أو احتيال.'
          : 'Strong phishing or fraud indicators were found.';
    }
    if (isSafe) {
      return context.isArabic
          ? 'لا توجد مؤشرات خطيرة واضحة.'
          : 'No clear dangerous indicators were found.';
    }
    return context.isArabic
        ? 'تحتاج الرسالة إلى تحقق قبل التفاعل معها.'
        : 'Verify this message before interacting with it.';
  }

  int? _resultConfidencePercent(double confidence) {
    if (confidence <= 0) return null;
    final percent = confidence > 1
        ? confidence.round()
        : (confidence * 100).round();
    return percent.clamp(1, 100).toInt();
  }

  List<(String, IconData)> _resultContextChips(
    BuildContext context,
    AnalysisHistoryItem item,
  ) {
    final entity = item.displayEntity.trim().isEmpty
        ? (context.isArabic ? 'غير محددة' : 'Unspecified')
        : item.displayEntity.trim();
    final channel = item.displayChannel.trim().isEmpty
        ? (context.isArabic ? 'يدوي' : 'Manual')
        : TextMapper.channel(context, item.displayChannel);
    final hasLink =
        item.url.trim().isNotEmpty || item.result.detectedUrl.trim().isNotEmpty;
    return <(String, IconData)>[
      (
        '${context.isArabic ? 'الجهة' : 'Entity'}: $entity',
        Icons.apartment_rounded,
      ),
      (
        '${context.isArabic ? 'المصدر' : 'Source'}: $channel',
        Icons.source_rounded,
      ),
      (
        '${context.isArabic ? 'الرابط' : 'Link'}: ${hasLink ? (context.isArabic ? 'موجود' : 'Present') : (context.isArabic ? 'غير موجود' : 'Absent')}',
        hasLink ? Icons.link_rounded : Icons.link_off_rounded,
      ),
    ];
  }

  Widget _mutedBadge(BuildContext context, String label, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context).withValues(alpha: 0.58),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.48),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: AppTokens.mutedText(context)),
          const SizedBox(width: 6),
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              fontWeight: FontWeight.w800,
              height: 1.1,
            ),
          ),
        ],
      ),
    );
  }

  IconData _resultIcon(String label) {
    switch (label.toLowerCase()) {
      case 'phishing':
        return Icons.gpp_bad_rounded;
      case 'safe':
        return Icons.verified_user_rounded;
      case 'suspicious':
        return Icons.warning_amber_rounded;
      default:
        return Icons.manage_search_rounded;
    }
  }

  List<(String, IconData, Color)> _resultIndicators(
    BuildContext context,
    AnalysisHistoryItem item,
  ) {
    final haystack =
        '${item.url} ${item.rawText} ${item.result.detectedUrl} '
                '${item.result.reasons.join(' ')} '
                '${item.result.matchedSignals.map((e) => e.values.join(' ')).join(' ')}'
            .toLowerCase();
    final isHigh =
        item.result.finalLabel.toLowerCase() == 'phishing' ||
        item.result.finalScore >= 61;
    final indicators = <(String, IconData, Color)>[];

    void add(String ar, String en, IconData icon, Color color) {
      final label = context.isArabic ? ar : en;
      if (!indicators.any((item) => item.$1 == label)) {
        indicators.add((label, icon, color));
      }
    }

    if (item.url.trim().isNotEmpty ||
        item.result.detectedUrl.trim().isNotEmpty) {
      add(
        isHigh ? 'رابط خطير' : 'رابط موجود',
        isHigh ? 'Risky link' : 'Link detected',
        Icons.link_rounded,
        isHigh ? AppTokens.danger : AppTokens.warning,
      );
    }
    if (haystack.contains('password') ||
        haystack.contains('credential') ||
        haystack.contains('otp') ||
        haystack.contains('رمز') ||
        haystack.contains('كلمة مرور')) {
      add(
        'طلب بيانات حساسة',
        'Sensitive data request',
        Icons.lock_rounded,
        AppTokens.danger,
      );
    }
    if (haystack.contains('http://')) {
      add(
        'لا يستخدم HTTPS',
        'No HTTPS',
        Icons.public_off_rounded,
        AppTokens.warning,
      );
    }
    if (haystack.contains('brand') ||
        haystack.contains('imperson') ||
        haystack.contains('entity') ||
        haystack.contains('جهة')) {
      add(
        'نطاق غير موثوق',
        'Untrusted domain',
        Icons.domain_disabled_rounded,
        AppTokens.warning,
      );
    }
    if (haystack.contains('urgent') ||
        haystack.contains('threat') ||
        haystack.contains('تعليق') ||
        haystack.contains('إغلاق')) {
      add(
        'استعجال أو تهديد',
        'Urgency or threat',
        Icons.timer_rounded,
        AppTokens.warning,
      );
    }
    if (item.result.entityConflict) {
      add(
        'تعارض في الجهة',
        'Entity mismatch',
        Icons.account_tree_rounded,
        AppTokens.warning,
      );
    }
    if (indicators.isEmpty) {
      add(
        isHigh ? 'مؤشرات متعددة' : 'اكتمل التحقق',
        isHigh ? 'Multiple signals' : 'Scan complete',
        isHigh ? Icons.rule_folder_rounded : Icons.verified_rounded,
        isHigh ? AppTokens.warning : AppTokens.success,
      );
    }
    return indicators;
  }

  Widget _indicatorPill(
    BuildContext context,
    String label,
    IconData icon,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.24)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 15),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 12.5,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }

  Widget _scanningStateCard(BuildContext context) {
    return FadeSlideIn(
      beginOffset: const Offset(0, 10),
      duration: const Duration(milliseconds: 300),
      child: AnalysisScanningExperience(isUrlAnalysis: _isUrlAnalysis),
    );
  }

  // ── Compact QR section divider label ───────────────────────────────────────
  Widget _qrSectionDivider(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Divider(
            height: 1,
            color: AppTokens.outline(context).withValues(alpha: 0.28),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.qr_code_scanner_rounded,
                size: 12,
                color: AppTokens.mutedText(context),
              ),
              const SizedBox(width: 5),
              Text(
                'مسح QR',
                style: TextStyle(
                  color: AppTokens.mutedText(context),
                  fontSize: 11.5,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: Divider(
            height: 1,
            color: AppTokens.outline(context).withValues(alpha: 0.28),
          ),
        ),
      ],
    );
  }

  // ── Compact inline QR scan buttons ─────────────────────────────────────────
  Widget _buildImageInputSection(
    BuildContext context, {
    bool embedded = false,
  }) {
    final bool busy = _isLoading || _isExtractingQr;

    final scanButtons = Row(
      children: [
        Expanded(
          child: _qrActionButton(
            context,
            label: 'مسح بالكاميرا',
            icon: Icons.camera_alt_rounded,
            onTap: busy ? null : _pickImageFromCamera,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _qrActionButton(
            context,
            label: 'من المعرض',
            icon: Icons.photo_library_rounded,
            onTap: busy ? null : _pickImageFromGallery,
          ),
        ),
      ],
    );

    if (_selectedImage == null) {
      if (embedded) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _qrSectionDivider(context),
            const SizedBox(height: 10),
            scanButtons,
          ],
        );
      }
      return AppSurfaceCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _qrSectionDivider(context),
            const SizedBox(height: 10),
            scanButtons,
          ],
        ),
      );
    }

    // Image selected — thumbnail + QR status row
    final imageStatus = Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.file(
            _selectedImage!,
            width: 52,
            height: 52,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: AppTokens.surfaceAlt(context),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.image_rounded,
                color: AppTokens.mutedText(context),
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(child: _buildQrStatusColumn(context)),
        if (!busy)
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: _clearImage,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(10, 2, 0, 2),
              child: Icon(
                Icons.close_rounded,
                size: 18,
                color: AppTokens.mutedText(context),
              ),
            ),
          ),
      ],
    );

    if (embedded) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _qrSectionDivider(context),
          const SizedBox(height: 10),
          imageStatus,
        ],
      );
    }
    return AppSurfaceCard(
      padding: const EdgeInsets.all(14),
      child: imageStatus,
    );
  }

  Widget _qrActionButton(
    BuildContext context, {
    required String label,
    required IconData icon,
    VoidCallback? onTap,
  }) {
    final enabled = onTap != null;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        height: 40,
        decoration: BoxDecoration(
          color: AppTokens.surfaceAlt(
            context,
          ).withValues(alpha: enabled ? 0.65 : 0.30),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppTokens.outline(
              context,
            ).withValues(alpha: enabled ? 0.50 : 0.22),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 16,
              color: enabled
                  ? AppTokens.brandCyan
                  : AppTokens.mutedText(context),
            ),
            const SizedBox(width: 7),
            Text(
              label,
              style: TextStyle(
                color: enabled
                    ? AppTokens.textPrimary(context)
                    : AppTokens.mutedText(context),
                fontWeight: FontWeight.w800,
                fontSize: 12.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQrStatusColumn(BuildContext context) {
    if (_isExtractingQr) {
      return Row(
        children: [
          SizedBox(
            width: 13,
            height: 13,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppTokens.brandCyan,
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              _imageStatusMsg ?? 'جارٍ فحص رمز QR...',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.brandCyan,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      );
    }
    if (_qrContent != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.qr_code_rounded,
                color: AppTokens.success,
                size: 14,
              ),
              const SizedBox(width: 5),
              Text(
                'تم العثور على QR',
                style: TextStyle(
                  color: AppTokens.success,
                  fontWeight: FontWeight.w900,
                  fontSize: 12.5,
                ),
              ),
            ],
          ),
          const SizedBox(height: 3),
          Text(
            _qrContent!,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: AppTokens.brandCyan,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      );
    }
    if (_imageStatusMsg != null) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: AppTokens.warning,
            size: 14,
          ),
          const SizedBox(width: 5),
          Expanded(
            child: Text(
              _imageStatusMsg!,
              style: const TextStyle(
                color: AppTokens.warning,
                fontWeight: FontWeight.w900,
                fontSize: 12.5,
              ),
            ),
          ),
        ],
      );
    }
    return const SizedBox.shrink();
  }

  @override
  void dispose() {
    _messageController.removeListener(_handleInputChanged);
    _senderController.dispose();
    _urlController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final keyboardOpen = MediaQuery.viewInsetsOf(context).bottom > 0;
    final bottomPadding = keyboardOpen
        ? 24.0
        : AppTokens.bottomNavContentPadding;
    return AppBackground(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.fromLTRB(20, 16, 20, bottomPadding),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              FadeSlideIn(
                beginOffset: const Offset(0, 8),
                child: PageIntroHeader(
                  icon: Icons.shield_rounded,
                  title: context.l10n.analyze,
                  subtitle: context.l10n.analyzePageSubtitle,
                ),
              ),
              const SizedBox(height: 14),
              FadeSlideIn(
                delay: const Duration(milliseconds: 60),
                beginOffset: const Offset(0, 12),
                child: AnalyzeFormCard(
                  senderController: _senderController,
                  claimedEntityController: _urlController,
                  messageController: _messageController,
                  urlController: _urlController,
                  isLoading: _isLoading,
                  canAnalyze: _canAnalyze && !_inputTooLong,
                  selectedChannel: _selectedChannel,
                  onChannelChanged: (value) =>
                      setState(() => _selectedChannel = value),
                  onAnalyze: _analyzeMessage,
                  onClear: _clearAll,
                  onPasteMessage: _pasteMessageFromClipboard,
                  onPasteUrl: _pasteUrlFromClipboard,
                  imageInput: _buildImageInputSection(context, embedded: true),
                ),
              ),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 240),
                switchInCurve: Curves.easeOutCubic,
                switchOutCurve: Curves.easeInCubic,
                child: _isLoading
                    ? Padding(
                        key: const ValueKey('scanning'),
                        padding: const EdgeInsets.only(top: 14),
                        child: _scanningStateCard(context),
                      )
                    : const SizedBox.shrink(),
              ),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 280),
                switchInCurve: Curves.easeOutCubic,
                switchOutCurve: Curves.easeInCubic,
                child: _lastResult == null
                    ? const SizedBox.shrink()
                    : Padding(
                        key: ValueKey(_lastResult!.id),
                        padding: const EdgeInsets.only(top: 16),
                        child: _resultCard(context, _lastResult!),
                      ),
              ),
              if (_errorMessage != null) ...[
                const SizedBox(height: 14),
                ErrorState(
                  title: _errorTitle ?? context.l10n.analyzeFailedTitle,
                  subtitle: _errorMessage!,
                  retryLabel: context.l10n.retryLabel,
                  onRetry: (_canAnalyze && !_inputTooLong && !_isLoading)
                      ? _analyzeMessage
                      : null,
                ),
              ],
              const SizedBox(height: 36),
            ],
          ),
        ),
      ),
    );
  }
}
