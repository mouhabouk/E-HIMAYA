import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:latlong2/latlong.dart';

import '../../core/config/app_config.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/sim_banner.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../guide/guide_models.dart' show guideColour;
import '../institution/institution_providers.dart';
import 'places_models.dart';
import 'places_providers.dart';

/// The user's position for "nearest to me": asked when the screen opens (prompting once if
/// needed), null when location is off or refused.
final myPositionProvider = FutureProvider.autoDispose<GeoPoint?>(
  (ref) => ref.read(locationServiceProvider).bestEffort(),
  retry: (_, _) => null,
);

/// Phase L1b: the nearest places of a layer timed on the road by the server, when it can be
/// reached (offline, the list keeps its straight-line order and distances).
final roadTimesProvider = FutureProvider.autoDispose
    .family<Map<String, RoadTime>, (String, double, double)>((ref, at) async {
      final (key, lat, lon) = at;
      try {
        return await ref
            .read(apiProvider)
            .roadNearest(key, GeoPoint(lat: lat, lon: lon));
      } on ApiException {
        return const {};
      }
    }, retry: (_, _) => null);

/// Layers the user turned off, kept between visits.
class PlacesOffController extends Notifier<Set<String>> {
  @override
  Set<String> build() => ref.read(appPrefsProvider).placesOff.toSet();

  Future<void> toggle(String key) async {
    final next = {...state};
    if (!next.remove(key)) next.add(key);
    state = next;
    await ref.read(appPrefsProvider).setPlacesOff(next.toList()..sort());
  }
}

final placesOffProvider = NotifierProvider<PlacesOffController, Set<String>>(
  PlacesOffController.new,
);

/// Emergency hub, phase B1: my coordinates (to read to the operator), then the three nearest
/// places of each public layer, computed on the phone from the copy kept offline.
class NearestScreen extends ConsumerWidget {
  const NearestScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final lang = ref.watch(localeCodeProvider);
    final places = ref.watch(placesProvider);
    final position = ref.watch(myPositionProvider);
    final off = ref.watch(placesOffProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.nearestTitle),
        actions: [
          IconButton(
            key: const Key('nearest-map-action'),
            tooltip: l10n.nearestMapTitle,
            icon: const Icon(Icons.map_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const NearestMapScreen()),
            ),
          ),
          const LanguageMenuAction(),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(myPositionProvider);
          await ref.read(placesProvider.notifier).refresh();
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            _PositionCard(position: position),
            const SizedBox(height: 12),
            ...switch (places) {
              AsyncData(:final value) => _layers(
                context,
                l10n,
                lang,
                value,
                position.value,
                off,
                ref,
              ),
              AsyncError() => [Text(l10n.nearestEmpty)],
              _ => [const Center(child: CircularProgressIndicator())],
            },
          ],
        ),
      ),
    );
  }

  List<Widget> _layers(
    BuildContext context,
    AppLocalizations l10n,
    String lang,
    PlacesData data,
    GeoPoint? here,
    Set<String> off,
    WidgetRef ref,
  ) {
    if (data.isEmpty) {
      return [
        Text(
          data.refreshFailed ? l10n.nearestEmpty : l10n.nearestLoading,
          key: const Key('nearest-empty'),
        ),
      ];
    }
    final shown = data.layers.where((l) => !off.contains(l.key)).toList();
    return [
      // ┏━━ SIMULATION ━━ layers of approximate, invented places (scripts/sim_layers.py)
      // ┃ PRODUCTION: the Office's lists replace them and the layer loses its "simulated" mark.
      // ┗━━━━━━━━━━━━━━━━
      if (shown.any((l) => l.simulated)) SimBanner(text: l10n.nearestSimBanner),
      if (data.refreshFailed)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Text(
            l10n.nearestOffline,
            key: const Key('nearest-offline'),
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      Wrap(
        spacing: 8,
        runSpacing: 4,
        children: [
          for (final layer in data.layers)
            FilterChip(
              key: Key('layer-chip-${layer.key}'),
              avatar: Icon(
                layerIcon(layer.icon),
                size: 18,
                color: guideColour(layer.colour),
              ),
              label: Text(layer.nameFor(lang)),
              selected: !off.contains(layer.key),
              onSelected: (_) =>
                  ref.read(placesOffProvider.notifier).toggle(layer.key),
            ),
        ],
      ),
      const SizedBox(height: 12),
      for (final layer in shown)
        _LayerCard(
          layer: layer,
          lang: lang,
          here: here,
          near: here == null
              ? null
              : nearest(data.packages[layer.key]?.places ?? const [], here),
        ),
      if (data.updatedAt != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            l10n.nearestUpdated(
              DateFormat.yMMMd(lang).add_Hm().format(data.updatedAt!),
            ),
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
    ];
  }
}

class _PositionCard extends ConsumerWidget {
  const _PositionCard({required this.position});

  final AsyncValue<GeoPoint?> position;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final here = position.value;
    final coords = here == null
        ? null
        : '${here.lat.toStringAsFixed(5)}, ${here.lon.toStringAsFixed(5)}';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.nearestMyPosition, style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            if (position.isLoading)
              Text(l10n.locationLocating)
            else if (coords == null) ...[
              Text(
                l10n.nearestNoLocation,
                key: const Key('nearest-no-location'),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                icon: const Icon(Icons.my_location),
                label: Text(l10n.locationRefresh),
                onPressed: () async {
                  final service = ref.read(locationServiceProvider);
                  if (await service.status() != LocationAvailability.granted) {
                    await service.openSettings();
                  }
                  ref.invalidate(myPositionProvider);
                },
              ),
            ] else ...[
              Text(
                coords,
                key: const Key('nearest-coords'),
                textDirection: TextDirection.ltr,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (here!.accuracyM != null)
                Text(l10n.locationAccuracy(here.accuracyM!.round())),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    key: const Key('nearest-copy'),
                    icon: const Icon(Icons.copy),
                    label: Text(l10n.nearestCopy),
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: coords));
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(l10n.nearestCopied)),
                        );
                      }
                    },
                  ),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.my_location),
                    label: Text(l10n.locationRefresh),
                    onPressed: () => ref.invalidate(myPositionProvider),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _LayerCard extends ConsumerWidget {
  const _LayerCard({
    required this.layer,
    required this.lang,
    this.here,
    this.near,
  });

  final PlaceLayer layer;
  final String lang;
  final GeoPoint? here;

  /// Null while the position is unknown.
  final List<NearPlace>? near;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final colour = guideColour(layer.colour);
    final at = here;
    final road = at == null
        ? const <String, RoadTime>{}
        : ref.watch(roadTimesProvider((layer.key, at.lat, at.lon))).value ??
              const <String, RoadTime>{};
    return Card(
      key: Key('nearest-layer-${layer.key}'),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor: colour,
                  child: Icon(
                    layerIcon(layer.icon),
                    color: Colors.white,
                    size: 18,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    layer.nameFor(lang),
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (layer.simulated)
                  Padding(
                    padding: const EdgeInsetsDirectional.only(end: 4),
                    child: Chip(
                      key: Key('sim-layer-${layer.key}'),
                      label: Text(l10n.nearestSimChip),
                      backgroundColor: simAmber,
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                if (layer.toVerify)
                  Chip(
                    key: Key('to-verify-${layer.key}'),
                    label: Text(l10n.nearestToVerify),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            if (near == null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(l10n.nearestNeedPosition),
              )
            else if (near!.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(l10n.nearestNone),
              )
            else
              for (final p in near!)
                _PlaceTile(near: p, road: road[p.place.id]),
            if (layer.source.isNotEmpty)
              Text(
                l10n.nearestSource(
                  [
                    layer.source,
                    layer.licence,
                  ].where((s) => s.isNotEmpty).join(' · '),
                ),
                style: theme.textTheme.bodySmall,
              ),
          ],
        ),
      ),
    );
  }
}

class _PlaceTile extends ConsumerWidget {
  const _PlaceTile({required this.near, this.road});

  final NearPlace near;

  /// The time on the road, when the server gave it.
  final RoadTime? road;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final place = near.place;
    final details = [
      place.kind,
      place.prop('address'),
      place.prop('hours'),
    ].whereType<String>().where((s) => s.trim().isNotEmpty).join(' · ');
    final phone = place.phone;
    return ListTile(
      key: Key('place-${place.id}'),
      contentPadding: EdgeInsets.zero,
      title: Text(place.name),
      subtitle: Text(
        [
          formatDistance(near.distanceM),
          if (road case final r?)
            r.estimated
                ? l10n.nearestByRoadEstimate(_minutes(r.seconds))
                : l10n.nearestByRoad(_minutes(r.seconds)),
          if (details.isNotEmpty) details,
        ].join(' · '),
      ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (phone != null && phone.isNotEmpty)
            IconButton(
              key: Key('call-${place.id}'),
              tooltip: l10n.nearestCall(phone),
              icon: const Icon(Icons.call),
              onPressed: () async {
                final ok = await ref.read(dialerProvider)(
                  Uri(scheme: 'tel', path: phone),
                );
                if (!ok && context.mounted) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(SnackBar(content: Text(l10n.dialFailed)));
                }
              },
            ),
          IconButton(
            key: Key('route-${place.id}'),
            tooltip: l10n.nearestRoute,
            icon: const Icon(Icons.directions),
            onPressed: () => ref.read(urlOpenerProvider)(routeUri(place)),
          ),
        ],
      ),
    );
  }
}

/// Phase D, review point 18: the places of the layers shown, on a map, drawn from the copy kept on
/// the phone. The markers need no connection; the background map comes from `MAP_TILE_URL` (the
/// offline map server of docs/offline-maps.md on the demonstration network) and stays plain when it
/// cannot be reached. Opened from the list's app bar, so the list stays the quick way.
class NearestMapScreen extends ConsumerStatefulWidget {
  const NearestMapScreen({super.key});

  @override
  ConsumerState<NearestMapScreen> createState() => _NearestMapScreenState();
}

class _NearestMapScreenState extends ConsumerState<NearestMapScreen> {
  String get _lang => ref.read(localeCodeProvider);

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final places = ref.watch(placesProvider).value;
    final here = ref.watch(myPositionProvider).value;
    final off = ref.watch(placesOffProvider);
    final layers = (places?.layers ?? const <PlaceLayer>[])
        .where((l) => !off.contains(l.key))
        .toList();
    final shown = [
      for (final layer in layers)
        for (final p in mapPlaces(
          places?.packages[layer.key]?.places ?? const [],
          here,
        ))
          (layer, p),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.nearestMapTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ┏━━ SIMULATION ━━ same mark as the list: approximate, invented places
          // ┗━━━━━━━━━━━━━━━━
          if (layers.any((l) => l.simulated))
            SimBanner(text: l10n.nearestSimBanner),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Text(
              l10n.nearestMapHint(shown.length),
              key: const Key('nearest-map-hint'),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          Expanded(child: _map(context, l10n, shown, here)),
        ],
      ),
    );
  }

  Widget _map(
    BuildContext context,
    AppLocalizations l10n,
    List<(PlaceLayer, Place)> shown,
    GeoPoint? here,
  ) {
    final config = ref.watch(appConfigProvider);
    final centre = here != null
        ? LatLng(here.lat, here.lon)
        : shown.isNotEmpty
        ? LatLng(shown.first.$2.lat, shown.first.$2.lon)
        : const LatLng(35.9, 10.2);
    return Semantics(
      label: l10n.nearestMapTitle,
      child: SizedBox(
        key: const Key('nearest-map'),
        child: ColoredBox(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: FlutterMap(
            options: MapOptions(
              initialCenter: centre,
              initialZoom: here == null ? 7 : 12,
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
                  for (final (layer, p) in shown)
                    Marker(
                      point: LatLng(p.lat, p.lon),
                      width: 32,
                      height: 32,
                      child: Semantics(
                        button: true,
                        label: '${layer.nameFor(_lang)}: ${p.name}',
                        child: GestureDetector(
                          key: Key('marker-${p.id}'),
                          onTap: () => _details(context, layer, p),
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              color: guideColour(layer.colour),
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 2),
                            ),
                            child: Icon(
                              layerIcon(layer.icon),
                              size: 16,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (here != null)
                    Marker(
                      point: LatLng(here.lat, here.lon),
                      width: 22,
                      height: 22,
                      child: const Icon(
                        Icons.my_location,
                        key: Key('marker-me'),
                        size: 22,
                        color: Hue.navy,
                      ),
                    ),
                ],
              ),
              RichAttributionWidget(
                attributions: [TextSourceAttribution(config.mapAttribution)],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _details(BuildContext context, PlaceLayer layer, Place p) {
    final here = ref.read(myPositionProvider).value;
    final near = NearPlace(
      p,
      here == null ? 0 : distanceM(here.lat, here.lon, p.lat, p.lon),
    );
    return showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                layer.nameFor(_lang),
                style: Theme.of(context).textTheme.labelLarge,
              ),
              _PlaceTile(near: near),
            ],
          ),
        ),
      ),
    );
  }
}

/// The places drawn on the map: with a position, the [mapMarkersPerLayer] nearest of the layer;
/// without, the first ones of the copy. A few hundred markers stay smooth on a modest phone.
const mapMarkersPerLayer = 60;

List<Place> mapPlaces(List<Place> places, GeoPoint? here) {
  if (here == null) return places.take(mapMarkersPerLayer).toList();
  return [
    for (final n in nearest(places, here, limit: mapMarkersPerLayer)) n.place,
  ];
}

int _minutes(int seconds) => seconds < 60 ? 1 : (seconds / 60).round();

/// Opens the phone's own maps app on the place (`geo:` URI, understood by Android and by the
/// usual map apps), with the name as label.
Uri routeUri(Place place) => Uri.parse(
  'geo:${place.lat},${place.lon}?q=${place.lat},${place.lon}'
  '(${Uri.encodeComponent(place.name)})',
);
