import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../core/config/app_config.dart';
import '../../core/config/providers.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../l10n/app_localizations.dart';

enum _Fix { locating, ok, unavailable, denied }

/// GPS auto-location with accuracy, and a map whose centre pin the user can move by dragging
/// the map (FR-A-040). A manually placed pin has no accuracy value.
class LocationPicker extends ConsumerStatefulWidget {
  const LocationPicker({super.key, required this.onChanged});

  final ValueChanged<GeoPoint?> onChanged;

  @override
  ConsumerState<LocationPicker> createState() => _LocationPickerState();
}

class _LocationPickerState extends ConsumerState<LocationPicker> {
  static const _tunis = LatLng(36.8065, 10.1815);
  final _map = MapController();
  _Fix _fix = _Fix.locating;
  GeoPoint? _point;
  bool _manual = false;
  bool _mapReady = false;

  @override
  void initState() {
    super.initState();
    _locate();
  }

  @override
  void dispose() {
    _map.dispose();
    super.dispose();
  }

  Future<void> _locate() async {
    setState(() {
      _fix = _Fix.locating;
      _manual = false;
    });
    final service = ref.read(locationServiceProvider);
    final permission = await service.ensurePermission();
    if (!mounted) return;
    if (permission != LocationAvailability.granted) {
      setState(() => _fix = _Fix.denied);
      return;
    }
    final point = await service.bestEffort(
      timeout: const Duration(seconds: 10),
    );
    if (!mounted) return;
    if (point == null) {
      setState(() => _fix = _Fix.unavailable);
      return;
    }
    _set(point, manual: false);
    if (_mapReady) _map.move(LatLng(point.lat, point.lon), 16);
  }

  void _set(GeoPoint point, {required bool manual}) {
    setState(() {
      _point = point;
      _manual = manual;
      _fix = _Fix.ok;
    });
    widget.onChanged(point);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final AppConfig config = ref.watch(appConfigProvider);
    final point = _point;
    final status = switch (_fix) {
      _Fix.locating => l10n.locationLocating,
      _Fix.denied => l10n.locationPermissionDenied,
      _Fix.unavailable => l10n.locationUnavailable,
      _Fix.ok when _manual => l10n.locationManual,
      _Fix.ok =>
        point?.accuracyM == null
            ? l10n.locationManual
            : l10n.locationAccuracy(point!.accuracyM!.round()),
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Icon(
              _fix == _Fix.ok ? Icons.my_location : Icons.location_searching,
              color: _fix == _Fix.ok ? theme.colorScheme.primary : null,
            ),
            const SizedBox(width: 8),
            Expanded(child: Text(status, style: theme.textTheme.bodyMedium)),
            if (_fix == _Fix.locating)
              const SizedBox.square(
                dimension: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            IconButton(
              tooltip: l10n.locationRefresh,
              icon: const Icon(Icons.gps_fixed),
              onPressed: _fix == _Fix.locating ? null : _locate,
            ),
          ],
        ),
        if (point != null && !point.isInTunisiaBox)
          Text(
            l10n.locationOutsideTunisia,
            style: TextStyle(color: theme.colorScheme.error),
          ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(
            height: 240,
            child: Stack(
              children: [
                FlutterMap(
                  mapController: _map,
                  options: MapOptions(
                    initialCenter: point == null
                        ? _tunis
                        : LatLng(point.lat, point.lon),
                    initialZoom: point == null ? 7 : 16,
                    onMapReady: () => _mapReady = true,
                    onPositionChanged: (camera, hasGesture) {
                      if (!hasGesture) return;
                      _set(
                        GeoPoint(
                          lat: camera.center.latitude,
                          lon: camera.center.longitude,
                        ),
                        manual: true,
                      );
                    },
                    interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                    ),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: config.mapTileUrl,
                      userAgentPackageName: AppConfig.applicationId,
                    ),
                  ],
                ),
                // Fixed centre pin: the map moves underneath it.
                IgnorePointer(
                  child: Center(
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 40),
                      child: Semantics(
                        label: l10n.mapPinSemantics,
                        child: Icon(
                          Icons.location_pin,
                          size: 44,
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ),
                  ),
                ),
                PositionedDirectional(
                  end: 0,
                  bottom: 0,
                  child: Container(
                    color: theme.colorScheme.surface.withValues(alpha: 0.85),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
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
        ),
        const SizedBox(height: 4),
        Text(l10n.locationAdjustHint, style: theme.textTheme.bodySmall),
      ],
    );
  }
}
