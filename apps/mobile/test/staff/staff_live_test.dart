// covers: review point 17 (phase D, docs/phase-d/design-d.md §4)
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/live_fakes.dart';
import 'staff_fakes.dart';

void main() {
  testWidgets('the team streams the scene to the room from the mission', (
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
    final publisher = FakeLivePublisher();
    await pumpStaffApp(tester, server, store: store, publisher: publisher);
    await enterPin(tester, '123456');
    await tester.tap(find.byKey(const Key('mission-m-1')));
    await tester.pumpAndSettle();

    await reveal(tester, 'open-live');
    await tester.tap(find.byKey(const Key('open-live')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pump(const Duration(milliseconds: 500));
    // The mission's stream, published with WHIP and its token.
    expect(server.liveStreams, ['m-1']);
    expect(publisher.opened, isTrue);
    expect(server.whipPosts.single.header('authorization'), 'Bearer tok-cs-1');
    expect(find.byKey(const Key('fake-preview')), findsOneWidget);
    expect(
      find.text('The room sees it on the video wall and the incident page'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('staff-live-stop')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(server.liveStops, ['cs-1']);
    expect(
      find.text('Stream over. The recording is kept with the incident.'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('staff-live-close')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.byKey(const Key('staff-live-close')), findsNothing);
    expect(
      find.byKey(const Key('open-live'), skipOffstage: false),
      findsOneWidget,
    );
  });
}
