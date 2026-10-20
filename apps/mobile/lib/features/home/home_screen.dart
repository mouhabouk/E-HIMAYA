import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alerts_providers.dart';
import '../alerts/notifications_screen.dart';
import '../institution/institution_providers.dart';
import '../institution/my_institution_screen.dart';
import '../quota/quota_widgets.dart';
import '../reports/reports_providers.dart';
import '../sos/sos_widgets.dart';
import '../weather/weather_card.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final pending = ref.watch(pendingSyncCountProvider).value ?? 0;
    final orgs = ref.watch(myOrgsProvider).value ?? const <MyOrg>[];
    final identity = ref.watch(identityProvider);
    final alertsCount = ref.watch(currentAlertsProvider).length;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.appTitle),
        actions: [
          IconButton(
            key: const Key('home-notifications'),
            tooltip: l10n.notificationsTitle,
            onPressed: () => context.push(Routes.notifications),
            icon: Badge(
              isLabelVisible: alertsCount > 0,
              label: Text('$alertsCount'),
              child: const Icon(Icons.notifications_outlined),
            ),
          ),
          const EmergencyNumbersAction(),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const HighAlertsBanner(),
            Text(
              l10n.homeTagline,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 24),
            const Center(child: SosButton()),
            const SizedBox(height: 16),
            // FR-A-031: the Live button, independent of the SOS and of the report form.
            OutlinedButton.icon(
              key: const Key('home-live'),
              style: OutlinedButton.styleFrom(
                foregroundColor: sosRed,
                side: const BorderSide(color: sosRed, width: 2),
                minimumSize: const Size.fromHeight(56),
                textStyle: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              onPressed: () => context.push(Routes.live),
              icon: const Icon(Icons.videocam),
              label: Text(l10n.homeLive),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                l10n.homeLiveDesc,
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ),
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
            // Phase 9 §3: reports left without an account (anonymous only).
            const AnonQuotaCard(),
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
            _HomeAction(
              key: const Key('home-tips'),
              icon: Icons.health_and_safety,
              title: l10n.tipsTitle,
              subtitle: l10n.homeTipsDesc,
              onTap: () => context.push(Routes.tips),
            ),
            if (identity.isRegistered && identity.role == UserRole.citizen)
              _HomeAction(
                key: const Key('home-volunteer'),
                icon: Icons.volunteer_activism,
                title: l10n.volunteerTitle,
                subtitle: l10n.homeVolunteerDesc,
                onTap: () => context.push(Routes.volunteer),
              ),
            // FR-A-072: anonymous citizens see why they earn no points.
            if (identity.role == UserRole.citizen)
              _HomeAction(
                key: const Key('home-rewards'),
                icon: Icons.military_tech,
                title: l10n.rewardsTitle,
                subtitle: l10n.homeRewardsDesc,
                onTap: () => context.push(Routes.rewards),
              ),
            if (orgs.isNotEmpty)
              _HomeAction(
                key: const Key('home-institution'),
                icon: Icons.apartment,
                title: l10n.myInstitutionTitle,
                subtitle: l10n.homeInstitutionDesc,
                onTap: () => openMyInstitution(context, orgs),
              ),
            const SizedBox(height: 8),
            // FR-A-034: below the emergency actions, which stay first on screen.
            const WeatherCard(),
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
