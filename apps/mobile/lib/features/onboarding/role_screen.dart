import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';

/// FR-A-002: citizen or institution.
class RoleScreen extends ConsumerWidget {
  const RoleScreen({super.key});

  Future<void> _choose(
    BuildContext context,
    WidgetRef ref,
    UserRole role,
  ) async {
    await ref.read(identityProvider.notifier).chooseRole(role);
    if (!context.mounted) return;
    context.go(
      role == UserRole.citizen
          ? Routes.onboardingCitizen
          : Routes.onboardingInstitution,
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.roleTitle),
        automaticallyImplyLeading: false,
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ChoiceCard(
              key: const Key('role-citizen'),
              icon: Icons.person,
              title: l10n.roleCitizen,
              description: l10n.roleCitizenDesc,
              onTap: () => _choose(context, ref, UserRole.citizen),
            ),
            const SizedBox(height: 12),
            ChoiceCard(
              key: const Key('role-institution'),
              icon: Icons.apartment,
              title: l10n.roleInstitution,
              description: l10n.roleInstitutionDesc,
              onTap: () => _choose(context, ref, UserRole.institution),
            ),
          ],
        ),
      ),
    );
  }
}

/// Large tappable card used by the onboarding choices.
class ChoiceCard extends StatelessWidget {
  const ChoiceCard({
    super.key,
    required this.icon,
    required this.title,
    required this.description,
    required this.onTap,
    this.emphasized = false,
  });

  final IconData icon;
  final String title;
  final String description;
  final VoidCallback? onTap;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Card(
      color: emphasized ? scheme.primaryContainer : null,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 72),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(icon, size: 36, color: scheme.primary),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: theme.textTheme.titleMedium),
                      const SizedBox(height: 4),
                      Text(description, style: theme.textTheme.bodyMedium),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
