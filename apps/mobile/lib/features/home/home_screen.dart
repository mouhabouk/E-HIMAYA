import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/brand.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/theme.dart';
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
        Icons.description_outlined,
        l10n.homeMyReports,
        () => context.go(Routes.reports),
      ),
      _Shortcut(
        const Key('home-track'),
        Icons.manage_search,
        l10n.trackTitle,
        () => context.push(Routes.track),
      ),
      // FR-A-031: the Live button, independent of the SOS and of the report form.
      _Shortcut(
        const Key('home-live'),
        Icons.videocam,
        l10n.homeLive,
        () => context.push(Routes.live),
        color: sosRed,
      ),
      _Shortcut(
        const Key('home-tips'),
        Icons.health_and_safety,
        l10n.tipsTitle,
        () => context.push(Routes.tips),
      ),
      _Shortcut(
        const Key('home-alerts'),
        Icons.campaign_outlined,
        l10n.notificationsTitle,
        () => context.push(Routes.notifications),
      ),
      if (identity.isRegistered && identity.role == UserRole.citizen)
        _Shortcut(
          const Key('home-volunteer'),
          Icons.volunteer_activism,
          l10n.volunteerTitle,
          () => context.push(Routes.volunteer),
        ),
      // FR-A-072: anonymous citizens see why they earn no points.
      if (identity.role == UserRole.citizen)
        _Shortcut(
          const Key('home-rewards'),
          Icons.military_tech,
          l10n.rewardsTitle,
          () => context.push(Routes.rewards),
        ),
      if (orgs.isNotEmpty)
        _Shortcut(
          const Key('home-institution'),
          Icons.apartment,
          l10n.myInstitutionTitle,
          () => openMyInstitution(context, orgs),
        ),
    ];
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 8,
        title: Row(
          children: [
            const BrandLogo(size: 36),
            const SizedBox(width: 8),
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
        actions: [
          const ThemeToggleAction(),
          const LanguageBar(),
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
            _TileGrid(
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
class _TileGrid extends StatelessWidget {
  const _TileGrid({required this.children, required this.minTileWidth});

  final List<Widget> children;
  final double minTileWidth;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      const gap = 8.0;
      final scale = MediaQuery.textScalerOf(context).scale(1);
      final min = minTileWidth * (scale > 1.3 ? scale * 0.8 : 1);
      final columns = ((constraints.maxWidth + gap) / (min + gap))
          .floor()
          .clamp(1, children.length.clamp(1, 4));
      final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
      return Wrap(
        spacing: gap,
        runSpacing: gap,
        children: [
          for (final child in children) SizedBox(width: width, child: child),
        ],
      );
    },
  );
}

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

  static const _colors = {
    EmergencyService.civilProtection: BrandColors.orange,
    EmergencyService.samu: BrandColors.red,
    EmergencyService.police: BrandColors.blue,
    EmergencyService.nationalGuard: BrandColors.green,
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final dark = theme.brightness == Brightness.dark;
    final dial = ref.watch(dialerProvider);
    return _TileGrid(
      minTileWidth: 76,
      children: [
        for (final n in emergencyNumbers)
          Semantics(
            button: true,
            label: l10n.emergencyCallSemantics(n.label(l10n), n.number),
            excludeSemantics: true,
            child: Material(
              key: Key('home-dial-${n.number}'),
              color: theme.colorScheme.surfaceContainerLow,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(
                  color: n.service == EmergencyService.civilProtection
                      ? BrandColors.orange
                      : theme.colorScheme.outlineVariant,
                  width: n.service == EmergencyService.civilProtection ? 2 : 1,
                ),
              ),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => dial(n.telUri),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: 12,
                    horizontal: 4,
                  ),
                  child: Column(
                    children: [
                      if (n.service == EmergencyService.civilProtection)
                        const BrandLogo(size: 32)
                      else
                        Icon(n.icon, size: 32, color: _colors[n.service]),
                      const SizedBox(height: 4),
                      Text(
                        n.number,
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          // Lighter tones keep the numbers readable on dark surfaces.
                          color: dark
                              ? Color.lerp(
                                  _colors[n.service],
                                  Colors.white,
                                  0.35,
                                )
                              : _colors[n.service],
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
            ),
          ),
      ],
    );
  }
}

class _Shortcut {
  const _Shortcut(this.key, this.icon, this.label, this.onTap, {this.color});
  final Key key;
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;
}

class _ShortcutTile extends StatelessWidget {
  const _ShortcutTile(this.shortcut);

  final _Shortcut shortcut;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      key: shortcut.key,
      color: theme.colorScheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: shortcut.onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 88),
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  shortcut.icon,
                  size: 28,
                  color: shortcut.color ?? theme.colorScheme.primary,
                ),
                const SizedBox(height: 6),
                Text(
                  shortcut.label,
                  textAlign: TextAlign.center,
                  style: theme.textTheme.labelLarge,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Fixed bar above the navigation: call 198, or send the SOS message (confirmation first).
class _CallBar extends ConsumerWidget {
  const _CallBar();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final civil = emergencyNumbers.first;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
        child: Row(
          children: [
            Expanded(
              child: FilledButton.icon(
                key: const Key('home-call-198'),
                style: FilledButton.styleFrom(
                  backgroundColor: sosRed,
                  foregroundColor: Colors.white,
                ),
                onPressed: () => ref.read(dialerProvider)(civil.telUri),
                icon: const Icon(Icons.phone),
                label: Text(l10n.homeCall198, textAlign: TextAlign.center),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: FilledButton.icon(
                key: const Key('home-sos-message'),
                style: FilledButton.styleFrom(
                  backgroundColor: BrandColors.blue,
                  foregroundColor: Colors.white,
                ),
                onPressed: () => showSosConfirmSheet(context, ref),
                icon: const Icon(Icons.sms),
                label: Text(l10n.homeSosMessage, textAlign: TextAlign.center),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
