import 'package:flutter/material.dart';
import '../l10n/l10n_extensions.dart';
import '../theme/app_tokens.dart';
import '../widgets/app_background.dart';
import '../widgets/app_surface_card.dart';

class OnboardingScreen extends StatefulWidget {
  final VoidCallback onFinish;
  final Locale currentLocale;
  final ValueChanged<Locale> onChangeLocale;

  const OnboardingScreen({
    super.key,
    required this.onFinish,
    required this.currentLocale,
    required this.onChangeLocale,
  });

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _index = 0;

  void _next() {
    if (_index == 2) {
      widget.onFinish();
      return;
    }

    _pageController.nextPage(
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
    );
  }

  Widget _buildLocaleChip(
    BuildContext context, {
    required String label,
    required bool selected,
    required VoidCallback onTap,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return ChoiceChip(
      label: Text(
        label,
        style: TextStyle(
          fontWeight: selected ? FontWeight.w800 : FontWeight.w700,
          color: selected
              ? (isDark ? Colors.white : const Color(0xFF2E1F74))
              : AppTokens.textPrimary(context),
        ),
      ),
      selected: selected,
      onSelected: (_) => onTap(),
      backgroundColor: isDark
          ? AppTokens.surfaceAlt(context)
          : const Color(0xFFF1F4FA),
      selectedColor: isDark
          ? AppTokens.brand.withValues(alpha: 0.28)
          : const Color(0xFFE9E3FF),
      checkmarkColor: selected
          ? (isDark ? Colors.white : const Color(0xFF2E1F74))
          : AppTokens.brand,
      side: BorderSide(
        color: selected
            ? AppTokens.brand.withValues(alpha: isDark ? 0.38 : 0.18)
            : AppTokens.outline(context),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    final pages = [
      _OnboardingPageData(
        icon: Icons.shield_rounded,
        title: l10n.onboardingTitle1,
        description: l10n.onboardingDesc1,
      ),
      _OnboardingPageData(
        icon: Icons.bolt_rounded,
        title: l10n.onboardingTitle2,
        description: l10n.onboardingDesc2,
      ),
      _OnboardingPageData(
        icon: Icons.notifications_active_rounded,
        title: l10n.onboardingTitle3,
        description: l10n.onboardingDesc3,
      ),
    ];

    return AppBackground(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Wrap(
                        spacing: 8,
                        children: [
                          _buildLocaleChip(
                            context,
                            label: l10n.arabic,
                            selected: widget.currentLocale.languageCode == 'ar',
                            onTap: () =>
                                widget.onChangeLocale(const Locale('ar')),
                          ),
                          _buildLocaleChip(
                            context,
                            label: l10n.english,
                            selected: widget.currentLocale.languageCode == 'en',
                            onTap: () =>
                                widget.onChangeLocale(const Locale('en')),
                          ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: widget.onFinish,
                      child: Text(l10n.skip),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: PageView.builder(
                    controller: _pageController,
                    itemCount: pages.length,
                    onPageChanged: (value) {
                      setState(() {
                        _index = value;
                      });
                    },
                    itemBuilder: (context, index) {
                      final page = pages[index];
                      return Center(
                        child: AppSurfaceCard(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Container(
                                width: 88,
                                height: 88,
                                decoration: BoxDecoration(
                                  gradient: LinearGradient(
                                    colors: [
                                      AppTokens.brand.withValues(alpha: 0.18),
                                      AppTokens.brandCyan.withValues(
                                        alpha: 0.14,
                                      ),
                                    ],
                                  ),
                                  borderRadius: BorderRadius.circular(28),
                                ),
                                child: Icon(
                                  page.icon,
                                  size: 42,
                                  color: AppTokens.brand,
                                ),
                              ),
                              const SizedBox(height: 24),
                              Text(
                                page.title,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.w900),
                              ),
                              const SizedBox(height: 14),
                              Text(
                                page.description,
                                textAlign: TextAlign.center,
                                style: Theme.of(context).textTheme.bodyLarge,
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(
                    pages.length,
                    (i) => AnimatedContainer(
                      duration: const Duration(milliseconds: 220),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: _index == i ? 26 : 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: _index == i
                            ? AppTokens.brand
                            : AppTokens.brand.withValues(alpha: 0.20),
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _next,
                    icon: Icon(
                      _index == pages.length - 1
                          ? Icons.check_rounded
                          : (context.isArabic
                                ? Icons.arrow_back_rounded
                                : Icons.arrow_forward_rounded),
                    ),
                    label: Text(
                      _index == pages.length - 1 ? l10n.startNow : l10n.next,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _OnboardingPageData {
  final IconData icon;
  final String title;
  final String description;

  const _OnboardingPageData({
    required this.icon,
    required this.title,
    required this.description,
  });
}
