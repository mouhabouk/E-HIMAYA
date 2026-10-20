// ┏━━ SIMULATION ━━ Amber "Simulation mode" band inside the weather card (WEATHER_PROVIDER=sim).
// ┃ PRODUCTION: nothing to remove: the band renders only when the API answers
// ┃   `"simulated": true`, i.e. while the server runs the weather simulator. Set
// ┃   WEATHER_PROVIDER=open-meteo (or a national feed) on the API and it disappears.
// ┗━━━━━━━━━━━━━━━━
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/config/providers.dart';
import '../../core/http/notify_models.dart';
import '../../core/http/weather_models.dart';
import '../../core/location/location_service.dart';
import '../../core/routing/app_router.dart';
import '../../core/settings/settings_controller.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alert_labels.dart';
import '../institution/institution_providers.dart';
import 'weather_providers.dart';

String fireDangerLabel(AppLocalizations l10n, FireDanger d) => switch (d) {
  FireDanger.low => l10n.weatherFireLow,
  FireDanger.moderate => l10n.weatherFireModerate,
  FireDanger.high => l10n.weatherFireHigh,
  FireDanger.veryHigh => l10n.weatherFireVeryHigh,
  FireDanger.extreme => l10n.weatherFireExtreme,
};

/// Badge colours: text keeps at least 4.5:1 on its background in both themes.
(Color, Color) fireDangerColors(FireDanger d) => switch (d) {
  FireDanger.low => (const Color(0xFF2E7D32), Colors.white),
  FireDanger.moderate => (const Color(0xFFF9A825), Colors.black),
  FireDanger.high => (const Color(0xFFEF6C00), Colors.black),
  FireDanger.veryHigh => (const Color(0xFFC62828), Colors.white),
  FireDanger.extreme => (const Color(0xFF4A0000), Colors.white),
};

(Color, Color) rainLevelColors(RainLevel r) => switch (r) {
  RainLevel.none => (const Color(0xFF1565C0), Colors.white),
  RainLevel.watch => (const Color(0xFFFBC02D), Colors.black),
  RainLevel.warning => (const Color(0xFFBF360C), Colors.white),
};

enum WeatherCondition { clear, cloudy, fog, rain, snow, storm }

/// From the WMO code when the server sends it, otherwise from the precipitation.
WeatherCondition conditionOf(WeatherHour h) {
  final code = h.weatherCode;
  if (code != null) {
    if (code == 0) return WeatherCondition.clear;
    if (code <= 3) return WeatherCondition.cloudy;
    if (code == 45 || code == 48) return WeatherCondition.fog;
    if ((code >= 71 && code <= 77) || code == 85 || code == 86) {
      return WeatherCondition.snow;
    }
    if (code >= 95) return WeatherCondition.storm;
    if (code >= 51) return WeatherCondition.rain;
    return WeatherCondition.cloudy;
  }
  final rain = h.precipitationMmH;
  if (rain != null && rain >= 0.1) return WeatherCondition.rain;
  return WeatherCondition.clear;
}

IconData conditionIcon(WeatherCondition c) => switch (c) {
  WeatherCondition.clear => Icons.wb_sunny_outlined,
  WeatherCondition.cloudy => Icons.cloud_outlined,
  WeatherCondition.fog => Icons.foggy,
  WeatherCondition.rain => Icons.water_drop_outlined,
  WeatherCondition.snow => Icons.ac_unit,
  WeatherCondition.storm => Icons.thunderstorm_outlined,
};

String conditionLabel(AppLocalizations l10n, WeatherCondition c) => switch (c) {
  WeatherCondition.clear => l10n.weatherCondClear,
  WeatherCondition.cloudy => l10n.weatherCondCloudy,
  WeatherCondition.fog => l10n.weatherCondFog,
  WeatherCondition.rain => l10n.weatherCondRain,
  WeatherCondition.snow => l10n.weatherCondSnow,
  WeatherCondition.storm => l10n.weatherCondStorm,
};

/// FR-A-034: the weather card of the home screen — current values and the next hours at the
/// user's coarse position, the weather alerts in force (opening the alert detail), fire-danger
/// and heavy-rain badges, the data attribution, and the time of the values (an offline copy
/// says so).
class WeatherCard extends ConsumerWidget {
  const WeatherCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final state = ref.watch(weatherProvider);
    final report = state.report;
    final now = ref.watch(clockProvider)();
    return Card(
      key: const Key('weather-card'),
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _padded(
              Row(
                children: [
                  Expanded(
                    child: Semantics(
                      header: true,
                      child: Text(
                        l10n.weatherTitle,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                  ),
                  if (state.loading)
                    Semantics(
                      label: l10n.weatherLoading,
                      child: const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                ],
              ),
            ),
            if (report != null && report.simulated) const _SimulationBand(),
            if (report == null)
              _padded(_EmptyState(state: state))
            else ...[
              _WeatherAlerts(alerts: report.activeAlerts(now)),
              _padded(_Current(report: report, now: now)),
              _Hours(hours: report.nextHours(now)),
              _padded(_Footer(state: state, report: report)),
            ],
          ],
        ),
      ),
    );
  }
}

Widget _padded(Widget child) => Padding(
  padding: const EdgeInsetsDirectional.symmetric(horizontal: 16, vertical: 4),
  child: child,
);

String _number(BuildContext context, double v, {int decimals = 0}) {
  final f = NumberFormat.decimalPatternDigits(
    locale: Localizations.localeOf(context).toLanguageTag(),
    decimalDigits: decimals,
  );
  return f.format(v);
}

class _SimulationBand extends StatelessWidget {
  const _SimulationBand();

  static const _background = Color(0xFFFFB300); // amber 600
  static const _foreground = Color(0xFF3E2723);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      child: Container(
        key: const Key('weather-simulation-band'),
        margin: const EdgeInsetsDirectional.fromSTEB(16, 4, 16, 4),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: _background,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.science_outlined, color: _foreground, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: '${l10n.weatherSimulationBadge} — ',
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    TextSpan(text: l10n.weatherSimulationHelp),
                  ],
                ),
                style: text.bodySmall?.copyWith(color: _foreground),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends ConsumerWidget {
  const _EmptyState({required this.state});

  final WeatherCardState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final controller = ref.read(weatherProvider.notifier);
    final (message, action) = switch (state.issue) {
      null => (l10n.weatherLoading, null),
      WeatherIssue.noLocation => (
        l10n.weatherNoLocation,
        TextButton.icon(
          key: const Key('weather-use-location'),
          onPressed: () async {
            // An explicit tap: the only place the card may show the permission prompt.
            final granted = await ref
                .read(locationServiceProvider)
                .ensurePermission();
            if (granted == LocationAvailability.granted) {
              await controller.refreshManually();
            }
          },
          icon: const Icon(Icons.my_location),
          label: Text(l10n.weatherUseLocation),
        ),
      ),
      WeatherIssue.outsideCoverage => (l10n.weatherOutsideCoverage, null),
      WeatherIssue.offline => (l10n.weatherOffline, null),
      WeatherIssue.unavailable => (
        l10n.weatherUnavailable,
        TextButton.icon(
          key: const Key('weather-retry'),
          onPressed: () => unawaited(controller.refreshManually()),
          icon: const Icon(Icons.refresh),
          label: Text(l10n.weatherRetry),
        ),
      ),
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(message, key: const Key('weather-message')),
        ?action,
      ],
    );
  }
}

class _WeatherAlerts extends ConsumerWidget {
  const _WeatherAlerts({required this.alerts});

  final List<ActiveAlert> alerts;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (alerts.isEmpty) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    return Padding(
      padding: const EdgeInsetsDirectional.fromSTEB(12, 4, 12, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 4, bottom: 4),
            child: Text(
              l10n.weatherAlertsTitle,
              style: Theme.of(context).textTheme.labelLarge,
            ),
          ),
          for (final a in alerts)
            Builder(
              builder: (context) {
                final (bg, fg) = severityColors(a.severity);
                return Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Material(
                    color: bg,
                    borderRadius: BorderRadius.circular(8),
                    clipBehavior: Clip.antiAlias,
                    child: ListTile(
                      key: Key('weather-alert-${a.id}'),
                      leading: Icon(hazardIcon(a.hazard), color: fg),
                      title: Text(
                        a.title.of(lang),
                        style: TextStyle(
                          color: fg,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      subtitle: Text(
                        '${severityLabel(l10n, a.severity)} · '
                        '${l10n.alertUntil(dateTimeLabel(context, a.expiresAt))}',
                        style: TextStyle(color: fg),
                      ),
                      // chevron_right is mirrored in RTL by Flutter itself.
                      trailing: Icon(Icons.chevron_right, color: fg),
                      onTap: () => context.push(Routes.alert(a.id)),
                    ),
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}

class _Current extends StatelessWidget {
  const _Current({required this.report, required this.now});

  final WeatherReport report;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final c = report.current;
    final condition = conditionOf(c);
    final temp = c.temperatureC;
    final details = <String>[
      if (c.windKmh != null)
        [
          l10n.weatherWind(_number(context, c.windKmh!)),
          if (c.gustKmh != null)
            l10n.weatherGusts(_number(context, c.gustKmh!)),
        ].join(', '),
      if (c.humidityPct != null)
        l10n.weatherHumidity(_number(context, c.humidityPct!)),
      if (c.precipitationMmH != null)
        l10n.weatherRain(_number(context, c.precipitationMmH!, decimals: 1)),
      if (c.precipitation24hMm != null)
        l10n.weatherRain24h(
          _number(context, c.precipitation24hMm!, decimals: 1),
        ),
    ];
    final fire = report.maxFireDanger(now);
    final rain = report.maxRainLevel(now);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MergeSemantics(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                conditionIcon(condition),
                size: 40,
                color: theme.colorScheme.primary,
                semanticLabel: conditionLabel(l10n, condition),
              ),
              const SizedBox(width: 12),
              if (temp != null)
                Semantics(
                  label: l10n.weatherTemperature(_number(context, temp)),
                  excludeSemantics: true,
                  child: Text(
                    '${_number(context, temp)}°',
                    key: const Key('weather-temp'),
                    style: theme.textTheme.displaySmall,
                  ),
                ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Already announced by the icon's semantic label.
                    ExcludeSemantics(
                      child: Text(
                        conditionLabel(l10n, condition),
                        style: theme.textTheme.titleSmall,
                      ),
                    ),
                    for (final d in details)
                      Text(d, style: theme.textTheme.bodySmall),
                  ],
                ),
              ),
              if (c.windDirectionDeg != null)
                ExcludeSemantics(
                  // Geographic direction the wind blows towards: not mirrored in RTL.
                  child: Transform.rotate(
                    angle:
                        (c.windDirectionDeg! + 180) * 3.141592653589793 / 180,
                    child: Icon(
                      Icons.navigation,
                      size: 20,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
            ],
          ),
        ),
        if (fire != null || (rain != null && rain != RainLevel.none)) ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              if (fire != null)
                _Badge(
                  key: const Key('weather-fire-badge'),
                  icon: Icons.local_fire_department,
                  text: l10n.weatherFireDanger(fireDangerLabel(l10n, fire)),
                  colors: fireDangerColors(fire),
                ),
              if (rain != null && rain != RainLevel.none)
                _Badge(
                  key: const Key('weather-rain-badge'),
                  icon: Icons.thunderstorm,
                  text: l10n.weatherHeavyRain(
                    rain == RainLevel.warning
                        ? l10n.weatherRainWarning
                        : l10n.weatherRainWatch,
                  ),
                  colors: rainLevelColors(rain),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({
    super.key,
    required this.icon,
    required this.text,
    required this.colors,
  });

  final IconData icon;
  final String text;
  final (Color, Color) colors;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = colors;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsetsDirectional.fromSTEB(8, 4, 12, 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: fg),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                text,
                style: Theme.of(context).textTheme.labelMedium
                    ?.copyWith(color: fg, fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Hours extends StatelessWidget {
  const _Hours({required this.hours});

  final List<WeatherHour> hours;

  @override
  Widget build(BuildContext context) {
    if (hours.isEmpty) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).toLanguageTag();
    final scale = MediaQuery.textScalerOf(context).scale(1);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _padded(Text(l10n.weatherNextHours, style: theme.textTheme.labelLarge)),
        SizedBox(
          // Grows with the user's text size so labels are never clipped.
          height: 92 * scale.clamp(1.0, 2.0),
          child: ListView.separated(
            key: const Key('weather-hours'),
            // Follows the reading direction: in Arabic the next hour is on the right.
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsetsDirectional.symmetric(horizontal: 16),
            itemCount: hours.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (context, i) {
              final h = hours[i];
              final time = DateFormat.Hm(locale).format(h.time.toLocal());
              final condition = conditionOf(h);
              final parts = [
                time,
                if (h.temperatureC != null)
                  l10n.weatherTemperature(_number(context, h.temperatureC!)),
                conditionLabel(l10n, condition),
                if (h.precipitationMmH != null && h.precipitationMmH! > 0)
                  l10n.weatherRain(
                    _number(context, h.precipitationMmH!, decimals: 1),
                  ),
              ];
              return Semantics(
                label: parts.join(', '),
                excludeSemantics: true,
                child: Container(
                  width: 64,
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      Text(time, style: theme.textTheme.labelSmall),
                      Icon(conditionIcon(condition), size: 20),
                      Text(
                        h.temperatureC == null
                            ? '–'
                            : '${_number(context, h.temperatureC!)}°',
                        style: theme.textTheme.labelLarge,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _Footer extends ConsumerWidget {
  const _Footer({required this.state, required this.report});

  final WeatherCardState state;
  final WeatherReport report;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final small = theme.textTheme.bodySmall;
    final at = report.updatedAt ?? state.fetchedAt;
    final stale = state.fromCache || state.issue != null;
    final url = report.attribution.url;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (state.issue != null && state.issue != WeatherIssue.offline)
          Text(l10n.weatherNotRefreshed, style: small),
        if (at != null)
          Row(
            children: [
              if (stale) ...[
                Icon(
                  Icons.cloud_off,
                  size: 14,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: 4),
              ],
              Expanded(
                child: Text(
                  stale
                      ? l10n.weatherCachedAt(dateTimeLabel(context, at))
                      : l10n.weatherUpdated(dateTimeLabel(context, at)),
                  key: const Key('weather-time'),
                  style: small,
                ),
              ),
            ],
          ),
        Semantics(
          link: url != null,
          child: InkWell(
            key: const Key('weather-attribution'),
            onTap: url == null
                ? null
                : () => unawaited(ref.read(urlOpenerProvider)(Uri.parse(url))),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text(
                l10n.weatherSource(report.attribution.text),
                style: small?.copyWith(
                  decoration: url == null ? null : TextDecoration.underline,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
