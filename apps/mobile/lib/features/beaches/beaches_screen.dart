import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../core/config/app_config.dart';
import '../../core/config/providers.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart' show Routes;
import '../../core/ui/components.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/sim_banner.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../places/nearest_screen.dart' show myPositionProvider;
import '../places/places_models.dart' show formatDistance;
import 'beach_models.dart';
import 'beach_providers.dart';

const _shown = 30;

String levelLabel(AppLocalizations l10n, BeachLevel level) => switch (level) {
  BeachLevel.red => l10n.beachLevelRed,
  BeachLevel.yellow => l10n.beachLevelYellow,
  BeachLevel.green => l10n.beachLevelGreen,
  BeachLevel.unknown => l10n.beachLevelUnknown,
};

String _num(Object? v) => v is num ? v.toStringAsFixed(v is int ? 0 : 1) : '';

/// One reason of a beach's colour, in words.
String factorText(AppLocalizations l10n, RiskFactor f) => switch (f.code) {
  'waves' => l10n.beachFactorWaves(_num(f.value)),
  'onshore_wind' => l10n.beachFactorOnshore(_num(f.value)),
  'current' => l10n.beachFactorCurrent(_num(f.value)),
  'season' => l10n.beachFactorSeason,
  'crowd' => l10n.beachFactorCrowd,
  'unguarded' => l10n.beachFactorUnguarded,
  'past_drownings' => l10n.beachFactorDrownings(_num(f.value)),
  _ => f.code,
};

/// Phase L1b, the bather's side of coastal safety: today's colour of the beaches (nearest first),
/// why, and an optional warning near a yellow or red beach computed on the phone.
class BeachesScreen extends ConsumerWidget {
  const BeachesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final report = ref.watch(beachesProvider);
    final here = ref.watch(myPositionProvider).value;
    final warn = ref.watch(beachWarningsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.beachesTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref
            ..invalidate(myPositionProvider)
            ..invalidate(beachesProvider);
          await ref.read(beachesProvider.future);
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            ...switch (report) {
              AsyncData(:final value) => _content(
                context,
                ref,
                l10n,
                value,
                here,
                warn,
              ),
              AsyncError(:final error) => [
                Text(
                  errorMessageFor(l10n, error),
                  key: const Key('beaches-error'),
                ),
              ],
              _ => [const Center(child: CircularProgressIndicator())],
            },
          ],
        ),
      ),
    );
  }

  List<Widget> _content(
    BuildContext context,
    WidgetRef ref,
    AppLocalizations l10n,
    BeachesReport report,
    GeoPoint? here,
    bool warn,
  ) {
    final danger = warn
        ? dangerNear(report.items, here, report.warnRadiusM)
        : null;
    final near = byDistance(report.items, here).take(_shown).toList();
    return [
      // ┏━━ SIMULATION ━━ simulated marine weather (WEATHER_PROVIDER=sim)
      // ┃ PRODUCTION: Open-Meteo Marine (or INM) feeds the same colours; the banner disappears.
      // ┗━━━━━━━━━━━━━━━━
      if (report.simulated) SimBanner(text: l10n.beachesSimBanner),
      if (danger != null) _DangerCard(near: danger),
      Card(
        child: SwitchListTile(
          key: const Key('beaches-warn'),
          value: warn,
          title: Text(l10n.beachesWarnToggle),
          subtitle: Text(l10n.beachesWarnHint),
          onChanged: (v) => ref.read(beachWarningsProvider.notifier).set(v),
        ),
      ),
      const SizedBox(height: 8),
      Text(
        l10n.beachDecisionNote,
        style: Theme.of(context).textTheme.bodySmall,
      ),
      const SizedBox(height: 8),
      if (report.items.isNotEmpty) _BeachMap(beaches: report.items, here: here),
      const SizedBox(height: 8),
      if (here == null)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(
            l10n.beachesNoPosition,
            key: const Key('beaches-no-position'),
          ),
        ),
      if (report.items.isEmpty)
        Text(l10n.beachesEmpty, key: const Key('beaches-empty')),
      for (final n in near) _BeachTile(near: n),
      if (report.attribution.isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            report.attribution,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
    ];
  }
}

class _DangerCard extends StatelessWidget {
  const _DangerCard({required this.near});

  final NearBeach near;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = toneOf(near.beach.level).colors(context);
    return Card(
      key: const Key('beaches-danger'),
      color: c.tint,
      child: ListTile(
        leading: Icon(Icons.warning_rounded, color: c.onTint),
        title: Text(
          l10n.beachesDanger(
            near.beach.name,
            levelLabel(l10n, near.beach.level),
            formatDistance(near.distanceM),
          ),
          style: TextStyle(color: c.onTint, fontWeight: FontWeight.w700),
        ),
        subtitle: Text(
          near.beach.factors.map((f) => factorText(l10n, f)).join(' · '),
          style: TextStyle(color: c.onTint),
        ),
        onTap: () => context.push('${Routes.beaches}/${near.beach.id}'),
      ),
    );
  }
}

class _BeachMap extends ConsumerWidget {
  const _BeachMap({required this.beaches, this.here});

  final List<BeachRisk> beaches;
  final GeoPoint? here;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final config = ref.watch(appConfigProvider);
    final centre = here == null
        ? const LatLng(35.9, 10.2)
        : LatLng(here!.lat, here!.lon);
    return Semantics(
      label: l10n.beachesMapLabel,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(Radii.card),
        child: SizedBox(
          height: 220,
          child: FlutterMap(
            options: MapOptions(
              initialCenter: centre,
              initialZoom: here == null ? 6 : 10,
              interactionOptions: const InteractionOptions(
                flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
              ),
            ),
            children: [
              TileLayer(
                urlTemplate: config.mapTileUrl,
                userAgentPackageName: AppConfig.applicationId,
              ),
              MarkerLayer(
                markers: [
                  for (final b in beaches)
                    Marker(
                      point: LatLng(b.lat, b.lon),
                      width: 22,
                      height: 22,
                      child: GestureDetector(
                        onTap: () => context.push('${Routes.beaches}/${b.id}'),
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: toneOf(b.level).colors(context).fill,
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 2),
                          ),
                        ),
                      ),
                    ),
                  if (here != null)
                    Marker(
                      point: LatLng(here!.lat, here!.lon),
                      width: 18,
                      height: 18,
                      child: const Icon(
                        Icons.my_location,
                        size: 18,
                        color: Hue.navy,
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BeachTile extends StatelessWidget {
  const _BeachTile({required this.near});

  final NearBeach near;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final b = near.beach;
    final reasons = b.factors.map((f) => factorText(l10n, f)).join(' · ');
    return Card(
      key: Key('beach-${b.id}'),
      child: ListTile(
        title: Text(b.name),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Pill(levelLabel(l10n, b.level), tone: toneOf(b.level)),
            if (near.distanceM.isFinite || reasons.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                [
                  if (near.distanceM.isFinite) formatDistance(near.distanceM),
                  if (reasons.isNotEmpty) reasons,
                ].join(' · '),
              ),
            ],
          ],
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.push('${Routes.beaches}/${b.id}'),
      ),
    );
  }
}

/// A beach: its colour and why, the next days, its card, and "I am here" when the user agreed.
class BeachScreen extends ConsumerWidget {
  const BeachScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final detail = ref.watch(beachDetailProvider(id));
    return Scaffold(
      appBar: AppBar(
        title: Text(detail.value?.beach.name ?? l10n.beachesTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: switch (detail) {
        AsyncData(:final value) => _BeachBody(detail: value),
        AsyncError(:final error) => Padding(
          padding: const EdgeInsets.all(16),
          child: Text(errorMessageFor(l10n, error)),
        ),
        _ => const Center(child: CircularProgressIndicator()),
      },
    );
  }
}

class _BeachBody extends ConsumerStatefulWidget {
  const _BeachBody({required this.detail});

  final BeachDetail detail;

  @override
  ConsumerState<_BeachBody> createState() => _BeachBodyState();
}

class _BeachBodyState extends ConsumerState<_BeachBody> {
  bool _sending = false;

  String _cardLabel(AppLocalizations l10n, String field) => switch (field) {
    'classification' => l10n.beachCardClassification,
    'blue_flag' => l10n.beachCardBlueFlag,
    'guarded' => l10n.beachCardGuarded,
    'guard_hours' => l10n.beachCardGuardHours,
    'sand' => l10n.beachCardSand,
    'slope' => l10n.beachCardSlope,
    'depth' => l10n.beachCardDepth,
    'currents' => l10n.beachCardCurrents,
    'crowd' => l10n.beachCardCrowd,
    'usage' => l10n.beachCardUsage,
    'peak_season' => l10n.beachCardPeakSeason,
    'water_quality' => l10n.beachCardWaterQuality,
    _ => field,
  };

  String _cardValue(AppLocalizations l10n, Object? value) =>
      switch (yesNo(value)) {
        true => l10n.beachYes,
        false => l10n.beachNo,
        null => '$value',
      };

  Future<void> _present() async {
    final l10n = AppLocalizations.of(context);
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sending = true);
    try {
      await ref.read(presenceSenderProvider)(widget.detail.beach.id);
      messenger.showSnackBar(SnackBar(content: Text(l10n.beachPresenceSent)));
    } on Object catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(errorMessageFor(l10n, e))));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final d = widget.detail;
    final b = d.beach;
    final consent = ref.watch(beachPresenceProvider);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (d.simulated) SimBanner(text: l10n.beachesSimBanner),
        Wrap(
          spacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Pill(levelLabel(l10n, b.level), tone: toneOf(b.level)),
            if (b.score != null) Text(l10n.beachScore(b.score!)),
          ],
        ),
        const SizedBox(height: 8),
        for (final f in b.factors)
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              '• ${factorText(l10n, f)}',
              key: Key('factor-${f.code}'),
            ),
          ),
        const SizedBox(height: 8),
        Text(l10n.beachDecisionNote, style: theme.textTheme.bodySmall),
        const SizedBox(height: 12),
        SectionTitle(l10n.beachDays),
        for (final day in d.days)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(day.day, textDirection: TextDirection.ltr),
            subtitle: Text(
              [
                if (day.waveHeightM != null)
                  l10n.beachWaves(day.waveHeightM!.toStringAsFixed(1)),
                if (day.seaTempC != null)
                  l10n.beachSeaTemp(day.seaTempC!.toStringAsFixed(1)),
              ].join(' · '),
            ),
            trailing: Pill(
              levelLabel(l10n, day.level),
              tone: toneOf(day.level),
            ),
          ),
        if (d.card.isNotEmpty) ...[
          const SizedBox(height: 12),
          SectionTitle(l10n.beachCardTitle),
          for (final e in d.card.entries)
            ListTile(
              key: Key('card-${e.key}'),
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text(_cardLabel(l10n, e.key)),
              subtitle: d.sources[e.key] == null
                  ? null
                  : Text(l10n.beachSource(d.sources[e.key]!)),
              trailing: Text(_cardValue(l10n, e.value)),
            ),
        ],
        const SizedBox(height: 12),
        Card(
          child: Column(
            children: [
              SwitchListTile(
                key: const Key('beach-presence-consent'),
                value: consent,
                title: Text(l10n.beachPresenceToggle),
                subtitle: Text(l10n.beachPresenceHint),
                onChanged: (v) =>
                    ref.read(beachPresenceProvider.notifier).set(v),
              ),
              if (consent)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: FilledButton.icon(
                    key: const Key('beach-presence'),
                    icon: const Icon(Icons.beach_access_rounded),
                    label: Text(l10n.beachPresenceButton),
                    onPressed: _sending ? null : _present,
                  ),
                ),
            ],
          ),
        ),
        if (d.attribution.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(d.attribution, style: theme.textTheme.bodySmall),
          ),
      ],
    );
  }
}
