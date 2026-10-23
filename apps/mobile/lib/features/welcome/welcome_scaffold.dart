import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/emergency_action.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';

/// Frame of the first-launch screens (addition 7): language bar and light/dark switch on top,
/// "Call 198" always visible, whatever step the person is at.
class WelcomeScaffold extends ConsumerWidget {
  const WelcomeScaffold({
    super.key,
    required this.body,
    this.title,
    this.bottom,
    this.showBack = false,
  });

  final Widget body;
  final String? title;

  /// Buttons of the step (Continue, Accept…), above the call-198 button.
  final Widget? bottom;
  final bool showBack;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final civil = emergencyNumbers.first;
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: showBack,
        title: title == null ? null : Text(title!),
        actions: const [
          ThemeToggleAction(),
          LanguageBar(),
          EmergencyNumbersAction(),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: body),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ?bottom,
                  if (bottom != null) const SizedBox(height: 8),
                  OutlinedButton.icon(
                    key: const Key('welcome-call-198'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: sosRed,
                      side: const BorderSide(color: sosRed, width: 1.5),
                    ),
                    onPressed: () => ref.read(dialerProvider)(civil.telUri),
                    icon: const Icon(Icons.phone),
                    label: Text(l10n.call198),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
