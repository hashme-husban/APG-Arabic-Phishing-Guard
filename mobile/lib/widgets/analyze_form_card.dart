import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';
import 'app_surface_card.dart';
import 'apg_ui.dart';
import 'motion.dart';

class AnalyzeFormCard extends StatefulWidget {
  final TextEditingController senderController;
  final TextEditingController claimedEntityController;
  final TextEditingController messageController;
  final TextEditingController urlController;
  final bool isLoading;
  final bool canAnalyze;
  final String selectedChannel;
  final ValueChanged<String> onChannelChanged;
  final VoidCallback onAnalyze;
  final VoidCallback onClear;
  final VoidCallback onPasteMessage;
  final VoidCallback onPasteUrl;
  final Widget? imageInput;

  const AnalyzeFormCard({
    super.key,
    required this.senderController,
    required this.claimedEntityController,
    required this.messageController,
    required this.urlController,
    required this.isLoading,
    required this.canAnalyze,
    required this.selectedChannel,
    required this.onChannelChanged,
    required this.onAnalyze,
    required this.onClear,
    required this.onPasteMessage,
    required this.onPasteUrl,
    this.imageInput,
  });

  @override
  State<AnalyzeFormCard> createState() => _AnalyzeFormCardState();
}

class _AnalyzeFormCardState extends State<AnalyzeFormCard> {
  bool _advancedOpen = false;

  bool get _hasUrl {
    final text = widget.messageController.text.trim().toLowerCase();
    return text.startsWith('http://') ||
        text.startsWith('https://') ||
        text.startsWith('www.') ||
        (text.isNotEmpty && text.contains('.') && !text.contains(' '));
  }

  String get _loadingLabel =>
      _hasUrl ? 'جاري فحص الرابط...' : 'جاري تحليل الرسالة...';

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SectionHeader(
            title: 'الصق رسالة أو رابطًا',
            subtitle: 'الصق النص أو الرابط — سيكتشف APG التهديدات تلقائيًا.',
            icon: Icons.auto_awesome_rounded,
          ),
          const SizedBox(height: 16),
          _SmartInput(
            controller: widget.messageController,
            enabled: !widget.isLoading,
            onPaste: widget.onPasteMessage,
            onClear: widget.onClear,
          ),
          if (widget.imageInput != null) ...[
            const SizedBox(height: 10),
            widget.imageInput!,
          ],
          const SizedBox(height: 10),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton.icon(
              onPressed: widget.isLoading
                  ? null
                  : () => setState(() => _advancedOpen = !_advancedOpen),
              icon: Icon(
                _advancedOpen ? Icons.expand_less_rounded : Icons.tune_rounded,
                size: 19,
              ),
              label: Text(
                _advancedOpen ? 'إخفاء الخيارات المتقدمة' : 'خيارات متقدمة',
              ),
            ),
          ),
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 240),
            sizeCurve: Curves.easeOutCubic,
            crossFadeState: _advancedOpen
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 8),
                _SourceSelector(
                  selected: widget.selectedChannel,
                  enabled: !widget.isLoading,
                  onChanged: widget.onChannelChanged,
                ),
                const SizedBox(height: 12),
                _InputField(
                  controller: widget.senderController,
                  hint: 'المصدر أو المرسل (اختياري)',
                  icon: Icons.person_rounded,
                  enabled: !widget.isLoading,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            label: widget.isLoading ? _loadingLabel : 'تحليل الآن',
            icon: Icons.shield_rounded,
            loading: widget.isLoading,
            onPressed: widget.canAnalyze && !widget.isLoading
                ? widget.onAnalyze
                : null,
          ),
          if (!widget.canAnalyze && !widget.isLoading) ...[
            const SizedBox(height: 8),
            Text(
              'أدخل نص الرسالة أو الرابط لبدء التحليل.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: AppTokens.mutedText(context),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SmartInput extends StatefulWidget {
  final TextEditingController controller;
  final bool enabled;
  final VoidCallback onPaste;
  final VoidCallback onClear;

  const _SmartInput({
    required this.controller,
    required this.enabled,
    required this.onPaste,
    required this.onClear,
  });

  @override
  State<_SmartInput> createState() => _SmartInputState();
}

class _SmartInputState extends State<_SmartInput> {
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(_handleFocusChanged);
  }

  void _handleFocusChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _focusNode.removeListener(_handleFocusChanged);
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final compactHeight = MediaQuery.sizeOf(context).height < 720;
    final inputMinLines = compactHeight ? 5 : 7;
    final inputMaxLines = compactHeight ? 7 : 10;
    final focused = _focusNode.hasFocus;
    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(22),
      borderSide: BorderSide(
        color: AppTokens.outline(context).withValues(alpha: 0.82),
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 210),
          curve: Curves.easeOutCubic,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            boxShadow: focused
                ? [
                    BoxShadow(
                      color: AppTokens.brand.withValues(alpha: 0.15),
                      blurRadius: 18,
                      offset: const Offset(0, 8),
                    ),
                  ]
                : null,
          ),
          child: TextField(
            focusNode: _focusNode,
            controller: widget.controller,
            enabled: widget.enabled,
            minLines: inputMinLines,
            maxLines: inputMaxLines,
            maxLength: 1000,
            textAlign: TextAlign.right,
            textAlignVertical: TextAlignVertical.top,
            textDirection: TextDirection.rtl,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(
              hintText: 'الصق الرسالة أو الرابط هنا...',
              hintTextDirection: TextDirection.rtl,
              alignLabelWithHint: true,
              contentPadding: EdgeInsets.fromLTRB(
                16,
                compactHeight ? 14 : 18,
                16,
                compactHeight ? 14 : 18,
              ),
              filled: true,
              fillColor: AppTokens.surfaceAlt(
                context,
              ).withValues(alpha: widget.enabled ? 0.72 : 0.48),
              enabledBorder: border,
              disabledBorder: border.copyWith(
                borderSide: BorderSide(
                  color: AppTokens.outline(context).withValues(alpha: 0.45),
                ),
              ),
              focusedBorder: border.copyWith(
                borderSide: BorderSide(
                  color: AppTokens.brand.withValues(alpha: 0.90),
                  width: 1.5,
                ),
              ),
              errorBorder: border.copyWith(
                borderSide: const BorderSide(
                  color: AppTokens.danger,
                  width: 1.2,
                ),
              ),
              focusedErrorBorder: border.copyWith(
                borderSide: const BorderSide(
                  color: AppTokens.danger,
                  width: 1.4,
                ),
              ),
              counterStyle: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTokens.mutedText(context),
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _SmallButton(
                label: 'لصق من الحافظة',
                icon: Icons.content_paste_rounded,
                onTap: widget.enabled ? widget.onPaste : null,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _SmallButton(
                label: 'مسح',
                icon: Icons.refresh_rounded,
                onTap: widget.enabled ? widget.onClear : null,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _SourceSelector extends StatelessWidget {
  final String selected;
  final bool enabled;
  final ValueChanged<String> onChanged;

  const _SourceSelector({
    required this.selected,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final options = const [
      ('unknown', 'تعذر التحقق'),
      ('sms', 'SMS'),
      ('whatsapp', 'WhatsApp'),
      ('email', 'Email'),
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: options.map((option) {
        final isSelected = selected == option.$1;
        return ChoiceChip(
          label: Text(option.$2),
          selected: isSelected,
          onSelected: enabled ? (_) => onChanged(option.$1) : null,
        );
      }).toList(),
    );
  }
}

class _SmallButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback? onTap;
  const _SmallButton({
    required this.label,
    required this.icon,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) => PressableScale(
    onTap: onTap,
    child: SizedBox(
      height: 42,
      child: OutlinedButton.icon(
        onPressed: null,
        icon: Icon(icon, size: 17),
        label: Text(label, overflow: TextOverflow.ellipsis),
        style: OutlinedButton.styleFrom(
          foregroundColor: onTap == null
              ? AppTokens.mutedText(context)
              : AppTokens.brandCyan,
          disabledForegroundColor: onTap == null
              ? AppTokens.mutedText(context)
              : AppTokens.brandCyan,
          side: BorderSide(
            color: AppTokens.brandCyan.withValues(
              alpha: onTap == null ? 0.10 : 0.20,
            ),
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(15),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
    ),
  );
}

class _InputField extends StatelessWidget {
  final TextEditingController controller;
  final String hint;
  final IconData icon;
  final bool enabled;
  const _InputField({
    required this.controller,
    required this.hint,
    required this.icon,
    required this.enabled,
  });
  @override
  Widget build(BuildContext context) => TextField(
    controller: controller,
    enabled: enabled,
    textAlign: TextAlign.right,
    textDirection: TextDirection.rtl,
    decoration: InputDecoration(
      hintText: hint,
      prefixIcon: Padding(
        padding: const EdgeInsetsDirectional.only(start: 8),
        child: Icon(icon, size: 20),
      ),
    ),
  );
}
