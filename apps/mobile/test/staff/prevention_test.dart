import 'dart:convert';

import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/prevention/prevention_labels.dart';
import 'package:ehimaya/staff/prevention/prevention_models.dart';
import 'package:ehimaya/staff/prevention/prevention_store.dart';
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'staff_fakes.dart';

/// F-STF-06 (phase P4c): the inspector's visits on the staff app, the grid by buttons offline,
/// photos, both signatures, the decision, and the sealed copy on the phone.
void main() {
  Future<MemorySecureStore> inspectorStore() async {
    final store = await signedInStore();
    await StaffVault(store).setPin('123456', 'salt');
    return store;
  }

  Future<void> tapKey(WidgetTester tester, String key) async {
    final f = find.byKey(Key(key));
    await tester.scrollUntilVisible(
      f,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    // Away from the bottom bar and the snack bar.
    await Scrollable.ensureVisible(tester.element(f), alignment: 0.3);
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

  /// Takes the visit, fills the grid and signs; returns before closing the inspection.
  Future<void> fillAndSign(WidgetTester tester, {bool take = true}) async {
    await tester.tap(find.byKey(const Key('visit-vis-1')));
    await tester.pumpAndSettle();
    if (take) {
      await tester.tap(find.byKey(const Key('take-visit')));
      await tester.pumpAndSettle();
    }
    await tester.tap(find.byKey(const Key('open-grid')));
    await tester.pumpAndSettle();

    await tapKey(tester, 'building.capacity-conform');
    // A count: starts from what was declared, then − twice.
    await tapKey(tester, 'equipment.extinguisher-nonconform');
    expect(
      tester
          .widget<Text>(find.byKey(const Key('equipment.extinguisher-count')))
          .data,
      '8',
    );
    await tapKey(tester, 'equipment.extinguisher-minus');
    await tapKey(tester, 'equipment.extinguisher-minus');
    await tapKey(tester, 'equipment.extinguisher-reason-expired');
    await tapKey(tester, 'all-conform-site');
    await tapKey(tester, 'site.exits-nonconform');
    expect(find.byKey(const Key('site.exits-needs-detail')), findsOneWidget);
    await tapKey(tester, 'site.exits-reason-blocked');
    expect(find.byKey(const Key('site.exits-needs-detail')), findsNothing);
    await tapKey(tester, 'site.exits-photo');
    expect(
      find.text('2 conforming · 2 non-conforming · 2 not checked'),
      findsOneWidget,
    );
    expect(find.textContaining('Suggested decision: '), findsOneWidget);
    await tester.tap(find.byKey(const Key('grid-next')));
    await tester.pumpAndSettle();

    // The representative declared is offered; name and role by chips; both signatures.
    await tapKey(tester, 'attendee-person:Sami Trabelsi');
    await tapKey(tester, 'attendee-safety_officer');
    expect(find.text('Sami Trabelsi'), findsWidgets);
    await tapKey(tester, 'role-director');
    await sign(tester, 'pad-inspector');
    await sign(tester, 'pad-representative');
  }

  testWidgets('an inspector takes a visit, inspects it with photos and '
      'signatures, then decides with reservations', (tester) async {
    final server = FakeCrewServer()
      ..roles = ['org_auditor']
      ..visits.add(fakeVisit());
    await pumpStaffApp(tester, server, store: await inspectorStore());
    await enterPin(tester, '123456');

    // An inspector only: the home is the list of visits.
    expect(find.text('Prevention visits'), findsWidgets);
    expect(find.byKey(const Key('visit-vis-1')), findsOneWidget);
    await fillAndSign(tester);
    await tapKey(tester, 'sign-off');

    final sent = [
      for (final w in server.writes)
        if (w.path.contains('/prevention/')) w.path.split('/').last,
    ];
    expect(sent, ['claim', 'photos', 'inspection']);
    final photo = server.writes.firstWhere((w) => w.path.endsWith('/photos'));
    expect(photo.uri.queryParameters['item_key'], 'site.exits');
    expect(photo.header('content-type'), 'image/jpeg');
    expect(photo.header('x-staff-device'), 'dev-1');
    final body =
        server.writes.firstWhere((w) => w.path.endsWith('/inspection')).json!
            as Map<String, dynamic>;
    expect(body['client_id'], isA<String>());
    expect(body['representative_name'], 'Sami Trabelsi');
    expect(body['representative_role'], 'Director');
    expect(body['attendees'], 'Sami Trabelsi، Safety officer');
    expect(body['inspector_signature'], isA<String>());
    final items = {for (final i in body['items'] as List) (i as Map)['key']: i};
    expect(items.keys, isNot(contains('safety_team.representative')));
    expect(items['equipment.extinguisher'], {
      'key': 'equipment.extinguisher',
      'result': 'nonconform',
      'observed': '6',
      'note': 'Expired',
    });
    expect(items['site.exits']!['note'], 'Blocked');
    expect(items['site.alarm']!['result'], 'conform');

    // The decision: reservations proposed from the two non-conformities, 6 months.
    // The snack bar goes away.
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('open-decision')));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<CheckboxListTile>(
            find.byKey(const Key('reservation-site.exits')),
          )
          .value,
      isTrue,
    );
    await tapKey(tester, 'reservation-equipment.extinguisher');
    await tapKey(tester, 'due-6');
    await tapKey(tester, 'valid-3');
    await tester.tap(find.byKey(const Key('send-decision')));
    await tester.pumpAndSettle();
    final decision = server.writes.last.json! as Map<String, dynamic>;
    expect(server.writes.last.path, endsWith('/decision'));
    expect(decision['decision'], 'approved_with_reservations');
    final reservations = decision['reservations'] as List;
    expect(reservations, hasLength(1));
    expect(reservations.single, containsPair('item_key', 'site.exits'));
    expect(reservations.single, containsPair('text', 'Exits clear: Blocked'));
    final today = DateTime.now();
    expect(
      reservations.single,
      containsPair('due_on', isoDay(addMonths(today, 6))),
    );
    expect(decision['valid_until'], isoDay(addMonths(today, 36)));
    expect(find.text('Decision sent.'), findsOneWidget);
    // Decided: nothing stays on the phone.
    expect(find.byKey(const Key('visit-vis-1')), findsNothing);
    expect(find.byKey(const Key('no-visits')), findsOneWidget);
  });

  testWidgets('offline: the work is kept sealed and sent in order later', (
    tester,
  ) async {
    final server = FakeCrewServer()
      ..roles = ['org_auditor']
      ..visits.add(fakeVisit());
    final store = await inspectorStore();
    final blobs = MemoryBlobStore();
    await pumpStaffApp(tester, server, store: store, blobs: blobs);
    await enterPin(tester, '123456');
    // The network drops once the visit is on the phone.
    await tester.tap(find.byKey(const Key('visit-vis-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('take-visit')));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    server.down = true;
    await fillAndSign(tester, take: false);
    await tapKey(tester, 'sign-off');
    expect(
      find.text('Inspection kept, sent when the network is back.'),
      findsWidgets,
    );
    expect(find.byKey(const Key('staff-offline')), findsOneWidget);
    expect(find.byKey(const Key('visits-pending')), findsOneWidget);
    expect(find.text('2 waiting to be sent'), findsWidgets);

    // Sealed: neither the names nor the grid can be read from the files.
    expect(store.values[PreventionBox.keyName], isNotNull);
    for (final b in blobs.values.values) {
      expect(latin1.decode(b), isNot(contains('Sami')));
      expect(latin1.decode(b), isNot(contains('site.exits')));
    }
    expect(
      blobs.values.keys.where((k) => k.startsWith('photo-')),
      hasLength(1),
    );

    // The phone restarts without network: the visit and its draft are still there.
    await pumpStaffApp(tester, server, store: store, blobs: blobs);
    await enterPin(tester, '123456');
    expect(find.byKey(const Key('visit-vis-1')), findsOneWidget);
    expect(find.text('2 waiting to be sent'), findsWidgets);

    server.down = false;
    final before = server.writes.length;
    await tester.tap(find.byKey(const Key('send-now')));
    await tester.pumpAndSettle();
    expect(
      [
        for (final w in server.writes.skip(before))
          if (w.path.contains('/prevention/')) w.path.split('/').last,
      ],
      ['photos', 'inspection'],
    );
    expect(find.byKey(const Key('visits-pending')), findsNothing);
    expect(blobs.values.keys.where((k) => k.startsWith('photo-')), isEmpty);
  });

  testWidgets('a visit another inspector took cannot be taken', (tester) async {
    final server = FakeCrewServer()
      ..roles = ['org_auditor']
      ..visits.add(fakeVisit(takenByOther: true));
    await pumpStaffApp(tester, server, store: await inspectorStore());
    await enterPin(tester, '123456');
    expect(find.text('Taken by another inspector'), findsOneWidget);
    await tester.tap(find.byKey(const Key('visit-vis-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('visit-taken')), findsOneWidget);
    expect(find.byKey(const Key('take-visit')), findsNothing);
  });

  testWidgets('a revoked phone erases the visits kept on it', (tester) async {
    final server = FakeCrewServer()
      ..roles = ['org_auditor']
      ..visits.add(fakeVisit());
    final store = await inspectorStore();
    final blobs = MemoryBlobStore();
    await pumpStaffApp(tester, server, store: store, blobs: blobs);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('visit-vis-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('take-visit')));
    await tester.pumpAndSettle();
    expect(blobs.values, isNotEmpty);
    server.revoked = true;
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    await tester.fling(find.byType(ListView).first, const Offset(0, 400), 1000);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('staff-signout-reason')), findsOneWidget);
    expect(blobs.values, isEmpty);
    expect(store.values[PreventionBox.keyName], isNull);
  });

  testWidgets('a team leader who is also an inspector opens the visits from '
      'the shift screen', (tester) async {
    final server = FakeCrewServer()
      ..roles = ['team_leader', 'org_auditor']
      ..visits.add(fakeVisit(mine: true));
    await pumpStaffApp(tester, server, store: await inspectorStore());
    await enterPin(tester, '123456');
    expect(find.text('Start of shift'), findsOneWidget);
    await tester.tap(find.byKey(const Key('open-visits')));
    await tester.pumpAndSettle();
    expect(find.text('Mine'), findsOneWidget);
  });

  test('the grid summary suggests reservations from one non-conformity', () {
    final v = FieldVisit(fakeVisit());
    var d = const InspectionDraft();
    expect(GridSummary.of(v.checklist, d).notChecked, 6);
    d = d.copyWith(
      items: {
        'site.alarm': const ItemDraft(result: Finding.conform),
        'site.exits': const ItemDraft(result: Finding.nonconform),
      },
    );
    final s = GridSummary.of(v.checklist, d);
    expect((s.conform, s.nonconform, s.notChecked), (1, 1, 4));
    expect(s.suggested, 'approved_with_reservations');
    final again = InspectionDraft.fromJson(
      jsonDecode(jsonEncode(d.toJson())) as Map<String, dynamic>,
    );
    expect(again.item('site.exits').result, Finding.nonconform);
  });
}
