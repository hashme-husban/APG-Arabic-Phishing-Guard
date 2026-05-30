import 'package:flutter/material.dart';
import '../theme/app_tokens.dart';
import 'motion.dart';

class ChannelSelector extends StatelessWidget {
  final String selectedChannel;
  final ValueChanged<String> onChanged;

  const ChannelSelector({
    super.key,
    required this.selectedChannel,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppTokens.isDark(context)
            ? const Color(0xFF081E31)
            : const Color(0xFFEFF4FF),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.85),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _item(context, 'email', Icons.mail_outline_rounded, 'Email'),
          _item(context, 'sms', Icons.sms_rounded, 'SMS'),
        ],
      ),
    );
  }

  Widget _item(
    BuildContext context,
    String value,
    IconData icon,
    String label,
  ) {
    final selected = selectedChannel == value;
    return PressableScale(
      onTap: () => onChanged(value),
      pressedScale: 0.96,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 9),
        decoration: BoxDecoration(
          gradient: selected
              ? LinearGradient(
                  colors: [AppTokens.brand, AppTokens.brandAlt],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                )
              : null,
          color: selected ? null : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              selected ? Icons.check_rounded : icon,
              size: 17,
              color: selected ? Colors.white : AppTokens.mutedText(context),
            ),
            const SizedBox(width: 7),
            Text(
              label,
              style: TextStyle(
                color: selected ? Colors.white : AppTokens.textPrimary(context),
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
