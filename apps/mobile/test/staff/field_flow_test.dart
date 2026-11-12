import 'dart:io';

import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'staff_fakes.dart';

/// Phase F (docs/phase-f/design-f.md): the agent's activation with a code, the charter, the
/// round button with its undo, the nature, «بدون تدخل», the toll, the spoken report, the mission
/// opened from the field and the crew who only read.
void main() {
  Future<FakeCrewServer> onMission({
    String status = 'on_scene',
    Map<String, dynamic> extra = const {},
  }) async => FakeCrewServer()
    ..shiftOpen = true
    ..missions.add({
      ...FakeCrewServer.mission(
        status: status,
        acknowledgedAt: '2026-10-26T09:00:10Z',
      ),
      'en_route_at': '2026-10-26T09:01:00Z',
      if (status == 'on_scene') 'on_scene_at': '2026-10-26T09:09:00Z',
      ...extra,
    });

  Future<void> openMission(
    WidgetTester tester,
    FakeCrewServer server, {
    MemorySecureStore? store,
  }) async {
    final s = store ?? await signedInStore();
    await StaffVault(s).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: s);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();
  }

  testWidgets(
    'an agent activates the phone with a code, sets a PIN, then accepts the charter',
    (tester) async {
      final server = FakeCrewServer()..roles = ['field_agent'];
      final store = MemorySecureStore();
      await pumpStaffApp(tester, server, store: store);

      // A wrong code is refused and said so.
      await tester.enterText(
        find.byKey(const Key('activation-matricule')),
        'M1234',
      );
      await tester.enterText(
        find.byKey(const Key('activation-code')),
        'WXYZ-0000',
      );
      await reveal(tester, 'activation-submit');
      await tester.tap(find.byKey(const Key('activation-submit')));
      await tester.pumpAndSettle();
      expect(find.text('Wrong professional number or code.'), findsOneWidget);
      expect(store.values['staff_tokens_v1'], isNull);

      await tester.enterText(
        find.byKey(const Key('activation-code')),
        'ABCD-EFGH',
      );
      await tester.tap(find.byKey(const Key('activation-submit')));
      await tester.pumpAndSettle();
      expect(store.values['staff_device_v1'], isNotNull);
      expect(store.values['staff_tokens_v1'], contains('"f":true'));
      expect(find.text('Choose a 6-digit PIN'), findsOneWidget);
      await enterPin(tester, '123456');
      await enterPin(tester, '123456');

      // The charter comes before anything else; accepting needs the boxes ticked.
      expect(find.text("Agent's charter"), findsOneWidget);
      await reveal(tester, 'charter-accept');
      await tester.tap(find.byKey(const Key('charter-accept')));
      await tester.pumpAndSettle();
      expect(server.charterAccepted, isFalse);
      await reveal(tester, 'charter-read');
      await tester.tap(find.byKey(const Key('charter-read')));
      await tester.tap(find.byKey(const Key('charter-sms')));
      await tester.pumpAndSettle();
      // Both consents are needed: one missing, the button stays off.
      await reveal(tester, 'charter-accept');
      await tester.tap(find.byKey(const Key('charter-accept')));
      await tester.pumpAndSettle();
      expect(server.charterAccepted, isFalse);
      await reveal(tester, 'charter-location');
      await tester.tap(find.byKey(const Key('charter-location')));
      await tester.pumpAndSettle();
      await reveal(tester, 'charter-accept');
      await tester.tap(find.byKey(const Key('charter-accept')));
      await tester.pumpAndSettle();
      final charter = server.writes.lastWhere(
        (w) => w.path.endsWith('/charter'),
      );
      expect(charter.json, {
        'version': '2026.1',
        'sms': true,
        'location': true,
      });
      expect(server.charterAccepted, isTrue);
      expect(find.text("Agent's charter"), findsNothing);
      // An agent of the crew waits for the leader's shift and records nothing.
      expect(find.byKey(const Key('agent-waiting')), findsOneWidget);
    },
  );

  testWidgets(
    'a disabled agent phone erases itself when its token is renewed',
    (tester) async {
      final server = FakeCrewServer()
        ..roles = ['field_agent']
        ..activatedAgent = true
        ..fieldRevoked = true;
      final store = MemorySecureStore();
      await store.write(
        'staff_tokens_v1',
        '{"a":"at-f1","r":"rf-1","e":"2020-01-01T00:00:00.000Z","f":true}',
      );
      await store.write('staff_device_v1', 'dev-1');
      await StaffVault(store).setPin('123456', 'salt');
      await pumpStaffApp(tester, server, store: store);
      await enterPin(tester, '123456');
      expect(server.fieldRefreshes, greaterThan(0));
      expect(store.values['staff_tokens_v1'], isNull);
      expect(store.values['staff_pin_v1'], isNull);
    },
  );

  testWidgets(
    'the round button waits for the hold, and the step can be undone',
    (tester) async {
      final server = await onMission(status: 'acknowledged')
        ..undoSeconds = 10;
      await openMission(tester, server);

      // A short press records nothing.
      await reveal(tester, 'step-en_route');
      final g = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('step-en_route'))),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));
      await g.up();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('undo-bar')), findsNothing);

      // Held: the step waits ten seconds for «تراجع»; undone, nothing is sent.
      await holdStep(tester, 'en_route');
      expect(find.byKey(const Key('undo-bar')), findsOneWidget);
      expect(find.byKey(const Key('step-en_route')), findsNothing);
      await tester.tap(find.byKey(const Key('undo-step')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('undo-bar')), findsNothing);
      expect(server.writes.where((w) => w.path.endsWith('/status')), isEmpty);

      // Held again and left: sent after the window, with the time of the press.
      await holdStep(tester, 'en_route');
      await tester.pump(const Duration(seconds: 11));
      await tester.pumpAndSettle();
      final sent = server.writes.last;
      expect(sent.path, '/api/v1/crew/missions/m-1/status');
      expect(sent.json, containsPair('status', 'en_route'));
      expect(find.byKey(const Key('undo-bar')), findsNothing);
      expect(
        find.byKey(const Key('step-on_scene'), skipOffstage: false),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'the leader corrects the nature, then ends without intervention',
    (tester) async {
      final server = await onMission();
      await openMission(tester, server);

      await reveal(tester, 'nature-flood');
      await tester.tap(find.byKey(const Key('nature-flood')));
      await tester.pumpAndSettle();
      expect(server.writes.last.path, '/api/v1/crew/missions/m-1/nature');
      expect(server.writes.last.json, containsPair('nature', 'flood'));

      await reveal(tester, 'flow-no-intervention');
      await tester.tap(find.byKey(const Key('flow-no-intervention')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('no-int-reason-false_alarm')));
      await tester.pumpAndSettle();
      // The second confirmation: cancelled, nothing is sent.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(server.writes.last.path, endsWith('/nature'));

      await reveal(tester, 'flow-no-intervention');
      await tester.tap(find.byKey(const Key('flow-no-intervention')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('no-int-reason-false_alarm')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('no-int-confirm')));
      await tester.pumpAndSettle();
      final ended = server.writes.last;
      expect(ended.path, '/api/v1/crew/missions/m-1/no-intervention');
      expect(ended.json, containsPair('reason', 'false_alarm'));

      // The toll follows at once: the damage, and the spoken description corrected.
      expect(find.byKey(const Key('toll-send')), findsOneWidget);
      await tester.tap(find.byKey(const Key('damage-minor')));
      await tester.pumpAndSettle();
      await reveal(tester, 'spoken-mic');
      await tester.tap(find.byKey(const Key('spoken-mic')));
      await tester.pumpAndSettle();
      expect(server.writes.last.path, '/api/v1/crew/missions/m-1/voice');
      expect(find.text('تم اخماد الحريق'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('spoken-text')),
        'تم اخماد الحريق قبل وصولنا',
      );
      await reveal(tester, 'toll-send');
      await tester.tap(find.byKey(const Key('toll-send')));
      await tester.pumpAndSettle();
      final toll = server.writes.last;
      expect(toll.path, '/api/v1/crew/missions/m-1/toll');
      expect(toll.json, containsPair('damage', 'minor'));
      expect(
        toll.json,
        containsPair('description', 'تم اخماد الحريق قبل وصولنا'),
      );
      expect(toll.json, containsPair('voice_id', 'v-1'));
    },
  );

  testWidgets('the intervention report is spoken, transcribed and corrected', (
    tester,
  ) async {
    final server = await onMission();
    await openMission(tester, server);
    await reveal(tester, 'open-report');
    await tester.tap(find.byKey(const Key('open-report')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('spoken-mic')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('spoken-text')),
      'محضر: تم اخماد الحريق وتأمين المكان',
    );
    await reveal(tester, 'report-send');
    await tester.tap(find.byKey(const Key('report-send')));
    await tester.pumpAndSettle();
    final report = server.writes.last;
    expect(report.path, '/api/v1/crew/missions/m-1/report');
    expect(
      report.json,
      containsPair('text', 'محضر: تم اخماد الحريق وتأمين المكان'),
    );
    expect(report.json, containsPair('voice_id', 'v-1'));
    expect(server.missions.single['intervention_report'], isNotNull);
  });

  testWidgets(
    'a spoken word at every step: heard, tidied, corrected, sent under the step',
    (tester) async {
      final server = await onMission(status: 'en_route');
      await openMission(tester, server);
      await reveal(tester, 'open-stage-message');
      await tester.tap(find.byKey(const Key('open-stage-message')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('stage-mic')));
      await tester.pumpAndSettle();
      expect(server.writes.last.path, '/api/v1/crew/missions/m-1/stage-voice');
      expect(find.text('امم الدخان كثيف كثيف'), findsOneWidget);
      expect(find.text('الدخان كثيف.'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('stage-text')),
        'الدخان كثيف. الطريق مغلقة، نسلك الطريق الثانوية.',
      );
      await reveal(tester, 'stage-send');
      await tester.tap(find.byKey(const Key('stage-send')));
      await tester.pumpAndSettle();
      final sent = server.writes.last;
      expect(sent.path, '/api/v1/crew/missions/m-1/stage-message');
      expect(sent.json, containsPair('voice_id', 'v-2'));
      expect(
        sent.json,
        containsPair(
          'text',
          'الدخان كثيف. الطريق مغلقة، نسلك الطريق الثانوية.',
        ),
      );
      expect(server.missions.single['attachments'], hasLength(1));
    },
  );

  testWidgets('no spoken word before leaving the unit', (tester) async {
    final server = await onMission(
      status: 'ordered',
      extra: {'en_route_at': null},
    );
    await openMission(tester, server);
    expect(find.byKey(const Key('open-stage-message')), findsNothing);
  });

  testWidgets('the point the room picked on the map is shown and copied', (
    tester,
  ) async {
    final server = await onMission(
      extra: {
        'target': {'lat': 36.81234, 'lon': 10.17654},
        'target_note': 'Entrée nord',
      },
    );
    await openMission(tester, server);
    await reveal(tester, 'mission-point');
    expect(find.text('Entrée nord'), findsOneWidget);
    expect(find.textContaining('36.81234'), findsWidgets);
  });

  testWidgets('a crew agent reads the mission and cannot record it', (
    tester,
  ) async {
    final server = await onMission()
      ..roles = ['field_agent']
      ..activatedAgent = true;
    await openMission(tester, server);
    expect(find.byKey(const Key('read-only')), findsOneWidget);
    expect(
      find.byKey(const Key('step-left_scene'), skipOffstage: false),
      findsNothing,
    );
    expect(
      find.byKey(const Key('open-toll'), skipOffstage: false),
      findsNothing,
    );
    expect(find.byKey(const Key('alert-backup')), findsNothing);
  });

  testWidgets(
    'the leader opens a mission from the field; the room is told at once',
    (tester) async {
      final server = FakeCrewServer()..shiftOpen = true;
      final store = await signedInStore();
      await StaffVault(store).setPin('123456', 'salt');
      await pumpStaffApp(tester, server, store: store);
      await enterPin(tester, '123456');
      await reveal(tester, 'open-mission');
      await tester.tap(find.byKey(const Key('open-mission')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('open-nature-traffic_accident')));
      await tester.enterText(find.byKey(const Key('open-note')), 'Route X3');
      await reveal(tester, 'open-send');
      await tester.tap(find.byKey(const Key('open-send')));
      await tester.pumpAndSettle();
      final opened = server.writes.lastWhere(
        (w) => w.path.endsWith('/missions/open'),
      );
      expect(opened.json, containsPair('nature', 'traffic_accident'));
      expect(opened.json, containsPair('note', 'Route X3'));
      expect((opened.json! as Map)['lat'], isA<double>());
      expect(server.missions.first['field_initiated'], isTrue);
    },
  );

  testWidgets('the leader names the crew agents of the shift', (tester) async {
    final server = FakeCrewServer();
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    await pumpStaffApp(tester, server, store: store);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('vehicle-v-1')));
    await reveal(tester, 'crew-agent-ag-1');
    await tester.tap(find.byKey(const Key('crew-agent-ag-1')));
    await tester.pumpAndSettle();
    await reveal(tester, 'start-shift');
    await tester.tap(find.byKey(const Key('start-shift')));
    await tester.pumpAndSettle();
    final shift = server.writes.lastWhere((w) => w.path.endsWith('/shifts'));
    expect((shift.json! as Map)['crew_agent_ids'], ['ag-1']);
  });

  testWidgets(
    'the team reads the call-taking card and completes it from the scene',
    (tester) async {
      final server = await onMission(
        extra: {
          'call_card': {
            'report_id': 'r-1',
            'card_id': 'c-1',
            'category': 'medical',
            'card_version': 1,
            'sim': true,
            'title': 'إسعاف: شخص مريض أو مصاب',
            'answers': {'chest': 'unknown'},
            'outcome': {
              'band': 'high',
              'flags': <String>[],
              'reasons': <String>[],
              'means': <String>[],
              'instructions': <String>[],
              'lives': false,
              'injured': false,
              'answered': 1,
              'asked': 2,
            },
            'read': <String>[],
            'field_answers': null,
            'field_outcome': null,
            'questions': [
              {
                'id': 'chest',
                'text': 'هل يشكو من ألم في الصدر؟',
                'help': null,
                'key': true,
                'when': null,
                'effects': <String, dynamic>{},
              },
              {
                'id': 'bleeding',
                'text': 'هل يوجد نزيف قوي لا يتوقف؟',
                'help': null,
                'key': true,
                'when': null,
                'effects': <String, dynamic>{},
              },
            ],
            'instructions': <String, dynamic>{},
            'created_at': '2026-10-26T09:00:00Z',
          },
        },
      );
      await openMission(tester, server);
      await reveal(tester, 'open-call-card');
      expect(find.text('Band: High'), findsOneWidget);
      await tester.tap(find.byKey(const Key('open-call-card')));
      await tester.pumpAndSettle();
      expect(find.text("Caller: Doesn't know"), findsOneWidget);
      await tester.tap(find.byKey(const Key('card-bleeding-yes')));
      await tester.pumpAndSettle();
      await reveal(tester, 'card-send');
      await tester.tap(find.byKey(const Key('card-send')));
      await tester.pumpAndSettle();
      final write = server.writes.last;
      expect(write.path, '/api/v1/crew/missions/m-1/call-card');
      expect(write.json, containsPair('answers', {'bleeding': 'yes'}));
      // Back on the mission: the band the room now sees too.
      expect(find.text('Band: Critical'), findsOneWidget);
    },
  );

  testWidgets(
    'the mission sheet is kept on the phone and opens again offline',
    (tester) async {
      final server = await onMission();
      final dir = await tester.runAsync(
        () => Directory.systemTemp.createTemp('sheet'),
      );
      addTearDown(() => dir!.deleteSync(recursive: true));
      final opened = <String>[];
      final s = await signedInStore();
      await StaffVault(s).setPin('123456', 'salt');
      await pumpStaffApp(
        tester,
        server,
        store: s,
        sheetDir: dir,
        opened: opened,
      );
      await enterPin(tester, '123456');
      await tester.tap(find.byKey(const Key('mission-m-1')));
      await tester.pumpAndSettle();

      await reveal(tester, 'open-mission-sheet');
      await tester.runAsync(() async {
        await tester.tap(find.byKey(const Key('open-mission-sheet')));
        for (var i = 0; i < 50 && opened.isEmpty; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 20));
        }
      });
      await tester.pump();
      expect(opened, hasLength(1));
      final file = File(opened.single);
      expect(file.readAsStringSync(), startsWith('%PDF'));

      // Without network the saved copy opens, and the leader is told so.
      server.down = true;
      await tester.runAsync(() async {
        await tester.tap(find.byKey(const Key('open-mission-sheet')));
        for (var i = 0; i < 50 && opened.length < 2; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 20));
        }
      });
      await tester.pump();
      expect(opened, [file.path, file.path]);
      expect(
        find.text('No network: the copy saved on the phone was opened'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'the leader reads the address warnings and proposes a mark (OS8)',
    (tester) async {
      final server = await onMission();
      server.addressWarnings.add({
        'marker_id': 'w-1',
        'category': 'gas',
        'category_name': 'Gas store',
        'personal': false,
        'address': '12 rue de Tunis',
        'description': 'Gas bottles on the ground floor',
        'distance_m': 40,
        'critical': true,
        'off_hours': false,
        'team_ack_at': null,
      });
      await openMission(tester, server);

      expect(find.text('Address warnings: 1'), findsOneWidget);
      await tester.tap(find.byKey(const Key('open-address-warnings')));
      await tester.pumpAndSettle();
      expect(find.text('Gas bottles on the ground floor'), findsOneWidget);
      expect(find.text('Critical with Fire'), findsOneWidget);

      await tester.tap(find.byKey(const Key('aw-ack')));
      await tester.pumpAndSettle();
      expect(server.addressWarnings.single['team_ack_at'], isNotNull);
      expect(find.byKey(const Key('aw-ack')), findsNothing);

      await tester.tap(find.byKey(const Key('aw-propose')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('aw-cat-dog')));
      await tester.enterText(
        find.byKey(const Key('aw-text')),
        'A dog in the yard',
      );
      await tester.pump();
      await tester.tap(find.byKey(const Key('aw-send')));
      await tester.pumpAndSettle();
      expect(server.proposals.single['category'], 'dog');
      expect(server.proposals.single['description'], 'A dog in the yard');
    },
  );

  testWidgets('the danger-zone check of the team leader (OS7)', (tester) async {
    final server = await onMission();
    await openMission(tester, server);
    await reveal(tester, 'open-par');
    await tester.tap(find.byKey(const Key('open-par')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('par-enter-hot')));
    await tester.pumpAndSettle();
    expect(server.parCalls.last.$1, 'enter');
    expect(server.parCalls.last.$2, {'zone': 'hot'});
    expect(find.text('10:00'), findsOneWidget);
    expect(find.text('Hot zone · every 10 min'), findsOneWidget);

    // A member out for air, then back.
    await tester.tap(find.byKey(const Key('par-away-m1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('par-why-air')));
    await tester.pumpAndSettle();
    expect(server.parCalls.last.$1, 'away');
    expect(server.parCalls.last.$2, {'member': 'm1', 'why': 'air'});
    expect(find.text('Out: Air refill'), findsOneWidget);
    await tester.tap(find.byKey(const Key('par-back-m1')));
    await tester.pumpAndSettle();
    expect(server.parCalls.last.$1, 'back');

    // The headcount must be complete before «we are out».
    await tester.tap(find.byKey(const Key('par-exit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('par-out-m0')));
    await tester.tap(find.byKey(const Key('par-out-m1')));
    await tester.pump();
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('par-exit-send')))
          .onPressed,
      isNull,
    );
    await tester.tap(find.byKey(const Key('par-out-m2')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('par-exit-send')));
    await tester.pumpAndSettle();
    expect(server.parCalls.last.$1, 'exit');
    expect((server.parCalls.last.$2['members'] as List).toSet(), {
      'm0',
      'm1',
      'm2',
    });
    expect(find.byKey(const Key('par-enter-warm')), findsOneWidget);
  });
}
