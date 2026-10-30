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

  testWidgets('F-STF-03/04: alert, steps, path, quick buttons', (tester) async {
    final server = FakeCrewServer()
      ..shiftOpen = true
      ..missions.add(FakeCrewServer.mission());
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    final launched = <Uri>[];
    await pumpStaffApp(tester, server, store: store, launched: launched);
    await enterPin(tester, '123456');

    // The new order covers the screen until it is acknowledged.
    expect(find.byKey(const Key('mission-alert')), findsOneWidget);
    expect(find.text('Feu de forêt, route de Zaghouan km 4'), findsOneWidget);
    await tester.tap(find.byKey(const Key('ack-mission')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mission-alert')), findsNothing);
    expect(find.byKey(const Key('staff-online')), findsOneWidget);

    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('mission-card')), findsOneWidget);
    expect(find.text('High priority'), findsOneWidget);
    expect(find.byKey(const Key('mission-timeline')), findsOneWidget);
    // No number given by the room: no "reporter" button.
    expect(find.byKey(const Key('quick-reporter')), findsNothing);
    await tester.tap(find.byKey(const Key('quick-room')));
    expect(launched.last.toString(), 'tel:198');
    await tester.tap(find.byKey(const Key('quick-route')));
    expect(launched.last.queryParameters['destination'], '36.8,10.18');

    await tester.tap(find.byKey(const Key('step-en_route')));
    await tester.pumpAndSettle();
    final step = server.writes.last.json! as Map<String, dynamic>;
    expect(step['status'], 'en_route');
    expect(step['lat'], 36.8);
    // The phone stands at the incident: arrival is suggested.
    expect(find.byKey(const Key('on-scene-hint')), findsOneWidget);
    expect(find.text('You are 0 m from the scene'), findsNothing);
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('open-situation')), findsOneWidget);
    expect(find.byKey(const Key('step-left_scene')), findsOneWidget);
    expect(find.byKey(const Key('open-record')), findsOneWidget);

    // Backup is one tap away from the bottom bar.
    await tester.tap(find.byKey(const Key('alert-backup')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('backup-ladder')));
    await tester.tap(find.byKey(const Key('backup-ambulance')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-backup')));
    await tester.pumpAndSettle();
    final alert = server.writes.last;
    expect(alert.path, '/api/v1/crew/missions/m-1/alerts');
    expect(alert.json, containsPair('kind', 'backup'));
    expect((alert.json! as Map)['items'], ['ambulance', 'ladder']);
    expect(find.text('Waiting for the room'), findsOneWidget);
  });

  testWidgets('S2: the steps after the arrival, the crew and the resources', (
    tester,
  ) async {
    final server = FakeCrewServer()
      ..shiftOpen = true
      ..missions.add({
        ...FakeCrewServer.mission(
          status: 'on_scene',
          acknowledgedAt: '2026-10-26T09:00:10Z',
        ),
        'en_route_at': '2026-10-26T09:01:00Z',
        'on_scene_at': '2026-10-26T09:09:00Z',
      });
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('step-left_scene')));
    await tester.pumpAndSettle();
    final left = server.writes.last;
    expect(left.path, '/api/v1/crew/missions/m-1/milestone');
    expect(left.json, containsPair('step', 'left_scene'));
    // No one taken to hospital: the return comes first, the hospital stays at hand.
    expect(find.byKey(const Key('step-back_at_unit')), findsOneWidget);
    expect(find.byKey(const Key('step-at_hospital')), findsOneWidget);
    expect(
      find.text('Back at the unit ends the mission and frees the vehicle.'),
      findsOneWidget,
    );

    final open = find.byKey(const Key('open-record'));
    await tester.scrollUntilVisible(
      open,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(open);
    await tester.pumpAndSettle();
    expect(find.text('Crew and resources'), findsWidgets);
    await tester.tap(find.byKey(const Key('record-crew-plus')));
    await tester.tap(find.byKey(const Key('record-water_m3-plus')));
    await tester.tap(find.byKey(const Key('record-water_m3-plus')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('send-record')));
    await tester.pumpAndSettle();
    final record = server.writes.last;
    expect(record.path, '/api/v1/crew/missions/m-1/record');
    expect(
      record.json,
      containsPair('crew_count', 6),
    ); // the shift's 5, plus one
    expect((record.json! as Map)['consumables'], {'water_m3': 2});

    // Free on the way back: the vehicle can be sent again, the return stays to be given.
    final free = find.byKey(const Key('step-available'));
    await tester.scrollUntilVisible(
      free,
      -200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(free);
    await tester.pumpAndSettle();
    expect(server.writes.last.json, containsPair('step', 'available'));
    expect(server.missions.single['status'], 'released');
    expect(find.byKey(const Key('step-available')), findsNothing);
    expect(find.byKey(const Key('step-at_hospital')), findsNothing);
    expect(find.text('Free on the way back'), findsOneWidget);

    final back = find.byKey(const Key('step-back_at_unit'));
    await tester.tap(back);
    await tester.pumpAndSettle();
    expect(server.writes.last.json, containsPair('step', 'back_at_unit'));
    expect(server.missions.single['status'], 'released');
    expect(find.byKey(const Key('step-back_at_unit')), findsNothing);
    expect(find.text('Back at the unit'), findsOneWidget);
  });

  testWidgets('situation report, counters, attachments, transport, template', (
    tester,
  ) async {
    final server = FakeCrewServer()
      ..shiftOpen = true
      ..missions.add(
        FakeCrewServer.mission(
          status: 'on_scene',
          acknowledgedAt: '2026-10-26T09:00:10Z',
        ),
      );
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('open-situation')));
    await tester.pumpAndSettle();
    // The room's type is offered as confirmed: nothing to type, three taps.
    expect(find.text('Confirmed: Fire'), findsOneWidget);
    await tester.tap(find.byKey(const Key('type-confirmed')));
    await tester.tap(find.byKey(const Key('severity-3')));
    await tester.tap(find.byKey(const Key('backup-yes')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('backup-extrication')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-situation')));
    await tester.pumpAndSettle();
    final report = server.writes.last;
    expect(report.path, '/api/v1/crew/missions/m-1/situation');
    final body = report.json! as Map<String, dynamic>;
    expect(body['category'], 'fire');
    expect(body['severity'], 3);
    expect(body['backup_needed'], isTrue);
    expect(body['backup_kinds'], ['extrication']);
    expect(find.byKey(const Key('situation-last')), findsOneWidget);

    await tester.scrollUntilVisible(
      find.byKey(const Key('injured_serious-plus')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    for (var i = 0; i < 2; i++) {
      await tester.tap(find.byKey(const Key('injured_light-plus')));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.byKey(const Key('injured_serious-plus')));
    await tester.pumpAndSettle();
    expect(
      tester.widget<Text>(find.byKey(const Key('injured_light-value'))).data,
      '2',
    );
    expect((server.writes.last.json! as Map)['injured_serious'], 1);

    await tester.scrollUntilVisible(
      find.byKey(const Key('attach-photo')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('attach-photo')));
    await tester.pumpAndSettle();
    final photo = server.writes.last;
    expect(photo.path, '/api/v1/crew/missions/m-1/attachments');
    expect(photo.uri.queryParameters['kind'], 'photo');
    expect(photo.uri.queryParameters['client_id'], isNotEmpty);
    expect(photo.header('content-type'), 'image/jpeg');
    expect(photo.body, [0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3]);
    expect(find.text('Photo (1)'), findsOneWidget);

    await tester.tap(find.byKey(const Key('attach-voice')));
    await tester.pumpAndSettle();
    expect(server.writes.last.uri.queryParameters['duration_s'], '7.5');
    expect(find.text('Voice note (1)'), findsOneWidget);

    await tester.tap(find.byKey(const Key('attach-text')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('note-text')), 'Roof unsafe');
    await tester.tap(find.byKey(const Key('send-note')));
    await tester.pumpAndSettle();
    expect(server.writes.last.json, containsPair('body', 'Roof unsafe'));

    final ids = {
      for (final w in server.writes)
        w.uri.queryParameters['client_id'] ??
            (w.json! as Map<String, dynamic>)['client_id'],
    };
    expect(ids, hasLength(server.writes.length));

    // Transport: a hospital of the map, no name typed.
    await tester.tap(find.byKey(const Key('open-transport')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('triage-red')));
    await tester.tap(find.byKey(const Key('age-under_12')));
    await tester.tap(find.byKey(const Key('hospital-h-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-transport')));
    await tester.pumpAndSettle();
    final t = server.writes.last.json! as Map<String, dynamic>;
    expect(t, containsPair('triage', 'red'));
    expect(t, containsPair('age_band', 'under_12'));
    expect(t, containsPair('sex', 'unknown'));
    expect(t, containsPair('hospital_ref', 'h-1'));
    expect(t.containsKey('hospital'), isFalse);
    expect(find.text('Transported (1)'), findsOneWidget);
    expect(find.textContaining('Hôpital Charles Nicolle ·'), findsWidgets);

    // "Other": the only typed hospital.
    await tester.tap(find.byKey(const Key('triage-green')));
    await tester.tap(find.byKey(const Key('hospital-other')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('hospital')), 'Clinique X');
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-transport')));
    await tester.pumpAndSettle();
    expect(server.writes.last.json, containsPair('hospital', 'Clinique X'));
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.pageBack();
    await tester.pumpAndSettle();

    // Detailed report from the template: taps only.
    await tester.scrollUntilVisible(
      find.byKey(const Key('open-detailed')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('open-detailed')));
    await tester.pumpAndSettle();
    expect(find.textContaining('[SIM]'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('send-detailed')))
          .onPressed,
      isNull,
    );
    await tester.tap(find.byKey(const Key('field-place-forest')));
    await tester.tap(find.byKey(const Key('field-spread_risk-yes')));
    await tester.tap(find.byKey(const Key('field-area_ha-plus')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('field-area_ha-plus')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('send-detailed')));
    await tester.pumpAndSettle();
    final detailed = server.writes.last.json! as Map<String, dynamic>;
    expect(detailed['template_id'], 'tpl-fire');
    expect(detailed['answers'], {
      'place': 'forest',
      'spread_risk': true,
      'area_ha': 2,
    });
    expect(find.textContaining('template v1'), findsOneWidget);
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
