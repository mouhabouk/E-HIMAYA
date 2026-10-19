import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../institution/institution_providers.dart';
import '../institution/my_institution_screen.dart';
import '../reports/reports_providers.dart';
import '../sos/sos_widgets.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final pending = ref.watch(pendingSyncCountProvider).value ?? 0;
    final orgs = ref.watch(myOrgsProvider).value ?? const <MyOrg>[];
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appTitle),
        actions: const [EmergencyNumbersAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              l10n.homeTagline,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 24),
            const Center(child: SosButton()),
            const SizedBox(height: 24),
            if (pending > 0)
              Card(
                color: theme.colorScheme.tertiaryContainer,
                child: ListTile(
                  leading: const Icon(Icons.cloud_upload_outlined),
                  title: Text(l10n.pendingSyncBanner(pending)),
                  onTap: () => context.go(Routes.reports),
                ),
              ),
            const SizedBox(height: 8),
            _HomeAction(
              key: const Key('home-new-report'),
              icon: Icons.add_alert,
              title: l10n.homeNewReport,
              subtitle: l10n.homeNewReportDesc,
              onTap: () => context.push(Routes.newReport),
            ),
            _HomeAction(
              key: const Key('home-emergency'),
              icon: Icons.phone_in_talk,
              title: l10n.emergencyTitle,
              subtitle: l10n.homeEmergencyDesc,
              onTap: () => context.push(Routes.emergency),
            ),
            _HomeAction(
              key: const Key('home-track'),
              icon: Icons.manage_search,
              title: l10n.trackTitle,
              subtitle: l10n.homeTrackDesc,
              onTap: () => context.push(Routes.track),
            ),
            if (orgs.isNotEmpty)
              _HomeAction(
                key: const Key('home-institution'),
                icon: Icons.apartment,
                title: l10n.myInstitutionTitle,
                subtitle: l10n.homeInstitutionDesc,
                onTap: () => openMyInstitution(context, orgs),
              ),
          ],
        ),
      ),
    );
  }
}

class _HomeAction extends StatelessWidget {
  const _HomeAction({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon, size: 32),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
