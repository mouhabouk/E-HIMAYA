import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/directional_icons.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'login_actions.dart';
import 'role_screen.dart';

/// FR-A-003: anonymous, or account (registration / login).
class CitizenModeScreen extends ConsumerStatefulWidget {
  const CitizenModeScreen({super.key});

  @override
  ConsumerState<CitizenModeScreen> createState() => _CitizenModeScreenState();
}

class _CitizenModeScreenState extends ConsumerState<CitizenModeScreen> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.citizenModeTitle),
        leading: BackButton(onPressed: () => context.go(Routes.onboarding)),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: AbsorbPointer(
          absorbing: _busy,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_busy) const LinearProgressIndicator(),
              ChoiceCard(
                key: const Key('mode-anonymous'),
                icon: Icons.visibility_off,
                title: l10n.citizenAnonymous,
                description: l10n.citizenAnonymousDesc,
                emphasized: true,
                onTap: () => _run(
                  () => ref.read(identityProvider.notifier).useAnonymous(),
                ),
              ),
              const SizedBox(height: 12),
              ChoiceCard(
                key: const Key('mode-register'),
                icon: Icons.person_add,
                title: l10n.citizenRegister,
                description: l10n.citizenRegisterDesc,
                onTap: () => _run(() => runLogin(context, ref, register: true)),
              ),
              const SizedBox(height: 12),
              ChoiceCard(
                key: const Key('mode-login'),
                icon: DirectionalIcons.login,
                title: l10n.citizenLogin,
                description: l10n.citizenLoginDesc,
                onTap: () => _run(() => runLogin(context, ref)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
