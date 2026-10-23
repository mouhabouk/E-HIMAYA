import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/settings/settings_controller.dart';
import '../../core/ui/brand.dart';
import '../../l10n/app_localizations.dart';
import 'welcome_controller.dart';
import 'welcome_scaffold.dart';

const _names = {'ar': 'العربية', 'fr': 'Français', 'en': 'English'};

/// First screen ever shown: the language, before anything else (addition 7).
class LanguageScreen extends ConsumerWidget {
  const LanguageScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final current = ref.watch(localeCodeProvider);
    return WelcomeScaffold(
      bottom: FilledButton(
        key: const Key('language-continue'),
        onPressed: () => ref.read(welcomeProvider.notifier).languageChosen(),
        child: Text(l10n.actionContinue),
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Center(child: BrandLogo(size: 120)),
          const SizedBox(height: 16),
          Text(
            l10n.appTitle,
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 24),
          Semantics(
            header: true,
            child: Text(
              l10n.languageTitle,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleLarge,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.languageSubtitle,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          RadioGroup<String>(
            groupValue: current,
            onChanged: (code) {
              if (code != null) {
                ref.read(settingsProvider.notifier).setLanguage(code);
              }
            },
            child: Column(
              children: [
                for (final code in supportedLanguageCodes)
                  Card(
                    child: RadioListTile<String>(
                      key: Key('language-choice-$code'),
                      value: code,
                      title: Text(
                        _names[code]!,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
