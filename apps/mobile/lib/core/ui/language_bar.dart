import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import '../settings/settings_controller.dart';

/// Short labels of the three languages, as written in each language.
const languageLabels = {'ar': 'ع', 'fr': 'FR', 'en': 'EN'};
const _languageNames = {'ar': 'العربية', 'fr': 'Français', 'en': 'English'};

/// Rule 1 (phase A): the language can be changed from every screen. Full bar (ع · FR · EN) on the
/// first-launch screens; [LanguageMenuAction] in the other app bars.
class LanguageBar extends ConsumerWidget {
  const LanguageBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final current = ref.watch(localeCodeProvider);
    final scheme = Theme.of(context).colorScheme;
    return Container(
      key: const Key('language-bar'),
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final code in supportedLanguageCodes)
            Semantics(
              button: true,
              selected: code == current,
              label: _languageNames[code],
              excludeSemantics: true,
              child: InkWell(
                key: Key('language-$code'),
                borderRadius: BorderRadius.circular(22),
                onTap: () =>
                    ref.read(settingsProvider.notifier).setLanguage(code),
                child: Container(
                  constraints: const BoxConstraints(
                    minWidth: 48,
                    minHeight: 44,
                  ),
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                    color: code == current ? scheme.primary : null,
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: Text(
                    languageLabels[code]!,
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: code == current
                          ? scheme.onPrimary
                          : scheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Compact language switch for app bars: the current language, a menu with the three.
class LanguageMenuAction extends ConsumerWidget {
  const LanguageMenuAction({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final current = ref.watch(localeCodeProvider);
    return PopupMenuButton<String>(
      key: const Key('language-menu'),
      tooltip: l10n.languageMenuTooltip,
      initialValue: current,
      onSelected: (code) =>
          ref.read(settingsProvider.notifier).setLanguage(code),
      itemBuilder: (_) => [
        for (final code in supportedLanguageCodes)
          PopupMenuItem(
            key: Key('language-menu-$code'),
            value: code,
            child: Text(_languageNames[code]!),
          ),
      ],
      child: SizedBox(
        width: 48,
        height: 48,
        child: Center(
          child: Text(
            languageLabels[current] ?? current,
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
          ),
        ),
      ),
    );
  }
}

/// Light/dark switch (addition 6), next to the language bar.
class ThemeToggleAction extends ConsumerWidget {
  const ThemeToggleAction({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return IconButton(
      key: const Key('theme-toggle'),
      tooltip: AppLocalizations.of(context).themeToggleTooltip,
      icon: Icon(dark ? Icons.light_mode_outlined : Icons.dark_mode_outlined),
      onPressed: () => ref
          .read(settingsProvider.notifier)
          .toggleBrightness(MediaQuery.platformBrightnessOf(context)),
    );
  }
}
