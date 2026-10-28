// covers: phase L1b (docs/phase-l/design-l1b-coastal.md): the beaches' colour and reasons, the
// warning near a yellow or red beach computed on the phone, the beach card and the anonymous
// "I am at this beach", and the nearest places timed on the road.
import 'dart:math';

import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/features/beaches/beach_models.dart';
import 'package:ehimaya/features/beaches/beach_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

Map<String, Object?> _beach(
  String id,
  double lat,
  double lon,
  String level, {
  List<Map<String, Object?>> factors = const [],
}) => {
  'id': id,
  'name': 'Beach $id',
  'lat': lat,
  'lon': lon,
  'gouvernorat_code': 11,
  'level': level,
  'score': level == 'red' ? 75 : 10,
  'factors': factors,
  'wave_height_m': 2.8,
  'sea_temp_c': 24.1,
  'current_kmh': 2.4,
  'classification': 'local',
  'guarded': false,
  'crowd': null,
  'present': null,
};

/// The fake location is Tunis centre, 36.8, 10.18: the red beach is about 560 m away.
final _report = {
  'day': '2026-07-04',
  'computed_at': '2026-07-04T07:00:00Z',
  'simulated': true,
  'attribution': [
    '[SIM] Simulated marine weather (e-Himaya simulator), not real data',
  ],
  'warn_radius_m': 1000,
  'items': [
    _beach('far', 37.27, 9.87, 'green'),
    _beach(
      'near',
      36.805,
      10.18,
      'red',
      factors: [
        {'code': 'waves', 'points': 55, 'value': 2.8},
        {'code': 'unguarded', 'points': 10, 'value': false},
      ],
    ),
  ],
};

final _detail = {
  'beach': (_report['items']! as List<Object?>)[1],
  'days': [
    {
      'day': '2026-07-04',
      'level': 'red',
      'score': 75,
      'factors': [],
      'wave_height_m': 2.8,
      'sea_temp_c': 24.1,
    },
    {
      'day': '2026-07-05',
      'level': 'green',
      'score': 20,
      'factors': [],
      'wave_height_m': 0.4,
      'sea_temp_c': 24.3,
    },
  ],
  'card': {'classification': 'local', 'guarded': 'False', 'blue_flag': 'oui'},
  'sources': {
    'classification': {'source': 'ONTT', 'date': '2026-06-01'},
  },
  'length_m': 1200,
  'seaward_deg': 350,
  'simulated': true,
  'attribution': ['[SIM] Simulated marine weather'],
};

void main() {
  group('on the phone', () {
    final beaches = [
      for (final b in _report['items']! as List)
        BeachRisk.fromJson(b as Map<String, Object?>),
    ];
    const here = GeoPoint(lat: 36.8, lon: 10.18);

    test('nearest first, and the danger within the radius only', () {
      expect(byDistance(beaches, here).map((n) => n.beach.id), ['near', 'far']);
      expect(byDistance(beaches, null).first.beach.name, 'Beach far');
      expect(dangerNear(beaches, here, 1000)?.beach.id, 'near');
      expect(dangerNear(beaches, here, 300), isNull);
      expect(dangerNear(beaches, null, 1000), isNull);
      expect(toneOf(BeachLevel.yellow).name, 'amber');
    });

    test('yes and no in the imported files', () {
      expect(yesNo('False'), isFalse);
      expect(yesNo('oui'), isTrue);
      expect(yesNo('نعم'), isTrue);
      expect(yesNo('medium'), isNull);
    });

    test('the code of the day is kept for the day, then drawn again', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = AppPrefs(await SharedPreferences.getInstance());
      final a = await dailyToken(prefs, '2026-07-04', random: Random(1));
      expect(a, matches(RegExp(r'^[A-Za-z0-9_-]{32}$')));
      expect(await dailyToken(prefs, '2026-07-04', random: Random(2)), a);
      expect(
        await dailyToken(prefs, '2026-07-05', random: Random(2)),
        isNot(a),
      );
    });
  });

  testWidgets('hub → beaches: colours, warning by consent, card and presence', (
    tester,
  ) async {
    final h = await pumpApp(
      tester,
      prefs: {...languageAndIntroDone, 'settings.locale': 'en'},
      api: (r) => switch (r.path) {
        '/api/v1/coastal/beaches' => FakeResponse(200, json: _report),
        '/api/v1/coastal/beaches/near' => FakeResponse(200, json: _detail),
        '/api/v1/coastal/beaches/near/presence' => const FakeResponse(204),
        '/api/v1/layers' => const FakeResponse(200, json: {'items': []}),
        _ => const FakeResponse(404, json: {'detail': 'not_found'}),
      },
    );
    await tester.tap(find.byKey(const Key('emergency-numbers-action')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('hub-beaches')), 200);
    await tester.ensureVisible(find.byKey(const Key('hub-beaches')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('hub-beaches')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    // No warning before the user agrees.
    expect(find.byKey(const Key('beaches-danger')), findsNothing);
    await tester.tap(find.byKey(const Key('beaches-warn')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('beaches-danger')), findsOneWidget);
    expect(
      find.textContaining('You are 560 m from Beach near: Red: high risk'),
      findsOneWidget,
    );
    expect(find.textContaining('Waves 2.8 m · No lifeguards'), findsWidgets);

    await tester.scrollUntilVisible(
      find.byKey(const Key('beach-near')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(find.byKey(const Key('beach-near')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('beach-near')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('factor-waves')), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('card-blue_flag')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Source: ONTT, 2026-06-01'), findsOneWidget);
    Finder cell(String key, String text) => find.descendant(
      of: find.byKey(Key('card-$key')),
      matching: find.text(text),
    );
    expect(cell('guarded', 'No'), findsOneWidget); // "False" in the file
    expect(cell('blue_flag', 'Yes'), findsOneWidget); // "oui" in the file

    // "I am at this beach" only after consent, with a random code and nothing else.
    expect(find.byKey(const Key('beach-presence')), findsNothing);
    await tester.scrollUntilVisible(
      find.byKey(const Key('beach-presence-consent')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('beach-presence-consent')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('beach-presence')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('beach-presence')));
    await tester.pumpAndSettle();
    final sent = h.adapter.requests.lastWhere(
      (r) => r.path.endsWith('/presence'),
    );
    expect((sent.json! as Map).keys, ['token']);
    expect(
      find.text('Thank you, you are counted for 30 minutes.'),
      findsOneWidget,
    );
    await unmountApp(tester);
  });
}
