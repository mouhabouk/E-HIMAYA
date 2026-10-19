import 'dart:convert';

import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/http/volunteer_models.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/push/push_controller.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/features/alerts/alerts_providers.dart';
import 'package:ehimaya/features/tips/tips_providers.dart';
import 'package:ehimaya/features/volunteer/volunteer_providers.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

/// Location granted with a fixed fix, or nothing at all.
class _Location extends LocationService {
  _Location(this.fix, {this.availability = LocationAvailability.granted});

  final GeoPoint? fix;
  final LocationAvailability availability;
  int quietCalls = 0;

  @override
  Future<LocationAvailability> ensurePermission() async => availability;
  @override
  Future<GeoPoint?> current({Duration timeout = Duration.zero}) async => fix;
  @override
  Future<GeoPoint?> lastKnown() async => fix;
  @override
  Future<GeoPoint?> withoutPrompt() async {
    quietCalls++;
    return fix;
  }
}

const _sfax = GeoPoint(lat: 34.7406, lon: 10.7603, accuracyM: 12);

void main() {
  group('safety tips offline cache (ETag)', () {
    late FakeAdapter adapter;
    var etag = '"tips-3"';
    var body = tipsJson();

    setUp(() {
      etag = '"tips-3"';
      body = tipsJson();
      adapter = FakeAdapter((r) {
        if (r.path != '/api/v1/safety-tips') {
          return const FakeResponse(404, json: {'detail': 'not_found'});
        }
        if (r.header('If-None-Match') == etag) {
          return FakeResponse(304, headers: {'ETag': etag});
        }
        return FakeResponse(200, json: body, headers: {'ETag': etag});
      });
    });

    Future<String> bundled() async => jsonEncode([
      {
        'hazard': 'earthquake',
        'content': {
          'ar': {
            'title': 'زلزال',
            'do': ['احتم تحت طاولة'],
            'dont': <String>[],
          },
        },
      },
    ]);

    test('bundled copy first, then the server copy is stored', () async {
      final c = await phase5Container(
        adapter,
        overrides: [bundledTipsLoaderProvider.overrideWithValue(bundled)],
      );
      final first = await c.read(safetyTipsProvider.future);
      expect(first.items.single.textFor('ar').title, 'زلزال');
      await pumpEventQueue();
      final shown = c.read(safetyTipsProvider).value!;
      expect(shown.revision, 3);
      expect(shown.items.map((t) => t.id), ['t2', 't1']);
      // No ETag sent while nothing was stored.
      expect(adapter.requests.single.header('If-None-Match'), isNull);
      expect(prefsOf(c).tipsEtag, '"tips-3"');
    });

    test('unchanged list: 304, nothing downloaded or rewritten', () async {
      final c = await phase5Container(
        adapter,
        overrides: [bundledTipsLoaderProvider.overrideWithValue(bundled)],
      );
      final repo = c.read(tipsRepositoryProvider);
      expect(await repo.refresh(), isNotNull);
      final stored = prefsOf(c).tipsJson;
      expect(await repo.refresh(), isNull);
      expect(adapter.requests.last.header('If-None-Match'), '"tips-3"');
      expect(prefsOf(c).tipsJson, stored);
      final local = await repo.local();
      expect(local.revision, 3);
      expect(local.items[1].textFor('fr').dontItems, [
        'Ne traversez pas les oueds',
      ]);

      // A new revision replaces the copy.
      etag = '"tips-4"';
      body = tipsJson(revision: 4);
      expect((await repo.refresh())!.revision, 4);
      expect(prefsOf(c).tipsEtag, '"tips-4"');
    });

    test('offline: the stored copy, else the bundled one', () async {
      adapter.handler = (_) => const FakeResponse.network();
      final c = await phase5Container(
        adapter,
        prefs: {'tips.json': jsonEncode(tipsJson())},
        overrides: [bundledTipsLoaderProvider.overrideWithValue(bundled)],
      );
      final tips = await c.read(safetyTipsProvider.future);
      await pumpEventQueue();
      expect(c.read(safetyTipsProvider).value!.revision, 3);
      expect(tips.items, hasLength(2));

      final corrupted = await phase5Container(
        adapter,
        prefs: {'tips.json': '{not json'},
        overrides: [bundledTipsLoaderProvider.overrideWithValue(bundled)],
      );
      final fallback = await corrupted.read(tipsRepositoryProvider).local();
      expect(fallback.items.single.hazard.wire, 'earthquake');
    });
  });

  group('volunteer readiness', () {
    late FakeAdapter adapter;
    late Map<String, Object?> volunteer;
    var now = DateTime.utc(2026, 10, 19, 10);
    final locations = <Object?>[];

    setUp(() {
      now = DateTime.utc(2026, 10, 19, 10);
      locations.clear();
      volunteer = volunteerJson(
        ready: true,
        readyUntil: '2026-10-19T18:00:00Z',
      );
      adapter = FakeAdapter((r) {
        switch ((r.method, r.path)) {
          case ('GET', '/api/v1/me/volunteer'):
            return FakeResponse(200, json: volunteer);
          case ('PUT', '/api/v1/me/volunteer/location'):
            if (volunteer['ready'] != true) {
              return const FakeResponse(409, json: {'detail': 'not_ready'});
            }
            locations.add(r.json);
            return const FakeResponse(204);
          case ('POST', '/api/v1/me/volunteer/readiness'):
            final body = r.json! as Map<String, Object?>;
            volunteer = {
              ...volunteer,
              'ready': body['ready'],
              'ready_until': body['ready'] == true
                  ? '2026-10-19T${10 + (body['hours']! as int)}:00:00Z'
                  : null,
            };
            return FakeResponse(200, json: volunteer);
        }
        return const FakeResponse(404, json: {'detail': 'not_found'});
      });
    });

    test('while ready the position is sent; it stops at the end', () async {
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: _Location(_sfax),
      );
      await c.read(volunteerProvider.future);
      final tracker = c.read(readinessTrackerProvider);
      expect(await tracker.tick(), ReadinessTick.sent);
      expect(locations.single, {
        'lat': 34.7406,
        'lon': 10.7603,
        'accuracy_m': 12.0,
      });

      // ready_until passed: the server ended readiness, the app reloads and stops.
      now = DateTime.utc(2026, 10, 19, 18, 1);
      volunteer = {...volunteer, 'ready': false, 'ready_until': null};
      expect(await tracker.tick(), ReadinessTick.ended);
      expect(c.read(volunteerProvider).value!.ready, isFalse);
      expect(await tracker.tick(), ReadinessTick.idle);
      expect(locations, hasLength(1));
    });

    test(
      'ended elsewhere (409 not_ready): reloads, nothing more sent',
      () async {
        final c = await phase5Container(
          adapter,
          clock: () => now,
          location: _Location(_sfax),
        );
        await c.read(volunteerProvider.future);
        volunteer = {...volunteer, 'ready': false, 'ready_until': null};
        expect(
          await c.read(readinessTrackerProvider).tick(),
          ReadinessTick.ended,
        );
        expect(c.read(volunteerProvider).value!.ready, isFalse);
        expect(locations, isEmpty);
      },
    );

    test('no fix or outside Tunisia: skipped, readiness kept', () async {
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: _Location(const GeoPoint(lat: 48.85, lon: 2.35)),
      );
      await c.read(volunteerProvider.future);
      expect(
        await c.read(readinessTrackerProvider).tick(),
        ReadinessTick.skipped,
      );
      expect(locations, isEmpty);
    });

    test('ready on sends the position and duration; off clears it', () async {
      volunteer = volunteerJson();
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: _Location(_sfax),
      );
      await c.read(volunteerProvider.future);
      await c.read(volunteerProvider.notifier).setReady(4);
      expect(lastTo(adapter, 'POST', '/api/v1/me/volunteer/readiness')!.json, {
        'ready': true,
        'lat': 34.7406,
        'lon': 10.7603,
        'accuracy_m': 12.0,
        'hours': 4,
      });
      expect(c.read(volunteerProvider).value!.isReadyAt(now), isTrue);
      await c.read(volunteerProvider.notifier).setNotReady();
      expect(lastTo(adapter, 'POST', '/api/v1/me/volunteer/readiness')!.json, {
        'ready': false,
      });
      expect(c.read(volunteerProvider).value!.ready, isFalse);
    });

    test('ready on without location permission is refused locally', () async {
      volunteer = volunteerJson();
      final c = await phase5Container(
        adapter,
        location: _Location(
          null,
          availability: LocationAvailability.deniedForever,
        ),
      );
      await c.read(volunteerProvider.future);
      await expectLater(
        c.read(volunteerProvider.notifier).setReady(8),
        throwsA(isA<LocationUnavailable>()),
      );
      expect(lastTo(adapter, 'POST', '/api/v1/me/volunteer/readiness'), isNull);
    });

    test('never applied: null; anonymous: never asked', () async {
      adapter.handler = (_) =>
          const FakeResponse(404, json: {'detail': 'not_volunteer'});
      final c = await phase5Container(adapter);
      expect(await c.read(volunteerProvider.future), isNull);
      final anon = await phase5Container(
        FakeAdapter((_) {
          fail('no request for anonymous users');
        }),
        registered: false,
      );
      expect(await anon.read(volunteerProvider.future), isNull);
    });

    test('profile_incomplete surfaces as its contract code', () async {
      adapter.handler = (_) =>
          const FakeResponse(409, json: {'detail': 'profile_incomplete'});
      final c = await phase5Container(adapter);
      final api = c.read(apiProvider);
      await expectLater(
        api.putVolunteer(
          VolunteerInput(
            skills: {VolunteerSkill.firstAid},
            availability: VolunteerAvailability.continuous,
            periodFrom: DateTime(2026, 10, 19),
          ),
        ),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            ApiErrorCode.profileIncomplete,
          ),
        ),
      );
    });
  });

  group('alerts', () {
    test('asked for the phone position, kept for offline use', () async {
      final adapter = FakeAdapter(
        (r) => FakeResponse(
          200,
          json: [
            alertJson(),
            alertJson(
              id: 'a2',
              severity: 'low',
              expiresAt: '2026-10-19T11:00:00Z',
            ),
          ],
        ),
      );
      var now = DateTime.utc(2026, 10, 19, 10);
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: _Location(_sfax),
      );
      final alerts = await c.read(activeAlertsProvider.future);
      expect(alerts, hasLength(2));
      final request = adapter.requests.single;
      expect(request.path, '/api/v1/alerts/active');
      expect(request.uri.queryParameters, {'lat': '34.7406', 'lon': '10.7603'});
      // Public endpoint: no identity sent.
      expect(request.header('Authorization'), isNull);
      expect(c.read(highAlertsProvider).single.id, alertJson()['id']);

      // Offline later: the stored list, without what has expired since.
      now = DateTime.utc(2026, 10, 19, 12);
      adapter.handler = (_) => const FakeResponse.network();
      c.invalidate(activeAlertsProvider);
      final offline = await c.read(activeAlertsProvider.future);
      expect(offline.map((a) => a.id), [alertJson()['id']]);
    });

    test('location alerts off: profile gouvernorat instead', () async {
      final adapter = FakeAdapter((r) {
        if (r.path == '/api/v1/me/profile') {
          return const FakeResponse(200, json: {'gouvernorat_code': 61});
        }
        return const FakeResponse(200, json: []);
      });
      final location = _Location(_sfax);
      final c = await phase5Container(
        adapter,
        prefs: {'alerts.location': false},
        location: location,
      );
      await c.read(activeAlertsProvider.future);
      expect(location.quietCalls, 0);
      expect(
        lastTo(adapter, 'GET', '/api/v1/alerts/active')!.uri.queryParameters,
        {'gouvernorat_code': '61'},
      );
    });

    test('inbox pages are appended without duplicates', () async {
      final adapter = FakeAdapter((r) {
        final cursor = r.uri.queryParameters['cursor'];
        return FakeResponse(
          200,
          json: cursor == null
              ? {
                  'items': [inboxItemJson('i1'), inboxItemJson('i2')],
                  'next_cursor': 'page2',
                }
              : {
                  'items': [
                    inboxItemJson('i2'),
                    inboxItemJson('i3', kind: 'alert'),
                  ],
                  'next_cursor': null,
                },
        );
      });
      final c = await phase5Container(adapter);
      final first = await c.read(inboxProvider.future);
      expect(first.hasMore, isTrue);
      await c.read(inboxProvider.notifier).loadMore();
      final all = c.read(inboxProvider).value!;
      expect(all.items.map((i) => i.id), ['i1', 'i2', 'i3']);
      expect(all.hasMore, isFalse);
      expect(adapter.requests.last.uri.queryParameters['cursor'], 'page2');
    });
  });

  group('push', () {
    test(
      'device registered with the coarse position, then forgotten',
      () async {
        final adapter = FakeAdapter((_) => const FakeResponse(204));
        final c = await phase5Container(adapter, location: _Location(_sfax));
        final registrar = c.read(deviceRegistrarProvider);
        await registrar.register();
        final put = lastTo(adapter, 'PUT', '/api/v1/devices')!;
        expect(put.json, {
          'token': 'fcm-token-0123456789-abcdefghij',
          'platform': 'android',
          'locale': 'ar',
          'location_alerts': true,
          'lat': 34.7406,
          'lon': 10.7603,
        });
        expect(put.header('Authorization'), 'Bearer a.b.c');
        expect(prefsOf(c).pushToken, 'fcm-token-0123456789-abcdefghij');

        await registrar.unregister();
        expect(
          lastTo(
            adapter,
            'DELETE',
            '/api/v1/devices/fcm-token-0123456789-abcdefghij',
          ),
          isNotNull,
        );
        expect(prefsOf(c).pushToken, isNull);
      },
    );

    test('location alerts off: no position; anonymous: device key', () async {
      final adapter = FakeAdapter((_) => const FakeResponse(204));
      final location = _Location(_sfax);
      final c = await phase5Container(
        adapter,
        registered: false,
        prefs: {'alerts.location': false, 'settings.locale': 'fr'},
        location: location,
      );
      await c.read(deviceRegistrarProvider).register();
      final put = lastTo(adapter, 'PUT', '/api/v1/devices')!;
      expect(put.json, {
        'token': 'fcm-token-0123456789-abcdefghij',
        'platform': 'android',
        'locale': 'fr',
        'location_alerts': false,
      });
      expect(put.header('X-Device-Key'), isNotNull);
      expect(put.header('Authorization'), isNull);
      expect(location.quietCalls, 0);
    });

    test('without a token or an identity nothing is sent', () async {
      final adapter = FakeAdapter((_) => const FakeResponse(204));
      final c = await phase5Container(
        adapter,
        push: FakePushMessaging(fixedToken: null),
      );
      await c.read(deviceRegistrarProvider).register();
      await c.read(deviceRegistrarProvider).unregister();
      expect(adapter.requests, isEmpty);
    });

    test('a received push refreshes what it is about', () async {
      var calls = 0;
      final adapter = FakeAdapter((r) {
        if (r.path == '/api/v1/alerts/active') calls++;
        if (r.path == '/api/v1/me/callouts') {
          return FakeResponse(200, json: [calloutJson()]);
        }
        return const FakeResponse(200, json: []);
      });
      final c = await phase5Container(adapter);
      await c.read(activeAlertsProvider.future);
      expect(calls, 1);
      final controller = c.read(pushControllerProvider);
      controller.handleReceived(
        PushPayload.parse({'type': 'alert', 'id': 'a1'})!,
      );
      await pumpEventQueue();
      expect(calls, 2);
      final sub = c.listen(myCalloutsProvider, (_, _) {});
      addTearDown(sub.close);
      await c.read(myCalloutsProvider.future);
      controller.handleReceived(PushPayload.parse({'type': 'callout'})!);
      await c.read(myCalloutsProvider.future);
      expect(
        adapter.requests.where((r) => r.path == '/api/v1/me/callouts'),
        hasLength(2),
      );
    });
  });
}
