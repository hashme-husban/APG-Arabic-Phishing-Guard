import 'package:flutter/material.dart';

import '../l10n/l10n_extensions.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/app_soft_switch.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/apg_ui.dart';
import '../widgets/motion.dart';
import '../widgets/page_intro_header.dart';

class SettingsScreen extends StatelessWidget {
  final bool isDarkMode;
  final ValueChanged<bool> onToggleDarkMode;
  final Locale currentLocale;
  final ValueChanged<Locale> onChangeLocale;
  final String accentThemeKey;
  final ValueChanged<String> onChangeAccentTheme;

  final bool saveHistoryEnabled;
  final ValueChanged<bool> onToggleSaveHistory;
  final bool autoAnalyzeNotifications;
  final Future<void> Function(bool) onToggleAutoAnalyzeNotifications;
  final int historyCount;
  final Future<void> Function() onClearAllHistory;

  final bool notificationAccessGranted;
  final Future<void> Function() onRequestNotificationAccess;
  final int notificationCount;
  final Future<void> Function() onClearAllNotifications;
  final Set<String> monitoredPackages;
  final Future<void> Function(String packageName, bool enabled)
  onToggleMonitoredPackage;
  final Future<void> Function() onResetMonitoredPackages;

  final bool serverConnected;
  final bool isCheckingServer;
  final String serverAddress;
  final Future<void> Function() onRefreshServerConnection;
  final Future<void> Function() onLogout;

  const SettingsScreen({
    super.key,
    required this.isDarkMode,
    required this.onToggleDarkMode,
    required this.currentLocale,
    required this.onChangeLocale,
    required this.accentThemeKey,
    required this.onChangeAccentTheme,
    required this.saveHistoryEnabled,
    required this.onToggleSaveHistory,
    required this.autoAnalyzeNotifications,
    required this.onToggleAutoAnalyzeNotifications,
    required this.historyCount,
    required this.onClearAllHistory,
    required this.notificationAccessGranted,
    required this.onRequestNotificationAccess,
    required this.notificationCount,
    required this.onClearAllNotifications,
    required this.monitoredPackages,
    required this.onToggleMonitoredPackage,
    required this.onResetMonitoredPackages,
    required this.serverConnected,
    required this.isCheckingServer,
    required this.serverAddress,
    required this.onRefreshServerConnection,
    required this.onLogout,
  });

  void _snack(BuildContext context, String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _confirmLogout(BuildContext context) async {
    final l10n = context.l10n;
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(l10n.confirmLogoutTitle),
            content: Text(l10n.confirmLogoutMessage),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(l10n.cancel),
              ),
              TextButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(l10n.logoutLabel),
              ),
            ],
          ),
        ) ??
        false;
    if (confirmed) await onLogout();
  }

  Future<void> _confirmClearHistory(BuildContext context) async {
    final l10n = context.l10n;
    final confirmed =
        await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(l10n.confirmClearHistoryTitle),
            content: Text(
              historyCount == 0
                  ? l10n.confirmClearHistoryEmpty
                  : l10n.confirmClearAllPrompt,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(l10n.cancel),
              ),
              FilledButton(
                onPressed: historyCount == 0
                    ? null
                    : () => Navigator.pop(ctx, true),
                child: Text(l10n.clearHistoryLabel),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed || historyCount == 0) return;
    await onClearAllHistory();
    if (context.mounted) _snack(context, l10n.historyClearedSnack);
  }

  Widget _section(
    BuildContext context, {
    required String title,
    required IconData icon,
    required List<Widget> children,
  }) {
    return AppSurfaceCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(title: title, icon: icon),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }

  Widget _tileText(
    BuildContext context, {
    required String title,
    required String subtitle,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(
            context,
          ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 3),
        Text(
          subtitle,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: AppTokens.mutedText(context),
            height: 1.45,
          ),
        ),
      ],
    );
  }

  Widget _tileShell({
    required BuildContext context,
    required IconData icon,
    required Color iconColor,
    required Widget child,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context).withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.62),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: iconColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: iconColor, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(child: child),
        ],
      ),
    );
  }

  Widget _switchTile({
    required BuildContext context,
    required String title,
    required String subtitle,
    required IconData icon,
    required bool value,
    required ValueChanged<bool>? onChanged,
  }) {
    return _tileShell(
      context: context,
      icon: icon,
      iconColor: value ? AppTokens.brandCyan : AppTokens.mutedText(context),
      child: Row(
        children: [
          Expanded(
            child: _tileText(context, title: title, subtitle: subtitle),
          ),
          const SizedBox(width: 10),
          AppSoftSwitch(value: value, onChanged: onChanged),
        ],
      ),
    );
  }

  Widget _appearanceSection(BuildContext context) {
    final l10n = context.l10n;
    return _section(
      context,
      title: l10n.appearanceAndLanguage,
      icon: Icons.palette_rounded,
      children: [
        _switchTile(
          context: context,
          title: l10n.darkMode,
          subtitle: l10n.darkModeSubtitle,
          icon: Icons.dark_mode_rounded,
          value: isDarkMode,
          onChanged: (value) {
            onToggleDarkMode(value);
            _snack(context, l10n.settingsUpdated);
          },
        ),
        _languageTile(context),
        _accentColorCard(context),
      ],
    );
  }

  Widget _languageTile(BuildContext context) {
    final l10n = context.l10n;
    final isAr = currentLocale.languageCode == 'ar';
    return _tileShell(
      context: context,
      icon: Icons.language_rounded,
      iconColor: AppTokens.brandCyan,
      child: Row(
        children: [
          Expanded(
            child: Text(
              l10n.language,
              style: Theme.of(
                context,
              ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
          ),
          SegmentedButton<String>(
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: 'en', label: Text('English')),
              ButtonSegment(value: 'ar', label: Text('العربية')),
            ],
            selected: {isAr ? 'ar' : 'en'},
            onSelectionChanged: (value) {
              onChangeLocale(Locale(value.first));
              _snack(context, l10n.languageUpdated);
            },
          ),
        ],
      ),
    );
  }

  Widget _accentColorCard(BuildContext context) {
    final l10n = context.l10n;
    final selectedTheme = AppTokens.accentThemes.firstWhere(
      (t) => t.key == accentThemeKey,
      orElse: () => AppTokens.accentThemes.first,
    );
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTokens.surfaceAlt(context).withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: AppTokens.outline(context).withValues(alpha: 0.62),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTokens.brand.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  Icons.color_lens_rounded,
                  color: AppTokens.brand,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _tileText(
                  context,
                  title: l10n.accentColorTitle,
                  subtitle: l10n.accentColorSubtitle,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: selectedTheme.primary.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: selectedTheme.primary.withValues(alpha: 0.42),
                  ),
                ),
                child: Text(
                  selectedTheme.label,
                  style: TextStyle(
                    color: selectedTheme.primary,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: AppTokens.accentThemes.map((theme) {
              final isSelected = theme.key == accentThemeKey;
              return GestureDetector(
                onTap: () {
                  onChangeAccentTheme(theme.key);
                  _snack(context, l10n.accentColorChanged);
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: theme.primary,
                    border: Border.all(
                      color: isSelected ? Colors.white : Colors.transparent,
                      width: 2.5,
                    ),
                  ),
                  child: isSelected
                      ? const Icon(
                          Icons.check_rounded,
                          size: 19,
                          color: Colors.white,
                        )
                      : null,
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _storageSection(BuildContext context) {
    final l10n = context.l10n;
    return _section(
      context,
      title: l10n.storageSection,
      icon: Icons.storage_rounded,
      children: [
        _switchTile(
          context: context,
          title: l10n.saveHistory,
          subtitle: l10n.saveHistorySubtitleLocal(historyCount),
          icon: Icons.history_rounded,
          value: saveHistoryEnabled,
          onChanged: (value) {
            onToggleSaveHistory(value);
            _snack(context, l10n.settingsUpdated);
          },
        ),
        OutlinedButton.icon(
          onPressed: () => _confirmClearHistory(context),
          icon: const Icon(Icons.delete_sweep_rounded),
          label: Text(l10n.clearHistoryLabel),
        ),
      ],
    );
  }

  Widget _aboutSection(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
      child: Column(
        children: [
          Image.asset(
            'assets/branding/apg_logo_transparent.png',
            height: 72,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
          ),
          const SizedBox(height: 14),
          Text(
            'Advanced Phishing Guard',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              letterSpacing: 0.4,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          Text(
            'APG • v1.0.0',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              letterSpacing: 0.8,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            'Built by Hashem & Ruba',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: AppTokens.mutedText(context),
              height: 1.4,
              fontWeight: FontWeight.w700,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return AppBackground(
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            22,
            14,
            22,
            AppTokens.bottomNavContentPadding,
          ),
          children: [
            FadeSlideIn(
              beginOffset: const Offset(0, 8),
              child: PageIntroHeader(
                icon: Icons.settings_rounded,
                title: l10n.settingsPageTitle,
                subtitle: l10n.settingsPageSubtitle,
              ),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 40),
              child: _appearanceSection(context),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 80),
              child: _storageSection(context),
            ),
            const SizedBox(height: 16),
            FadeSlideIn(
              delay: const Duration(milliseconds: 120),
              child: _aboutSection(context),
            ),
            const SizedBox(height: 20),
            FadeSlideIn(
              delay: const Duration(milliseconds: 280),
              beginOffset: const Offset(0, 8),
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTokens.danger,
                  side: BorderSide(
                    color: AppTokens.danger.withValues(alpha: 0.45),
                  ),
                ),
                onPressed: () => _confirmLogout(context),
                icon: const Icon(Icons.logout_rounded),
                label: Text(l10n.logoutLabel),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
