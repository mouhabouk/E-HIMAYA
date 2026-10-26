import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:ehimaya/staff/staff_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'staff_fakes.dart';

void main() {
  testWidgets('F-STF-01/02: device sign-in, PIN, then the shift', (
    tester,
  ) async {
    final server = FakeCrewServer();
    final store = MemorySecureStore();
    final launched = <Uri>[];
    await pumpStaffApp(tester, server, store: store, launched: launched);

    await tester.tap(find.byKey(const Key('staff-sign-in')));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('WXYZ-ABCD'), findsOneWidget);
    await tester.tap(find.byKey(const Key('staff-open-browser')));
    expect(launched.single.queryParameters['user_code'], 'WXYZ-ABCD');

    // One "pending" answer, then the grant; the phone registers itself.
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(store.values['staff_device_v1'], 'dev-1');
    expect(find.text('Choose a 6-digit PIN'), findsOneWidget);
    final register = server.writes.single;
    expect(register.header('authorization'), 'Bearer at-1');
    expect(register.header('x-staff-device'), isNull);

    await enterPin(tester, '123456');
    await enterPin(tester, '654321');
    expect(find.text('The two PINs differ. Start again.'), findsOneWidget);
    await enterPin(tester, '123456');
    await enterPin(tester, '123456');
    expect(store.values['staff_pin_v1'], isNot(contains('123456')));

    expect(find.text('Start of shift'), findsOneWidget);
    expect(find.text('Hello Sami Ben Ali'), findsOneWidget);
    await tester.tap(find.byKey(const Key('vehicle-v-1')));
    await tester.tap(find.byKey(const Key('crew-plus')));
    await tester.pump();
    expect(find.byKey(const Key('crew-size')), findsOneWidget);
    await tester.tap(find.byKey(const Key('start-shift')));
    await tester.pumpAndSettle();

    final shift = server.writes.last;
    expect(shift.path, '/api/v1/crew/shifts');
    expect(shift.header('x-staff-device'), 'dev-1');
    final body = shift.json! as Map<String, dynamic>;
    expect(body['crew_size'], 5);
    expect(body['resource_id'], 'v-1');
    expect(body['client_id'], isA<String>());
    expect(find.byKey(const Key('no-missions')), findsOneWidget);
  });

  testWidgets('F-STF-03/04: alert, steps, first report and casualties', (
    tester,
  ) async {
    final server = FakeCrewServer()
      ..shiftOpen = true
      ..missions.add(FakeCrewServer.mission());
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');

    // The new order covers the screen until it is acknowledged.
    expect(find.byKey(const Key('mission-alert')), findsOneWidget);
    expect(find.text('Feu de forêt, route de Zaghouan km 4'), findsOneWidget);
    await tester.tap(find.byKey(const Key('ack-mission')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mission-alert')), findsNothing);

    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('step-en_route')));
    await tester.pumpAndSettle();
    final step = server.writes.last.json! as Map<String, dynamic>;
    expect(step['status'], 'en_route');
    expect(step['lat'], 36.8);
    // The phone stands at the incident: arrival is suggested.
    expect(find.byKey(const Key('on-scene-hint')), findsOneWidget);
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('open-first-report')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('severity-3')));
    await tester.tap(find.byKey(const Key('backup-needed')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-first-report')));
    await tester.pumpAndSettle();
    final report = server.writes.last.json! as Map<String, dynamic>;
    expect(report['category'], 'fire');
    expect(report['severity'], 3);
    expect(report['backup_needed'], isTrue);
    expect(find.text('3 · Serious'), findsOneWidget);

    await tester.tap(find.byKey(const Key('open-casualties')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('injured-plus')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('injured-plus')));
    await tester.pumpAndSettle();
    expect(
      tester.widget<Text>(find.byKey(const Key('injured-value'))).data,
      '2',
    );
    final ids = {
      for (final w in server.writes)
        (w.json! as Map<String, dynamic>)['client_id'],
    };
    expect(ids, hasLength(server.writes.length));

    await tester.tap(find.byKey(const Key('add-transport')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('triage-red')));
    await tester.tap(find.byKey(const Key('age-child')));
    await tester.enterText(
      find.byKey(const Key('hospital')),
      'Hôpital Charles Nicolle',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-transport')));
    await tester.pumpAndSettle();
    final t = server.writes.last.json! as Map<String, dynamic>;
    expect(t, containsPair('triage', 'red'));
    expect(t, containsPair('age_band', 'child'));
    expect(t, containsPair('sex', 'unknown'));
    expect(find.textContaining('Hôpital Charles Nicolle'), findsOneWidget);
  });

  testWidgets(
    'the PIN is asked after five minutes away; five wrong PINs wipe',
    (tester) async {
      final server = FakeCrewServer()..shiftOpen = true;
      final store = await signedInStore();
      await StaffVault(store).setPin('123456', 'salt');
      final clock = TestClock();
      await pumpStaffApp(tester, server, store: store, clock: clock);
      await enterPin(tester, '123456');
      expect(find.byKey(const Key('no-missions')), findsOneWidget);

      final binding = tester.binding;
      binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      clock.now = clock.now.add(const Duration(minutes: 2));
      binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('no-missions')), findsOneWidget);

      binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      clock.now = clock.now.add(const Duration(minutes: 6));
      binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(find.text('Enter your PIN'), findsOneWidget);

      for (var i = 0; i < 4; i++) {
        await enterPin(tester, '000000');
      }
      expect(find.text('Wrong PIN. 1 tries left.'), findsOneWidget);
      await enterPin(tester, '000000');
      expect(find.byKey(const Key('staff-signout-reason')), findsOneWidget);
      expect(store.values, isEmpty);
    },
  );

  testWidgets('remote wipe: a revoked phone erases everything', (tester) async {
    final server = FakeCrewServer()..shiftOpen = true;
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');

    server.revoked = true;
    await tester.pump(const Duration(seconds: 15));
    await tester.pumpAndSettle();
    expect(
      find.text(
        'This phone was withdrawn from the team leaders\' phones. Its data was erased.',
      ),
      findsOneWidget,
    );
    expect(store.values, isEmpty);
  });

  testWidgets('an expired token is refreshed; a refused refresh signs out', (
    tester,
  ) async {
    final server = FakeCrewServer()..shiftOpen = true;
    final store = await signedInStore(expires: DateTime.utc(2000));
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');
    expect(server.refreshes, 1);
    expect(store.values['staff_tokens_v1'], contains('at-2'));
    expect(server.adapter.requests.last.header('authorization'), 'Bearer at-2');

    await store.write(
      'staff_tokens_v1',
      '{"a":"at-2","r":"rt-2","e":"2000-01-01T00:00:00.000Z"}',
    );
    server.refuseRefresh = true;
    await tester.pump(const Duration(seconds: 15));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('staff-sign-in')), findsOneWidget);
    expect(store.values, isEmpty);
  });

  test('the PIN is stored salted, never in clear', () async {
    final store = MemorySecureStore();
    final vault = StaffVault(store);
    await vault.setPin('123456', 'aa');
    final a = store.values['staff_pin_v1']!;
    await vault.setPin('123456', 'bb');
    final b = store.values['staff_pin_v1']!;
    expect(a, isNot(b));
    expect(a, isNot(contains('123456')));
    expect(await vault.checkPin('123456'), isTrue);
    expect(await vault.checkPin('123457'), isFalse);
    expect(await vault.failures(), 1);
  });

  test('distance between two points', () {
    expect(
      distanceM(
        const GeoPoint(lat: 36.8, lon: 10.18),
        const GeoPoint(lat: 36.801, lon: 10.18),
      ).round(),
      inInclusiveRange(110, 112),
    );
  });
}
