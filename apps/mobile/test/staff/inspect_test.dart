import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/prevention/prevention_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import 'staff_fakes.dart';

/// `/api/v1/inspect` in memory (phase I3): registration, activation, missions, one report.
class FakeInspectServer {
  bool down = false;
  bool gone = false;
  String code = 'K7P2-QX9M';
  final registrations = <Map<String, dynamic>>[];
  final submits = <Map<String, dynamic>>[];
  final progresses = <Map<String, dynamic>>[];
  final applied = <String>{};
  final starts = <Map<String, dynamic>>[];
  String onDate = '2026-01-05';

  static const profile = {
    'axes': [
      {'key': 'staff', 'name': 'Personnel', 'weight': 40},
      {'key': 'means', 'name': 'Resources', 'weight': 35},
    ],
    'items': [
      {'key': 'st1', 'axis': 'staff', 'text': 'Roll call done', 'weight': 40},
      {'key': 'mn1', 'axis': 'means', 'text': 'Engines ready', 'weight': 35},
    ],
  };

  Map<String, dynamic> get mission => {
    'id': 'm-1',
    'ref': 'OM-2026-0007',
    'on_date': onDate,
    'at_time': '09:00:00',
    'kind': 'surprise',
    'sites': [
      {
        'id': 's-1',
        'position': 1,
        'target': 'unit',
        'unit_kind': 'guard_post',
        'unit_name': 'Poste plage nord',
        'unit_id': null,
        'room': null,
        'name': 'Poste plage nord',
        'gouvernorat_code': 61,
        'sections': <String>[],
        'inspection_id': null,
        'inspection_status': null,
      },
    ],
    'profile': profile,
  };

  FakeResponse handle(SeenRequest r) {
    if (down) return const FakeResponse.network();
    final path = r.path.replaceFirst('/api/v1/inspect', '');
    final body = r.json as Map<String, dynamic>?;
    if (gone && path != '/register' && path != '/activate') {
      return const FakeResponse(410, json: {'detail': 'account_inactive'});
    }
    switch ((r.method, path)) {
      case ('POST', '/register'):
        registrations.add(body!);
        return const FakeResponse(
          201,
          json: {'status': 'pending', 'destination': '+216 •• ••• 905'},
        );
      case ('POST', '/activate'):
        if (body!['code'] != code) {
          return const FakeResponse(
            401,
            json: {'detail': 'activation_refused'},
          );
        }
        return const FakeResponse(200, json: _tokens);
      case ('GET', '/missions'):
        return FakeResponse(200, json: [mission]);
      case ('POST', '/inspections'):
        starts.add(body!);
        return const FakeResponse(
          200,
          json: {
            'id': 'x-1',
            'site_id': 's-1',
            'status': 'in_progress',
            'profile': profile,
            'answers': <String, String>{},
            'present': null,
            'expected': null,
            'exit_seconds': null,
            'score': null,
            'verdict': null,
            'receipt': null,
          },
        );
      case ('PUT', '/inspections/x-1'):
        progresses.add(body!);
        return const FakeResponse(200, json: {});
      case ('POST', '/inspections/x-1/submit'):
        submits.add(body!);
        applied.add(body['client_id'] as String);
        return const FakeResponse(
          200,
          json: {
            'inspection_id': 'x-1',
            'receipt': 'T-20261112-01',
            'score': 88,
            'verdict': 'Ready',
            'received_at': '2026-11-12T10:00:00Z',
          },
        );
    }
    return const FakeResponse(404, json: {'detail': 'not_found'});
  }
}

const _tokens = {
  'access_token': 'insp-at',
  'expires_at': '2099-01-01T00:00:00Z',
  'refresh_token': 'insp-refresh-token-0123456789',
  'name': 'Sami Inspecteur',
  'kind': 'internal',
  'expires_on': null,
};

Future<FakeInspectServer> pumpInspector(
  WidgetTester tester, {
  MemorySecureStore? store,
  MemoryBlobStore? blobs,
}) async {
  final crew = FakeCrewServer();
  final insp = FakeInspectServer();
  final crewHandler = crew.adapter.handler;
  crew.adapter.handler = (r) =>
      r.path.startsWith('/api/v1/inspect') ? insp.handle(r) : crewHandler(r);
  await pumpStaffApp(
    tester,
    crew,
    store: store,
    inspectBlobs: blobs ?? MemoryBlobStore(),
  );
  await tester.tap(find.byKey(const Key('open-inspector')));
  await tester.pumpAndSettle();
  return insp;
}

Future<MemorySecureStore> activatedStore() async {
  final store = MemorySecureStore();
  await store.write(
    'insp_tokens_v1',
    '{"access_token":"insp-at","expires_at":"2099-01-01T00:00:00Z",'
        '"refresh_token":"insp-refresh-token-0123456789","name":"Sami Inspecteur",'
        '"kind":"internal","expires_on":null}',
  );
  return store;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final f = find.byKey(Key(key));
  await tester.scrollUntilVisible(
    f,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
  await tester.tap(f);
  await tester.pumpAndSettle();
}

Future<void> sign(WidgetTester tester, String pad) async {
  final f = find.byKey(Key(pad));
  await tester.scrollUntilVisible(
    f,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await Scrollable.ensureVisible(tester.element(f), alignment: 0.5);
  await tester.pumpAndSettle();
  await tester.drag(
    find.descendant(of: f, matching: find.byType(CustomPaint)).first,
    const Offset(120, 30),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('asks for an account, then activates the phone with the code', (
    tester,
  ) async {
    final insp = await pumpInspector(tester);
    await tester.tap(find.byKey(const Key('insp-to-register')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('insp-matricule')), '12345');
    await tester.enterText(find.byKey(const Key('insp-name')), 'Sami Ben Ali');
    await tester.enterText(find.byKey(const Key('insp-phone')), '+21620000905');
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('insp-register')));
    await tester.pumpAndSettle();
    expect(insp.registrations.single['matricule'], '12345');
    expect(insp.registrations.single['via'], 'sms');
    expect(find.byKey(const Key('insp-registered')), findsOneWidget);

    // A wrong code first, then the right one.
    await tester.enterText(find.byKey(const Key('insp-code')), 'WRONG-CODE');
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('insp-activate')));
    await tester.pumpAndSettle();
    expect(find.text('Wrong number or code.'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('insp-code')), 'k7p2-qx9m');
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('insp-activate')));
    await tester.pumpAndSettle();
    expect(find.text('My missions'), findsOneWidget);
    expect(find.text('OM-2026-0007'), findsOneWidget);
    expect(find.text('Poste plage nord'), findsOneWidget);
    expect(find.text('Guard post'), findsOneWidget);
  });

  testWidgets(
    'fills a report without network, seals it and sends it once the network is back',
    (tester) async {
      final store = await activatedStore();
      final insp = await pumpInspector(tester, store: store);
      expect(find.text('OM-2026-0007'), findsOneWidget);

      // From here the network is gone: the report opens from the order and the model on the
      // phone, and everything stays there.
      insp.down = true;
      await tester.tap(find.byKey(const Key('insp-site-s-1')));
      await tester.pumpAndSettle();
      expect(insp.starts, isEmpty);
      await tapKey(tester, 'st1-ok');
      await tapKey(tester, 'mn1-ko');
      expect(find.text('2 of 2 items answered'), findsOneWidget);
      await tester.enterText(find.byKey(const Key('insp-present')), '8');
      await tester.enterText(find.byKey(const Key('insp-expected')), '10');
      await tester.enterText(find.byKey(const Key('insp-exit')), '75');
      await tester.pumpAndSettle();
      await tapKey(tester, 'insp-to-sign');

      // A detailed recommendation needs its item and its priority.
      await tapKey(tester, 'insp-add-rec');
      await tester.tap(find.byKey(const Key('insp-rec-item')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Engines ready').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('High'));
      await tester.enterText(
        find.byKey(const Key('insp-rec-text')),
        'Service the pump',
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('insp-rec-save')));
      await tester.pumpAndSettle();
      expect(find.text('Service the pump'), findsOneWidget);

      expect(find.byKey(const Key('insp-sign-needs')), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('insp-head-name')),
        'Chef de poste',
      );
      await tester.pumpAndSettle();
      await sign(tester, 'insp-pad-inspector');
      await sign(tester, 'insp-pad-head');
      expect(find.byKey(const Key('insp-sign-needs')), findsNothing);
      await tapKey(tester, 'insp-sign');
      expect(find.byKey(const Key('insp-sign')), findsNothing);
      await tester.scrollUntilVisible(
        find.byKey(const Key('insp-sealed')),
        -300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.byKey(const Key('insp-sealed')), findsOneWidget);
      expect(
        find.text(
          'Signed and sealed on the phone; it will be sent as soon as the network is back.',
        ),
        findsOneWidget,
      );
      expect(insp.submits, isEmpty);

      // Back on the missions, the network returns and the report goes.
      await tester.pageBack();
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Waiting to send'), findsOneWidget);
      insp.down = false;
      await tester.tap(find.byKey(const Key('insp-retry')));
      await tester.pumpAndSettle();
      expect(find.text('Sent'), findsOneWidget);
      // The server recorded the arrival taken on the phone, then the report.
      expect(insp.starts.single['site_id'], 's-1');
      expect(insp.starts.single['started_at'], isNotNull);
      final sent = insp.submits.single;
      expect(sent['answers'], {'st1': 'ok', 'mn1': 'ko'});
      expect(sent['present'], 8);
      expect(sent['expected'], 10);
      expect(sent['exit_seconds'], 75);
      expect(sent['head_name'], 'Chef de poste');
      expect(sent['client_id'], isNotEmpty);
      expect(sent['inspector_signature'], isNotEmpty);
      expect(sent['head_signature'], isNotEmpty);
      expect(sent['signed_at'], isNotNull);
      expect(sent['recommendations'], [
        {
          'kind': 'detailed',
          'item_key': 'mn1',
          'text': 'Service the pump',
          'priority': 'high',
        },
      ]);
    },
  );

  testWidgets('does not open a mission before its day', (tester) async {
    final store = await activatedStore();
    final crew = FakeCrewServer();
    final insp = FakeInspectServer()..onDate = '2099-01-01';
    final crewHandler = crew.adapter.handler;
    crew.adapter.handler = (r) =>
        r.path.startsWith('/api/v1/inspect') ? insp.handle(r) : crewHandler(r);
    await pumpStaffApp(
      tester,
      crew,
      store: store,
      inspectBlobs: MemoryBlobStore(),
    );
    await tester.tap(find.byKey(const Key('open-inspector')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('insp-site-s-1')));
    await tester.pumpAndSettle();
    expect(find.text('This mission is not for today yet.'), findsOneWidget);
    expect(find.text('Roll call done'), findsNothing);
  });

  testWidgets('erases the phone when the account is closed', (tester) async {
    final store = await activatedStore();
    final crew = FakeCrewServer();
    final insp = FakeInspectServer()..gone = true;
    final crewHandler = crew.adapter.handler;
    crew.adapter.handler = (r) =>
        r.path.startsWith('/api/v1/inspect') ? insp.handle(r) : crewHandler(r);
    await pumpStaffApp(
      tester,
      crew,
      store: store,
      inspectBlobs: MemoryBlobStore(),
    );
    await tester.tap(find.byKey(const Key('open-inspector')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('insp-wiped')), findsOneWidget);
    expect(await store.read('insp_tokens_v1'), isNull);
  });
}
