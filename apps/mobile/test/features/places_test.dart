// covers: phase B1 "nearest to me" (docs/phase-b/design.md §2): public layers and their places kept
// offline with ETags, nearest computed on the phone, call and route, coordinates to read out.
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/features/places/nearest_screen.dart';
import 'package:ehimaya/features/places/places_models.dart';
import 'package:ehimaya/features/places/places_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

Map<String, Object?> _layer(
  String key, {
  bool toVerify = false,
  bool simulated = false,
}) => {
  'key': key,
  'name': key,
  'names': {'ar': 'ع $key', 'fr': 'F $key', 'en': 'E $key'},
  'icon': key == 'civil_protection' ? 'civil_protection' : 'hospital',
  'colour': '#C62828',
  'source': 'OpenStreetMap',
  'licence': 'ODbL',
  'to_verify': toVerify,
  'simulated': simulated,
  'count': 2,
  'data_version': 1,
  'origin': key == 'civil_protection' ? 'units' : 'file',
};

Map<String, Object?> _place(
  String id,
  double lat,
  double lon, {
  String? phone,
}) => {
  'id': id,
  'name': 'Place $id',
  'kind': null,
  'phone': phone,
  'lat': lat,
  'lon': lon,
  'gouvernorat_code': 11,
  'props': {'address': 'Rue $id'},
};

/// Tunis centre is 36.8, 10.18 (the fake location); Sfax is far away.
final _packages = <String, Map<String, Object?>>{
  'civil_protection': {
    'layer': 'civil_protection',
    'data_version': 1,
    'items': [
      _place('cp-tunis', 36.81, 10.17, phone: '198'),
      _place('cp-sfax', 34.74, 10.76, phone: '74000000'),
    ],
  },
  'hospitals': {
    'layer': 'hospitals',
    'data_version': 1,
    'items': [
      _place('h-far', 35.0, 10.0),
      _place('h-near', 36.79, 10.19, phone: '71000000'),
    ],
  },
};

void main() {
  group('distances', () {
    test('haversine, nearest order and formatting', () {
      // Tunis → Sfax is about 230 km.
      expect(distanceM(36.8, 10.18, 34.74, 10.76) / 1000, closeTo(235, 10));
      final places = [
        for (final p in _packages['hospitals']!['items']! as List)
          Place.fromJson(p as Map<String, Object?>),
      ];
      final near = nearest(places, const GeoPoint(lat: 36.8, lon: 10.18));
      expect(near.map((n) => n.place.id), ['h-near', 'h-far']);
      expect(formatDistance(853), '850 m');
      expect(formatDistance(1520), '1.5 km');
      expect(formatDistance(23456), '23 km');
      expect(routeUri(places.first).scheme, 'geo');
    });
  });

  group('offline copies (ETag)', () {
    late FakeAdapter adapter;
    late List<Map<String, Object?>> layers;
    var layersEtag = '"layers-1"';

    setUp(() {
      layers = [
        _layer('civil_protection'),
        _layer('hospitals', toVerify: true, simulated: true),
      ];
      layersEtag = '"layers-1"';
      adapter = FakeAdapter((r) {
        if (r.path == '/api/v1/layers') {
          if (r.header('If-None-Match') == layersEtag) {
            return FakeResponse(304, headers: {'ETag': layersEtag});
          }
          return FakeResponse(
            200,
            json: {'items': layers},
            headers: {'ETag': layersEtag},
          );
        }
        final m = RegExp(r'^/api/v1/layers/(\w+)/package$').firstMatch(r.path);
        if (m != null) {
          final etag = '"${m[1]}-${r.uri.queryParameters['lang']}"';
          if (r.header('If-None-Match') == etag) {
            return FakeResponse(304, headers: {'ETag': etag});
          }
          return FakeResponse(
            200,
            json: _packages[m[1]],
            headers: {'ETag': etag},
          );
        }
        return const FakeResponse(404, json: {'detail': 'not_found'});
      });
    });

    test(
      'download, 304 when unchanged, forget a layer no longer public',
      () async {
        final store = MemoryPlacesStore();
        final c = await phase5Container(
          adapter,
          overrides: [placesStoreProvider.overrideWithValue(store)],
        );
        final repo = c.read(placesRepositoryProvider);
        final first = await repo.refresh(await repo.local(), 'ar');
        expect(first.layers.map((l) => l.key), [
          'civil_protection',
          'hospitals',
        ]);
        expect(first.packages['hospitals']!.places, hasLength(2));

        // A new start reads everything back without network.
        final local = await repo.local();
        expect(local.packages['civil_protection']!.places.first.phone, '198');
        expect(local.layers.last.toVerify, isTrue);
        expect(local.layers.last.simulated, isTrue);

        // Unchanged: every request is conditional and answered 304.
        adapter.requests.clear();
        await repo.refresh(local, 'ar');
        expect(adapter.requests.map((r) => r.header('If-None-Match')), [
          '"layers-1"',
          '"civil_protection-ar"',
          '"hospitals-ar"',
        ]);

        // Another language asks again without ETag.
        adapter.requests.clear();
        await repo.refresh(local, 'fr');
        expect(adapter.requests.last.header('If-None-Match'), isNull);

        // The hospitals layer is withdrawn from the public.
        layers = [_layer('civil_protection')];
        layersEtag = '"layers-2"';
        final after = await repo.refresh(await repo.local(), 'fr');
        expect(after.layers.map((l) => l.key), ['civil_protection']);
        expect(store.docs.containsKey('layer-hospitals'), isFalse);
      },
    );

    test('unreadable copy starts empty', () async {
      final store = MemoryPlacesStore()..docs['layers'] = '{oops';
      final c = await phase5Container(
        adapter,
        overrides: [placesStoreProvider.overrideWithValue(store)],
      );
      expect((await c.read(placesRepositoryProvider).local()).isEmpty, isTrue);
    });
  });

  testWidgets('hub → nearest: coordinates, nearest places, call and route', (
    tester,
  ) async {
    final opened = <Uri>[];
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String;
        }
        return null;
      },
    );
    final h = await pumpApp(
      tester,
      prefs: {...languageAndIntroDone, 'settings.locale': 'en'},
      opened: opened,
      api: (r) {
        if (r.path == '/api/v1/layers') {
          return FakeResponse(
            200,
            json: {
              'items': [
                _layer('civil_protection'),
                _layer('hospitals', toVerify: true, simulated: true),
              ],
            },
          );
        }
        final m = RegExp(r'^/api/v1/layers/(\w+)/package$').firstMatch(r.path);
        if (m != null) return FakeResponse(200, json: _packages[m[1]]);
        return const FakeResponse(404, json: {'detail': 'not_found'});
      },
      overrides: [placesStoreProvider.overrideWithValue(MemoryPlacesStore())],
    );
    await tester.tap(find.byKey(const Key('emergency-numbers-action')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('hub-nearest')), 200);
    await tester.ensureVisible(find.byKey(const Key('hub-nearest')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('hub-nearest')));
    await tester.pumpAndSettle();

    expect(find.text('36.80000, 10.18000'), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('nearest-copy')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nearest-copy')));
    await tester.pumpAndSettle();
    expect(copied, '36.80000, 10.18000');

    expect(find.byKey(const Key('to-verify-hospitals')), findsOneWidget);
    // Approximate trial places: amber banner and [SIM] chip on their layer only.
    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    expect(find.byKey(const Key('sim-layer-hospitals')), findsOneWidget);
    expect(find.byKey(const Key('sim-layer-civil_protection')), findsNothing);
    await tester.scrollUntilVisible(
      find.byKey(const Key('call-h-near')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(find.byKey(const Key('route-h-near')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('call-h-near')));
    await tester.pumpAndSettle();
    expect(h.dialled.last, Uri.parse('tel:71000000'));
    await tester.tap(find.byKey(const Key('route-h-near')));
    await tester.pumpAndSettle();
    expect(opened.single.scheme, 'geo');

    // Turning a layer off hides it, and is remembered.
    await tester.scrollUntilVisible(
      find.byKey(const Key('layer-chip-hospitals')),
      -200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(find.byKey(const Key('layer-chip-hospitals')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('layer-chip-hospitals')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('nearest-layer-hospitals')), findsNothing);
    // No simulated layer shown any more: no banner.
    expect(find.byKey(const Key('sim-banner')), findsNothing);
    await unmountApp(tester);
  });

  test('turned-off layers are kept in the preferences', () async {
    final c = await phase5Container(
      FakeAdapter((_) => const FakeResponse(404)),
    );
    await c.read(placesOffProvider.notifier).toggle('hospitals');
    expect(prefsOf(c).placesOff, ['hospitals']);
    await c.read(placesOffProvider.notifier).toggle('hospitals');
    expect(prefsOf(c).placesOff, isEmpty);
  });
}
