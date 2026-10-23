// covers: phase B1 emergency hub (docs/phase-b/design.md §2bis): topics and items kept offline
// with the ETag, hidden content removed at refresh, [SIM] banner until medical validation.
import 'dart:convert';
import 'dart:io';

import 'package:ehimaya/features/guide/guide_models.dart';
import 'package:ehimaya/features/guide/guide_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

Map<String, Object?> _text(String title, {List<String> call = const []}) => {
  'title': title,
  'call': call,
  'steps': ['Step one $title', 'Step two $title'],
  'dont': ['Never $title'],
};

Map<String, Object?> guideJson({
  int revision = 3,
  bool validated = false,
  bool withBurns = true,
}) => {
  'revision': revision,
  'topics': [
    {
      'id': 't1',
      'key': 'fire',
      'title': {'ar': 'الحرائق', 'fr': 'Incendies', 'en': 'Fires'},
      'icon': 'fire',
      'colour': '#C62828',
      'items': [
        {
          'id': 'i1',
          'content': {
            'ar': _text('ملابس مشتعلة'),
            'fr': _text('Vêtements en feu'),
            'en': _text('Clothes on fire', call: ['Large burn']),
          },
          'call_198': true,
          'validated': validated,
        },
      ],
    },
    if (withBurns)
      {
        'id': 't2',
        'key': 'burns',
        'title': {'ar': 'الحروق', 'fr': 'Brûlures', 'en': 'Burns'},
        'icon': 'burn',
        'colour': '#BF360C',
        'items': <Object?>[],
      },
  ],
};

Future<String> _bundled() async => jsonEncode({
  'revision': 0,
  'topics': [
    {
      'id': 'seed-fire',
      'key': 'fire',
      'title': {'ar': 'حرائق', 'fr': 'Feu', 'en': 'Fire'},
      'icon': 'fire',
      'colour': '#C62828',
      'items': [
        {
          'id': 'seed-fire-0',
          'content': {'ar': _text('بذرة')},
          'call_198': true,
          'validated': false,
        },
      ],
    },
  ],
});

void main() {
  group('models', () {
    test('missing language falls back to Arabic; round trip', () {
      final g = EmergencyGuide.fromJson(guideJson());
      final item = g.topic('fire')!.items.single;
      expect(item.textFor('en').call, ['Large burn']);
      expect(
        GuideItem.fromJson({
          'id': 'x',
          'content': {'ar': _text('عربي')},
        }).textFor('fr').title,
        'عربي',
      );
      expect(EmergencyGuide.fromJson(g.toJson()).toJson(), g.toJson());
      expect(g.topic('fire')!.hasSimulated, isTrue);
      expect(guideColour('#C62828'), const Color(0xFFC62828));
      expect(guideIcon('unknown'), Icons.place);
    });
  });

  test('bundled first load: seven topics, all awaiting validation', () {
    final g = EmergencyGuide.fromJson(
      jsonDecode(File('assets/emergency_guide.json').readAsStringSync()),
    );
    expect(g.topics, hasLength(7));
    expect(g.topics.last.key, 'other');
    for (final t in g.topics) {
      expect(t.items, isNotEmpty, reason: t.key);
      for (final i in t.items) {
        expect(i.validated, isFalse);
        for (final lang in ['ar', 'fr', 'en']) {
          expect(i.content[lang]!.steps, isNotEmpty, reason: '${i.id} $lang');
        }
      }
    }
  });

  group('offline copy (ETag)', () {
    late FakeAdapter adapter;
    var etag = '"guide-3"';
    var body = guideJson();

    setUp(() {
      etag = '"guide-3"';
      body = guideJson();
      adapter = FakeAdapter((r) {
        if (r.path != '/api/v1/emergency-guide') {
          return const FakeResponse(404, json: {'detail': 'not_found'});
        }
        if (r.header('If-None-Match') == etag) {
          return FakeResponse(304, headers: {'ETag': etag});
        }
        return FakeResponse(200, json: body, headers: {'ETag': etag});
      });
    });

    test('bundled copy first, then the published guide is stored', () async {
      final c = await phase5Container(
        adapter,
        overrides: [bundledGuideLoaderProvider.overrideWithValue(_bundled)],
      );
      final first = await c.read(emergencyGuideProvider.future);
      expect(first.revision, 0);
      await pumpEventQueue();
      final shown = c.read(emergencyGuideProvider).value!;
      expect(shown.revision, 3);
      expect(shown.topics.map((t) => t.key), ['fire', 'burns']);
      expect(prefsOf(c).guideEtag, '"guide-3"');
    });

    test('unchanged guide costs a 304; a hidden topic disappears', () async {
      final c = await phase5Container(
        adapter,
        overrides: [bundledGuideLoaderProvider.overrideWithValue(_bundled)],
      );
      final repo = c.read(guideRepositoryProvider);
      await repo.refresh();
      expect(await repo.refresh(), isNull);
      expect(adapter.requests.last.header('If-None-Match'), '"guide-3"');

      // The editors hide "burns" and validate the item: new revision.
      etag = '"guide-4"';
      body = guideJson(revision: 4, validated: true, withBurns: false);
      final fresh = (await repo.refresh())!;
      expect(fresh.topics.map((t) => t.key), ['fire']);
      expect(fresh.topics.single.items.single.validated, isTrue);
      expect((await repo.local()).revision, 4);
    });

    test('corrupted copy falls back to the bundled one', () async {
      final c = await phase5Container(
        adapter,
        prefs: {'guide.json': '{not json'},
        overrides: [bundledGuideLoaderProvider.overrideWithValue(_bundled)],
      );
      expect((await c.read(guideRepositoryProvider).local()).revision, 0);
    });
  });

  testWidgets('hub → topic → item with [SIM] banner and Call 198, '
      'before the charter', (tester) async {
    final h = await pumpApp(
      tester,
      prefs: {...languageAndIntroDone, 'settings.locale': 'en'},
      api: (r) => r.path == '/api/v1/emergency-guide'
          ? FakeResponse(200, json: guideJson(), headers: {'ETag': '"g-3"'})
          : const FakeResponse(404, json: {'detail': 'not_found'}),
      overrides: [bundledGuideLoaderProvider.overrideWithValue(_bundled)],
    );
    await tester.tap(find.byKey(const Key('emergency-numbers-action')));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byKey(const Key('hub-guide')), 200);
    await tester.tap(find.byKey(const Key('hub-guide')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('guide-topic-burns')), findsOneWidget);

    await tester.tap(find.byKey(const Key('guide-topic-fire')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    expect(find.byKey(const Key('guide-sim-tag')), findsOneWidget);

    await tester.tap(find.byKey(const Key('guide-item-i1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    expect(find.byKey(const Key('guide-call')), findsOneWidget);
    expect(find.byKey(const Key('guide-steps')), findsOneWidget);
    expect(find.byKey(const Key('guide-dont')), findsOneWidget);
    await tester.tap(find.byKey(const Key('guide-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri.parse('tel:198')]);
    await unmountApp(tester);
  });
}
