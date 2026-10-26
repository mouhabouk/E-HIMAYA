import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/brand.dart';
import '../../core/ui/components.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/theme.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alerts_providers.dart';
import '../alerts/notifications_screen.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import '../institution/my_institution_screen.dart';
import '../quota/quota_widgets.dart';
import '../reports/reports_providers.dart';
import '../sos/sos_widgets.dart';
import '../weather/weather_card.dart';
import 'location_strip.dart';

/// Home (phase A, addition 9): SOS and "report an incident" first, the four emergency numbers
/// (a tap opens the dialler, never an automatic call), shortcuts, weather, and a fixed
/// "Call 198 / SOS message" bar.
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
    final shortcuts = <_Shortcut>[
      _Shortcut(
        const Key('home-my-reports'),
        Icons.description_rounded,
        l10n.homeMyReports,
        Tone.navy,
        () => context.go(Routes.reports),
      ),
      _Shortcut(
        const Key('home-track'),
        Icons.manage_search_rounded,
        l10n.trackTitle,
        Tone.purple,
        () => context.push(Routes.track),
      ),
      // FR-A-031: the Live button, independent of the SOS and of the report form.
      _Shortcut(
        const Key('home-live'),
        Icons.videocam_rounded,
        l10n.homeLive,
        Tone.red,
        () => context.push(Routes.live),
      ),
      _Shortcut(
        const Key('home-tips'),
        Icons.health_and_safety_rounded,
        l10n.tipsTitle,
        Tone.green,
        () => context.push(Routes.tips),
      ),
      _Shortcut(
        const Key('home-alerts'),
        Icons.campaign_rounded,
        l10n.notificationsTitle,
        Tone.sky,
        () => context.push(Routes.notifications),
      ),
      if (identity.isRegistered && identity.role == UserRole.citizen)
        _Shortcut(
          const Key('home-volunteer'),
          Icons.volunteer_activism_rounded,
          l10n.volunteerTitle,
          Tone.teal,
          () => context.push(Routes.volunteer),
        ),
      // FR-A-072: anonymous citizens see why they earn no points.
      if (identity.role == UserRole.citizen)
        _Shortcut(
          const Key('home-rewards'),
          Icons.military_tech_rounded,
          l10n.rewardsTitle,
          Tone.pink,
          () => context.push(Routes.rewards),
        ),
      if (orgs.isNotEmpty)
        _Shortcut(
          const Key('home-institution'),
          Icons.apartment_rounded,
          l10n.myInstitutionTitle,
          Tone.amber,
          () => openMyInstitution(context, orgs),
        ),
    ];
    final largeText = MediaQuery.textScalerOf(context).scale(10) > 15;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 8,
        // Accessibility: at large text sizes the actions leave little room, so the logo yields
        // its place to the app's name.
        title: LayoutBuilder(
          builder: (context, box) => Row(
            children: [
              if (box.maxWidth >= 120) ...[
                const BrandLogo(size: 36),
                const SizedBox(width: 8),
              ],
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      l10n.appTitle,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    // Accessibility: at large text sizes the subtitle no longer fits the
                    // toolbar height, so only the title is kept.
                    if (MediaQuery.textScalerOf(context).scale(10) <= 13)
                      Text(
                        l10n.homeSubtitle,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.bodySmall,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          // Accessibility: at large text sizes the theme and language switches stay in the
          // settings, so the app's name keeps room to be read.
          if (!largeText) ...[const ThemeToggleAction(), const LanguageBar()],
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
        ],
      ),
      bottomNavigationBar: const _CallBar(),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const HighAlertsBanner(),
            const LocationStrip(),
            const SizedBox(height: 12),
            const Center(child: SosButton()),
            const SizedBox(height: 16),
            _ReportCard(
              title: l10n.homeReportCardTitle,
              subtitle: l10n.homeReportCardDesc,
              onTap: () => context.push(Routes.newReport),
            ),
            const SizedBox(height: 12),
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
            _SectionTitle(
              key: const Key('home-emergency'),
              title: l10n.emergencyTitle,
              trailing: l10n.homeNumbersOffline,
              onTap: () => context.push(Routes.emergency),
            ),
            const _NumbersGrid(),
            const SizedBox(height: 16),
            _SectionTitle(title: l10n.homeShortcuts),
            TileGrid(
              minTileWidth: 104,
              children: [for (final s in shortcuts) _ShortcutTile(s)],
            ),
            const SizedBox(height: 16),
            // FR-A-034: below the emergency actions, which stay first on screen.
            const WeatherCard(),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    super.key,
    required this.title,
    this.trailing,
    this.onTap,
  });

  final String title;
  final String? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: Row(
          children: [
            Expanded(
              child: Semantics(
                header: true,
                child: Text(
                  title,
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
            if (trailing != null)
              Flexible(
                child: Text(
                  trailing!,
                  textAlign: TextAlign.end,
                  style: theme.textTheme.bodySmall,
                ),
              ),
            if (onTap != null) const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}

/// Lays out tiles in equal columns: as many as fit [minTileWidth] (fewer with large text).
class _ReportCard extends StatelessWidget {
  const _ReportCard({
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      key: const Key('home-new-report'),
      borderRadius: BorderRadius.circular(20),
      clipBehavior: Clip.antiAlias,
      color: sosRed,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              const CircleAvatar(
                radius: 28,
                backgroundColor: Color(0x33FFFFFF),
                child: Icon(Icons.priority_high, color: Colors.white, size: 32),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The four emergency numbers as square buttons; 198 (Civil Protection) highlighted.
class _NumbersGrid extends ConsumerWidget {
  const _NumbersGrid();

  static const _tones = {
    EmergencyService.civilProtection: Tone.orange,
    EmergencyService.samu: Tone.red,
    EmergencyService.police: Tone.navy,
    EmergencyService.nationalGuard: Tone.green,
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final dial = ref.watch(dialerProvider);
    return TileGrid(
      minTileWidth: 76,
      children: [
        for (final n in emergencyNumbers)
          Semantics(
            button: true,
            label: l10n.emergencyCallSemantics(n.label(l10n), n.number),
            excludeSemantics: true,
            child: AppCard(
              key: Key('home-dial-${n.number}'),
              onTap: () => dial(n.telUri),
              borderColor: n.service == EmergencyService.civilProtection
                  ? _tones[n.service]!.colors(context).fill
                  : null,
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
              child: Column(
                children: [
                  if (n.service == EmergencyService.civilProtection)
                    const BrandLogo(size: 40)
                  else
                    IconTile(
                      n.icon,
                      tone: _tones[n.service]!,
                      soft: true,
                      size: 40,
                    ),
                  const SizedBox(height: 6),
                  Text(
                    n.number,
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      // The darker shade reads at AA on the card in both brightnesses.
                      color: _tones[n.service]!.colors(context).onTint,
                    ),
                  ),
                  Text(
                    n.label(l10n),
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    style: theme.textTheme.labelSmall,
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _Shortcut {
  const _Shortcut(this.key, this.icon, this.label, this.tone, this.onTap);
  final Key key;
  final IconData icon;
  final String label;
  final Tone tone;
  final VoidCallback onTap;
}

class _ShortcutTile extends StatelessWidget {
  const _ShortcutTile(this.shortcut);

  final _Shortcut shortcut;

  @override
  Widget build(BuildContext context) => ChoiceTile(
    key: shortcut.key,
    icon: shortcut.icon,
    tone: shortcut.tone,
    title: shortcut.label,
    onTap: shortcut.onTap,
  );
}

/// Fixed bar above the navigation: call 198, or send the SOS message to the user's contacts.
class _CallBar extends ConsumerWidget {
  const _CallBar();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final civil = emergencyNumbers.first;
    return BottomActionBar(
      actions: [
        BarAction(
          key: const Key('home-call-198'),
          label: l10n.homeCall198,
          icon: Icons.phone_rounded,
          tone: Tone.red,
          onPressed: () => ref.read(dialerProvider)(civil.telUri),
        ),
        // Phase B2 (addition 5): the SOS message to the user's own contacts. The
        // Civil Protection SOS stays on the big button above.
        BarAction(
          key: const Key('home-sos-message'),
          label: l10n.homeSosMessage,
          icon: Icons.sms_rounded,
          tone: Tone.navy,
          onPressed: () => context.push(Routes.safetySend),
        ),
      ],
    );
  }
}
