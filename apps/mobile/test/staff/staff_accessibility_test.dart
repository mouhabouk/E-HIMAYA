import 'package:ehimaya/staff/staff_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'staff_fakes.dart';

/// The staff app's screens in Arabic (right to left), at large text: tap targets, labels and
/// contrast (design system §6), and no layout overflow.
void main() {
  Future<void> check(WidgetTester tester, String name) async {
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    await expectLater(tester, meetsGuideline(textContrastGuideline));
    expect(tester.takeException(), isNull, reason: name);
  }

  for (final scale in [1.0, 2.0]) {
    testWidgets('sign-in, PIN, shift, alert and mission in Arabic x$scale', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

      final server = FakeCrewServer();
      await pumpStaffApp(tester, server, locale: 'ar');
      expect(
        Directionality.of(tester.element(find.byType(Scaffold).first)),
        TextDirection.rtl,
      );
      await check(tester, 'sign-in');
      await tester.tap(find.byKey(const Key('staff-sign-in')));
      await tester.pump(const Duration(milliseconds: 100));
      await check(tester, 'code');
      await tester.scrollUntilVisible(
        find.byKey(const Key('staff-cancel-sign-in')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('staff-cancel-sign-in')));
      await tester.pumpAndSettle();

      final store = await signedInStore();
      await StaffVault(store).setPin('123456', 'salt');
      server.missions.add(FakeCrewServer.mission());
      await pumpStaffApp(tester, server, store: store, locale: 'ar');
      await check(tester, 'pin');
      await enterPin(tester, '123456');
      await check(tester, 'shift');

      server.shiftOpen = true;
      await tester.ensureVisible(find.byKey(const Key('vehicle-v-1')));
      await tester.tap(find.byKey(const Key('vehicle-v-1')));
      await tester.pump();
      await tester.ensureVisible(find.byKey(const Key('start-shift')));
      await tester.tap(find.byKey(const Key('start-shift')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('mission-alert')), findsOneWidget);
      await check(tester, 'alert');
      await tester.tap(find.byKey(const Key('ack-mission')));
      await tester.pumpAndSettle();
      await check(tester, 'missions');
      await tester.ensureVisible(find.byKey(const Key('mission-m-1')));
      await tester.tap(find.byKey(const Key('mission-m-1')));
      await tester.pumpAndSettle();
      await check(tester, 'mission');
      handle.dispose();
    });
  }

  for (final scale in [1.0, 2.0]) {
    testWidgets('situation, transport and detailed report in Arabic x$scale', (
      tester,
    ) async {
      final handle = tester.ensureSemantics();
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
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
      await pumpStaffApp(tester, server, store: store, locale: 'ar');
      await enterPin(tester, '123456');
      await tester.tap(find.byKey(const Key('mission-m-1')));
      await tester.pumpAndSettle();
      await check(tester, 'mission on scene');
      Future<void> open(String key, String name) async {
        await tester.scrollUntilVisible(
          find.byKey(Key(key)),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        // Away from the bottom bar.
        await Scrollable.ensureVisible(
          tester.element(find.byKey(Key(key))),
          alignment: 0.5,
        );
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(Key(key)));
        await tester.pumpAndSettle();
        await check(tester, name);
      }

      await open('open-situation', 'situation');
      await Scrollable.ensureVisible(
        tester.element(find.byKey(const Key('backup-yes'))),
        alignment: 0.5,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('backup-yes')));
      await tester.pumpAndSettle();
      await check(tester, 'situation with backup');
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await open('open-transports', 'transport');
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await open('open-detailed', 'detailed');
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('alert-danger')));
      await tester.pumpAndSettle();
      await check(tester, 'danger sheet');
      handle.dispose();
    });
  }

  for (final scale in [1.0, 2.0]) {
    testWidgets('prevention visit, grid, signatures and decision in Arabic '
        'x$scale', (tester) async {
      final handle = tester.ensureSemantics();
      Future<void> tap(String key) async {
        final f = find.byKey(Key(key));
        await tester.scrollUntilVisible(
          f,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await Scrollable.ensureVisible(tester.element(f), alignment: 0.3);
        await tester.pumpAndSettle();
        await tester.tap(f);
        await tester.pumpAndSettle();
      }

      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final server = FakeCrewServer()
        ..roles = ['org_auditor']
        ..visits.add(fakeVisit());
      final store = await signedInStore();
      await StaffVault(store).setPin('123456', 'salt');
      await pumpStaffApp(tester, server, store: store, locale: 'ar');
      await enterPin(tester, '123456');
      await check(tester, 'visits');
      await tap('visit-vis-1');
      await check(tester, 'visit');
      await tap('take-visit');
      await tap('open-grid');
      await tap('site.exits-nonconform');
      await check(tester, 'grid');
      await tester.tap(find.byKey(const Key('grid-next')));
      await tester.pumpAndSettle();
      await check(tester, 'signatures');
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      server.visits[0] = {...server.visits[0], 'status': 'inspected'};
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      await tester.fling(
        find.byType(ListView).first,
        const Offset(0, 400),
        1000,
      );
      await tester.pumpAndSettle();
      await tap('visit-vis-1');
      await tap('open-decision');
      await check(tester, 'decision');
      handle.dispose();
    });
  }
}
