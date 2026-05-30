import 'package:flutter/material.dart';
import '../config/app_config.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';
import '../widgets/app_soft_switch.dart';
import '../widgets/page_intro_header.dart';
import '../widgets/apg_ui.dart';

class MonitoredAppsScreen extends StatefulWidget {
  final Set<String> monitoredPackages;
  final Future<void> Function(String packageName, bool enabled) onTogglePackage;
  final Future<void> Function() onResetPackages;
  final bool notificationAccessGranted;

  const MonitoredAppsScreen({
    super.key,
    required this.monitoredPackages,
    required this.onTogglePackage,
    required this.onResetPackages,
    this.notificationAccessGranted = true,
  });

  @override
  State<MonitoredAppsScreen> createState() => _MonitoredAppsScreenState();
}

class _MonitoredAppsScreenState extends State<MonitoredAppsScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _query = '';
  late Set<String> _selectedPackages;

  @override
  void initState() {
    super.initState();
    _selectedPackages = {...widget.monitoredPackages};
    _searchController.addListener(
      () =>
          setState(() => _query = _searchController.text.trim().toLowerCase()),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _snack(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  List<MapEntry<String, String>> get _entries {
    final all = AppConfig.supportedApps.entries.toList();
    if (_query.isEmpty) return all;
    return all
        .where(
          (e) =>
              e.key.toLowerCase().contains(_query) ||
              e.value.toLowerCase().contains(_query),
        )
        .toList();
  }

  Future<void> _selectAll() async {
    for (final entry in AppConfig.supportedApps.entries) {
      await widget.onTogglePackage(entry.key, true);
      _selectedPackages.add(entry.key);
    }
    if (mounted) {
      setState(() {});
      _snack('تم تحديد كل التطبيقات');
    }
  }

  Future<void> _clearAll() async {
    for (final entry in AppConfig.supportedApps.entries) {
      await widget.onTogglePackage(entry.key, false);
      _selectedPackages.remove(entry.key);
    }
    if (mounted) {
      setState(() {});
      _snack('تم إلغاء كل التطبيقات');
    }
  }

  @override
  Widget build(BuildContext context) {
    final entries = _entries;
    return Scaffold(
      appBar: AppBar(title: const Text('التطبيقات المراقبة')),
      body: AppBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(22, 14, 22, 28),
            children: [
              const PageIntroHeader(
                icon: Icons.apps_rounded,
                title: 'التطبيقات المراقبة',
                subtitle:
                    'سيحلل APG الإشعارات الواردة من التطبيقات المحددة فقط.',
              ),
              const SizedBox(height: 16),
              if (!widget.notificationAccessGranted) ...[
                AppSurfaceCard(
                  padding: const EdgeInsets.all(14),
                  border: Border.all(
                    color: AppTokens.warning.withValues(alpha: 0.24),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.lock_rounded, color: AppTokens.warning),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'فعّل صلاحية الإشعارات أولًا حتى تعمل المراقبة.',
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: AppTokens.mutedText(context),
                                fontWeight: FontWeight.w800,
                                height: 1.45,
                              ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
              ],
              TextField(
                controller: _searchController,
                decoration: const InputDecoration(
                  hintText: 'بحث داخل التطبيقات',
                  prefixIcon: Icon(Icons.search_rounded),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _selectAll,
                      icon: const Icon(Icons.done_all_rounded),
                      label: const Text('تحديد الكل'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _clearAll,
                      icon: const Icon(Icons.clear_all_rounded),
                      label: const Text('إلغاء الكل'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (entries.isEmpty)
                EmptyState(
                  title: 'تعذر تحميل التطبيقات',
                  subtitle: 'لم يتم العثور على تطبيقات مطابقة للبحث.',
                  icon: Icons.search_off_rounded,
                )
              else
                ...entries.map(
                  (entry) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _AppTile(
                      packageName: entry.key,
                      appName: entry.value,
                      selected: _selectedPackages.contains(entry.key),
                      onChanged: (value) async {
                        await widget.onTogglePackage(entry.key, value);
                        setState(() {
                          if (value) {
                            _selectedPackages.add(entry.key);
                          } else {
                            _selectedPackages.remove(entry.key);
                          }
                        });
                        if (mounted) _snack('تم حفظ الإعداد');
                      },
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AppTile extends StatelessWidget {
  final String packageName;
  final String appName;
  final bool selected;
  final ValueChanged<bool> onChanged;

  const _AppTile({
    required this.packageName,
    required this.appName,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return AppSurfaceCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      child: Row(
        children: [
          _BrandAppIcon(packageName: packageName, appName: appName),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  appName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                    height: 1.15,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  selected ? 'المراقبة مفعلة' : 'غير مراقب',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: selected
                        ? AppTokens.success
                        : AppTokens.mutedText(context),
                    fontWeight: FontWeight.w700,
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          AppSoftSwitch(value: selected, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _BrandAppIcon extends StatelessWidget {
  final String packageName;
  final String appName;

  const _BrandAppIcon({required this.packageName, required this.appName});

  @override
  Widget build(BuildContext context) {
    final spec = _AppIconSpec.forPackage(packageName, appName);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        gradient: spec.gradient,
        color: spec.gradient == null
            ? spec.background.withValues(alpha: 0.14)
            : null,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: spec.border.withValues(alpha: 0.34)),
        boxShadow: [
          BoxShadow(
            color: spec.shadow.withValues(alpha: 0.07),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Center(
        child: spec.text != null
            ? Text(
                spec.text!,
                style: TextStyle(
                  color: spec.foreground,
                  fontWeight: FontWeight.w900,
                  fontSize: spec.text!.length > 1 ? 12 : 18,
                  letterSpacing: -0.4,
                ),
              )
            : Icon(spec.icon, color: spec.foreground, size: 22),
      ),
    );
  }
}

class _AppIconSpec {
  final IconData icon;
  final Color background;
  final Color foreground;
  final Color border;
  final Color shadow;
  final Gradient? gradient;
  final bool rounded;
  final String? text;

  const _AppIconSpec({
    required this.icon,
    required this.background,
    required this.foreground,
    required this.border,
    required this.shadow,
    this.gradient,
    this.rounded = false,
    this.text,
  });

  static _AppIconSpec forPackage(String packageName, String appName) {
    switch (packageName) {
      case 'com.whatsapp':
        return const _AppIconSpec(
          icon: Icons.call_rounded,
          background: Color(0xFF25D366),
          foreground: Colors.white,
          border: Color(0xFFB9F6D0),
          shadow: Color(0xFF25D366),
        );
      case 'org.telegram.messenger':
        return const _AppIconSpec(
          icon: Icons.send_rounded,
          background: Color(0xFF229ED9),
          foreground: Colors.white,
          border: Color(0xFFBDEBFF),
          shadow: Color(0xFF229ED9),
        );
      case 'com.google.android.gm':
        return const _AppIconSpec(
          icon: Icons.mail_rounded,
          background: Colors.white,
          foreground: Color(0xFFEA4335),
          border: Color(0xFFE5E7EB),
          shadow: Color(0xFFEA4335),
          text: 'M',
          rounded: true,
        );
      case 'com.google.android.apps.messaging':
        return const _AppIconSpec(
          icon: Icons.chat_bubble_rounded,
          background: Color(0xFF1A73E8),
          foreground: Colors.white,
          border: Color(0xFFCFE3FF),
          shadow: Color(0xFF1A73E8),
        );
      case 'com.android.mms':
        return const _AppIconSpec(
          icon: Icons.sms_rounded,
          background: Color(0xFF22C55E),
          foreground: Colors.white,
          border: Color(0xFFBBF7D0),
          shadow: Color(0xFF22C55E),
        );
      case 'com.samsung.android.messaging':
        return const _AppIconSpec(
          icon: Icons.message_rounded,
          background: Color(0xFF38BDF8),
          foreground: Colors.white,
          border: Color(0xFFBAE6FD),
          shadow: Color(0xFF38BDF8),
        );
      case 'com.facebook.orca':
        return const _AppIconSpec(
          icon: Icons.bolt_rounded,
          background: Color(0xFF0084FF),
          foreground: Colors.white,
          border: Color(0xFFCDE7FF),
          shadow: Color(0xFF0084FF),
        );
      case 'com.instagram.android':
        return const _AppIconSpec(
          icon: Icons.camera_alt_rounded,
          background: Color(0xFFE1306C),
          foreground: Colors.white,
          border: Color(0xFFFBCFE8),
          shadow: Color(0xFFE1306C),
          gradient: LinearGradient(
            colors: [
              Color(0xFFF58529),
              Color(0xFFDD2A7B),
              Color(0xFF8134AF),
              Color(0xFF515BD4),
            ],
            begin: Alignment.topRight,
            end: Alignment.bottomLeft,
          ),
          rounded: true,
        );
      default:
        return _AppIconSpec(
          icon: Icons.apps_rounded,
          background: AppTokens.brand.withValues(alpha: 0.14),
          foreground: AppTokens.brand,
          border: AppTokens.brand.withValues(alpha: 0.20),
          shadow: AppTokens.brand,
          text: appName.isNotEmpty
              ? appName.substring(0, 1).toUpperCase()
              : null,
        );
    }
  }
}
