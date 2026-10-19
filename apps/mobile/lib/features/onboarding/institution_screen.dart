import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_router.dart';
import '../../core/ui/directional_icons.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'login_actions.dart';

/// FR-A-002: institutions must register through the institutions portal (phase 4); the app
/// only offers login for accounts that already exist.
class InstitutionScreen extends ConsumerStatefulWidget {
  const InstitutionScreen({super.key});

  @override
  ConsumerState<InstitutionScreen> createState() => _InstitutionScreenState();
}

class _InstitutionScreenState extends ConsumerState<InstitutionScreen> {
  bool _busy = false;

  Future<void> _login() async {
    setState(() => _busy = true);
    await runLogin(context, ref);
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.institutionTitle),
        leading: BackButton(onPressed: () => context.go(Routes.onboarding)),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Icon(Icons.apartment, size: 56, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text(l10n.institutionBody, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 24),
            FilledButton.icon(
              key: const Key('institution-login'),
              onPressed: _busy ? null : _login,
              icon: const Icon(DirectionalIcons.login),
              label: Text(l10n.institutionLogin),
            ),
          ],
        ),
      ),
    );
  }
}
