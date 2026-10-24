import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../core/config/app_config.dart';
import '../../core/config/providers.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../l10n/app_localizations.dart';
import '../onboarding/login_actions.dart';

/// `14:05` (and the date when it is not today), in the phone's time zone.
String safetyTime(BuildContext context, DateTime at, {DateTime? now}) {
  final local = at.toLocal();
  final today = (now ?? DateTime.now()).toLocal();
  final hm = TimeOfDay.fromDateTime(local).format(context);
  if (local.year == today.year &&
      local.month == today.month &&
      local.day == today.day) {
    return hm;
  }
  final d = local.day.toString().padLeft(2, '0');
  final m = local.month.toString().padLeft(2, '0');
  return '$d/$m $hm';
}

/// `1 h 05 min` style remaining time (never negative).
String safetyDuration(AppLocalizations l10n, Duration d) {
  final minutes = d.isNegative ? 0 : (d.inSeconds / 60).ceil();
  if (minutes < 60) return l10n.safetyMinutes(minutes);
  final h = minutes ~/ 60;
  final m = minutes % 60;
  return m == 0 ? l10n.safetyHours(h) : l10n.safetyHoursMinutes(h, m);
}

/// A small map centred on [point], with its accuracy circle. Tiles of the configured server.
class SafetyMap extends ConsumerWidget {
  const SafetyMap({super.key, required this.point, this.height = 220});

  final GeoPoint point;
  final double height;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final config = ref.watch(appConfigProvider);
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);
    final center = LatLng(point.lat, point.lon);
    final accuracy = point.accuracyM;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: SizedBox(
        height: height,
        child: Stack(
          children: [
            FlutterMap(
              options: MapOptions(
                initialCenter: center,
                initialZoom: 16,
                interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                ),
              ),
              children: [
                TileLayer(
                  urlTemplate: config.mapTileUrl,
                  userAgentPackageName: AppConfig.applicationId,
                ),
                if (accuracy != null && accuracy.isFinite && accuracy > 0)
                  CircleLayer(
                    circles: [
                      CircleMarker(
                        point: center,
                        radius: accuracy,
                        useRadiusInMeter: true,
                        color: theme.colorScheme.error.withValues(alpha: 0.15),
                        borderColor: theme.colorScheme.error,
                        borderStrokeWidth: 1,
                      ),
                    ],
                  ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: center,
                      width: 44,
                      height: 44,
                      alignment: Alignment.topCenter,
                      child: Semantics(
                        label: l10n.mapPinSemantics,
                        child: Icon(
                          Icons.location_pin,
                          size: 44,
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            PositionedDirectional(
              end: 0,
              bottom: 0,
              child: Container(
                color: theme.colorScheme.surface.withValues(alpha: 0.85),
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                child: Text(
                  config.mapAttribution,
                  textDirection: TextDirection.ltr,
                  style: theme.textTheme.labelSmall,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shown instead of a feature that needs an account (links, in-app alerts, live share, check).
class SafetyRegistrationCard extends ConsumerWidget {
  const SafetyRegistrationCard({super.key, required this.reason});

  final String reason;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return Card(
      key: const Key('safety-registration-needed'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(reason),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: () => runLogin(context, ref, register: true),
              icon: const Icon(Icons.person_add),
              label: Text(l10n.settingsRegister),
            ),
          ],
        ),
      ),
    );
  }
}

/// An error of a server call, with a retry.
class SafetyError extends StatelessWidget {
  const SafetyError({super.key, required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(errorMessageFor(l10n, error), textAlign: TextAlign.center),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: Text(l10n.actionRetry),
          ),
        ],
      ),
    );
  }
}

void showSafetySnack(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
