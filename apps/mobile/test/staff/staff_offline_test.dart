import 'dart:async';

import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/staff/mission_box.dart';
import 'package:ehimaya/staff/prevention/prevention_store.dart';
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:ehimaya/staff/staff_push.dart';
import 'package:ehimaya/staff/staff_sms.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import 'staff_fakes.dart';

/// Phase P4d (F-STF-07, docs/phase-p4/design-staff.md §9): the leader's writes without network,
/// the signed text message, the vehicle's positions and the phone's push token.
void main() {
  Future<FakeCrewServer> onShift({String status = 'ordered'}) async =>
      FakeCrewServer()
        ..shiftOpen = true
        ..missions.add(
          FakeCrewServer.mission(
            status: status,
            acknowledgedAt: status == 'ordered' ? null : '2026-10-26T09:00:10Z',
          ),
        );

  Future<void> unlock(WidgetTester tester) => enterPin(tester, '123456');

  testWidgets(
    'without network the steps are kept sealed, in order, and sent once later',
    (tester) async {
      final server = await onShift();
      final store = await signedInStore();
      await StaffVault(store).setPin('123456', 'salt');
      final blobs = MemoryBlobStore();
      await pumpStaffApp(tester, server, store: store, missionBlobs: blobs);
      await unlock(tester);
      expect(find.byKey(const Key('mission-alert')), findsOneWidget);

      // The network goes: the order is acknowledged and the team sets off all the same.
      server.down = true;
      await tester.tap(find.byKey(const Key('ack-mission')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('mission-alert')), findsNothing);
      await tester.tap(find.byKey(const Key('mission-m-1')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('step-en_route')));
      await tester.pumpAndSettle();
      expect(
        find.text('2 waiting, sent when the network is back'),
        findsOneWidget,
      );
      // Shown at once: the next step is offered.
      expect(find.byKey(const Key('step-on_scene')), findsOneWidget);
      expect(server.writes, isEmpty);

      // Nothing readable in the box: the missions and the writes are sealed.
      final sealed = String.fromCharCodes(blobs.values.values.expand((b) => b));
      expect(sealed, isNot(contains('Zaghouan')));
      expect(sealed, isNot(contains('en_route')));

      // The phone restarts, still without network: the mission and what waits are there.
      await pumpStaffApp(tester, server, store: store, missionBlobs: blobs);
      await unlock(tester);
      expect(find.byKey(const Key('staff-pending')), findsOneWidget);
      expect(find.textContaining('Waiting'), findsOneWidget);

      // The network is back: sent in order, with the phone's ids and times.
      server.down = false;
      await tester.tap(find.byKey(const Key('staff-send-now')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('staff-pending')), findsNothing);
      final sent = [
        for (final w in server.writes)
          if (w.path.startsWith('/api/v1/crew/missions/')) w,
      ];
      expect(sent.map((w) => w.path.split('/').last), ['ack', 'status']);
      final ids = {for (final w in sent) (w.json! as Map)['client_id']};
      expect(ids, hasLength(2));
      expect((sent.last.json! as Map)['device_at'], isA<String>());
      expect(server.missions.single['status'], 'en_route');
    },
  );

  testWidgets('a write the server refuses is dropped and its reason shown', (
    tester,
  ) async {
    final server = await onShift(status: 'en_route');
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await unlock(tester);
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();

    // The room cancelled the mission meanwhile: the counter is refused, nothing waits after.
    server.missions.clear();
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('staff-pending')), findsNothing);
    expect(server.writes.last.path, '/api/v1/crew/missions/m-1/status');
  });

  testWidgets('a step that waits goes by a signed text message', (
    tester,
  ) async {
    final server = await onShift(status: 'en_route');
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    final launched = <Uri>[];
    await pumpStaffApp(
      tester,
      server,
      store: store,
      launched: launched,
      smsNumber: '+216 71 000 111',
    );
    await unlock(tester);
    // The phone's key was fetched while there was network, and kept in the keystore.
    expect(await StaffVault(store).smsKey(), FakeCrewServer.smsKey);

    server.down = true;
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('staff-send-sms')));
    await tester.pumpAndSettle();

    final sms = launched.single;
    expect(sms.scheme, 'sms');
    expect(sms.path, '+21671000111');
    final body = sms.queryParameters['body']!;
    final parts = body.split(' ');
    expect(parts, hasLength(7));
    expect(parts.take(4), ['EH2', 'dev1', 'm1', 'on_scene']);
    expect(body.length, lessThanOrEqualTo(160));
    // Signed with the phone's key over the same fields as the server checks.
    final write = MissionWrite(
      missionId: 'm-1',
      action: 'status',
      body: {
        'client_id': parts[5],
        'device_at': DateTime.fromMillisecondsSinceEpoch(
          int.parse(parts[4]) * 1000,
          isUtc: true,
        ).toIso8601String(),
        'status': 'on_scene',
      },
    );
    expect(
      crewSmsBody(key: FakeCrewServer.smsKey, deviceId: 'dev-1', write: write),
      body,
    );
    // Sent by SMS: no second message, and it still goes over the internet later (applied once).
    expect(find.byKey(const Key('staff-send-sms')), findsNothing);
    expect(find.byKey(const Key('staff-pending')), findsOneWidget);
    server.down = false;
    await tester.tap(find.byKey(const Key('staff-send-now')));
    await tester.pumpAndSettle();
    final cid = (server.writes.last.json! as Map)['client_id'] as String;
    expect(cid.replaceAll('-', ''), parts[5]);
    expect(server.missions.single['status'], 'on_scene');
  });

  testWidgets('the vehicle is followed on the way, and its positions sent', (
    tester,
  ) async {
    final server = await onShift(status: 'en_route');
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    final location = _MovingLocation();
    await pumpStaffApp(tester, server, store: store, location: location);
    await unlock(tester);
    expect(location.following, isTrue);
    location.moveTo(const GeoPoint(lat: 36.79, lon: 10.17, accuracyM: 9));
    await tester.pumpAndSettle();
    // Kept, then sent with the next pass.
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();
    final points = server.positions['m-1']!;
    expect(points.first['lat'], 36.79);
    expect(points.first['accuracy_m'], 9);
  });

  testWidgets('the phone gives the server its push token', (tester) async {
    final server = await onShift(status: 'en_route');
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store, push: _FakePush());
    await unlock(tester);
    expect(server.pushToken, 'fcm-token-1');
  });

  testWidgets('a revoked phone erases the missions kept on it', (tester) async {
    final server = await onShift(status: 'en_route');
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    final blobs = MemoryBlobStore();
    await pumpStaffApp(tester, server, store: store, missionBlobs: blobs);
    await unlock(tester);
    expect(blobs.values, isNotEmpty);
    server.revoked = true;
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('step-on_scene')));
    await tester.pumpAndSettle();
    expect(blobs.values, isEmpty);
    expect(store.values[MissionBox.keyName], isNull);
  });
}

class _MovingLocation extends FakeLocationService {
  final _points = StreamController<GeoPoint>.broadcast();
  bool following = false;

  void moveTo(GeoPoint p) => _points.add(p);

  @override
  Stream<GeoPoint> follow({required String title, required String text}) {
    following = true;
    return _points.stream;
  }
}

class _FakePush implements StaffPush {
  @override
  Future<String?> start(String channelName) async => 'fcm-token-1';
  @override
  Stream<String> get onTokenRefresh => const Stream.empty();
  @override
  Stream<void> get onMission => const Stream.empty();
}
