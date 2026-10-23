import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/location/location_service.dart';
import '../../l10n/app_localizations.dart';

/// Whether location works now (no permission prompt). Refreshed when the strip is tapped.
final locationStatusProvider = FutureProvider.autoDispose<LocationAvailability>(
  (ref) => ref.watch(locationServiceProvider).status(),
);

/// Addition 4: location on every use. Green when it works; amber with "Turn on" otherwise. SOS
/// and the emergency numbers are never blocked by it.
class LocationStrip extends ConsumerWidget {
  const LocationStrip({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final status = ref.watch(locationStatusProvider);
    final on = status.value == LocationAvailability.granted;
    final checking = status.isLoading && !status.hasValue;
    final dark = theme.brightness == Brightness.dark;
    final background = on
        ? (dark ? const Color(0xFF16351E) : const Color(0xFFE3F2E5))
        : (dark ? const Color(0xFF3D2E00) : const Color(0xFFFFF3CD));
    final foreground = on
        ? (dark ? const Color(0xFF9BE3A4) : const Color(0xFF1B5E20))
        : (dark ? const Color(0xFFFFD866) : const Color(0xFF6D4C00));
    return Semantics(
      liveRegion: true,
      child: Container(
        key: Key(on ? 'location-on' : 'location-off'),
        margin: const EdgeInsets.only(top: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            // Shape and text, not colour alone (rule 3).
            Icon(
              on ? Icons.location_on : Icons.location_off,
              color: foreground,
              size: 20,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                checking
                    ? l10n.locationChecking
                    : on
                    ? l10n.locationOn
                    : l10n.locationOff,
                style: TextStyle(
                  color: foreground,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (!on && !checking)
              TextButton(
                key: const Key('location-turn-on'),
                style: TextButton.styleFrom(foregroundColor: foreground),
                onPressed: () async {
                  await ref.read(locationServiceProvider).openSettings();
                  ref.invalidate(locationStatusProvider);
                },
                child: Text(l10n.locationTurnOn),
              ),
          ],
        ),
      ),
    );
  }
}
