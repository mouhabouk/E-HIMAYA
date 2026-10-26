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
}
