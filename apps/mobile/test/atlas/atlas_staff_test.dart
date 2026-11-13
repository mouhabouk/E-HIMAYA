// The staff (field agents) app's screens and windows for the flowchart atlas (Yamen, 2026-11-13): the field team, the
// team leader, the prevention inspector and the inspector of the periodic inspections. Skipped unless ATLAS_OUT is set.
import 'dart:io';

import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/inspect/inspect_screens.dart';
import 'package:ehimaya/staff/screens/address_warnings_screen.dart';
import 'package:ehimaya/staff/screens/call_card_screen.dart';
import 'package:ehimaya/staff/screens/detailed_report_screen.dart';
import 'package:ehimaya/staff/screens/field_flow.dart';
import 'package:ehimaya/staff/screens/par_screen.dart';
import 'package:ehimaya/staff/screens/record_screen.dart';
import 'package:ehimaya/staff/screens/situation_screen.dart';
import 'package:ehimaya/staff/screens/staff_live_screen.dart';
import 'package:ehimaya/staff/screens/stage_message_screen.dart';
import 'package:ehimaya/staff/screens/transport_screen.dart';
import 'package:ehimaya/staff/staff_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/live_fakes.dart';
import '../staff/inspect_test.dart'
    as insp
    show FakeInspectServer, activatedStore;
import '../staff/staff_fakes.dart';
import 'atlas_kit.dart';

enum Who {
  signedOut,
  agent,
  onShift,
  onScene,
  auditor,
  auditorInspected,
  inspector,
  inspectorNew,
}

class Case {
  const Case(this.id, this.who, {this.push, this.taps = const []});

  final String id;
  final Who who;

  /// A screen opened over the home, as the app's own buttons do.
  final Widget Function()? push;
  final List<String> taps;
}

const m = 'm-1';
final cases = <Case>[
  Case('s-signin', Who.signedOut),
  Case('s-pin', Who.agent),
  Case('s-shift', Who.agent, taps: ['__pin']),
  Case('s-missions', Who.onShift, taps: ['__pin', 'ack-mission']),
  Case('s-mission-alert', Who.onShift, taps: ['__pin']),
  Case('s-mission', Who.onShift, taps: ['__pin', 'ack-mission', 'mission-m-1']),
  Case('s-mission-onscene', Who.onScene, taps: ['__pin', 'mission-m-1']),
  Case(
    's-open-mission',
    Who.onShift,
    push: () => const OpenMissionScreen(),
    taps: ['__pin', 'ack-mission'],
  ),
  Case(
    's-call-card',
    Who.onScene,
    push: () => const CallCardScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-address-warnings',
    Who.onScene,
    push: () => const AddressWarningsScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-par',
    Who.onScene,
    push: () => const ParScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-toll',
    Who.onScene,
    push: () => const TollScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-stage-message',
    Who.onScene,
    push: () => const StageMessageScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-live',
    Who.onScene,
    push: () => const StaffLiveScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-situation',
    Who.onScene,
    push: () => const SituationScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-record',
    Who.onScene,
    push: () => const MissionRecordScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-transport',
    Who.onScene,
    push: () => const TransportScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-detailed-report',
    Who.onScene,
    push: () => const DetailedReportScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-intervention-report',
    Who.onScene,
    push: () => const InterventionReportScreen(missionId: m),
    taps: ['__pin'],
  ),
  Case(
    's-field-charter',
    Who.onShift,
    push: () => const CharterScreen(),
    taps: ['__pin', 'ack-mission'],
  ),
  // windows of the field team
  Case(
    'sw-backup',
    Who.onScene,
    taps: ['__pin', 'mission-m-1', 'alert-backup'],
  ),
  Case(
    'sw-danger',
    Who.onScene,
    taps: ['__pin', 'mission-m-1', 'alert-danger'],
  ),
  Case(
    'sw-par-enter',
    Who.onScene,
    push: () => const ParScreen(missionId: m),
    taps: ['__pin', 'par-enter-hot'],
  ),
  Case(
    'sw-address-propose',
    Who.onScene,
    push: () => const AddressWarningsScreen(missionId: m),
    taps: ['__pin', 'aw-propose'],
  ),
  Case(
    'sw-end-shift',
    Who.onShift,
    taps: ['__pin', 'ack-mission', 'staff-menu', 'end-shift'],
  ),
  Case(
    'sw-no-intervention',
    Who.onShift,
    taps: ['__pin', 'ack-mission', 'mission-m-1', 'flow-no-intervention'],
  ),
  Case(
    'sw-situation-text',
    Who.onScene,
    push: () => const SituationScreen(missionId: m),
    taps: ['__pin', 'attach-text'],
  ),
  Case(
    'sw-par-missing',
    Who.onScene,
    push: () => const ParScreen(missionId: m),
    taps: ['__pin', 'par-enter-hot', 'par-missing'],
  ),
  Case(
    'sw-par-exit',
    Who.onScene,
    push: () => const ParScreen(missionId: m),
    taps: ['__pin', 'par-enter-hot', 'par-exit'],
  ),
  Case(
    'sw-par-sitrep',
    Who.onScene,
    push: () => const ParScreen(missionId: m),
    taps: ['__pin', 'par-enter-hot', 'par-sitrep'],
  ),
  // the prevention inspector (Office auditor)
  Case('s-prevention-visits', Who.auditor, taps: ['__pin']),
  Case('s-prevention-visit', Who.auditor, taps: ['__pin', 'visit-vis-1']),
  Case(
    's-prevention-grid',
    Who.auditor,
    taps: ['__pin', 'visit-vis-1', 'take-visit', 'open-grid'],
  ),
  Case(
    's-prevention-sign',
    Who.auditor,
    taps: ['__pin', 'visit-vis-1', 'take-visit', 'open-sign'],
  ),
  Case(
    's-prevention-decision',
    Who.auditorInspected,
    taps: ['__pin', 'visit-vis-1', 'take-visit', 'open-decision'],
  ),
  // the periodic inspections
  Case('s-inspect-entry', Who.inspectorNew, taps: ['open-inspector']),
  Case(
    's-inspect-register',
    Who.inspectorNew,
    taps: ['open-inspector', 'insp-to-register'],
  ),
  Case('s-inspect-missions', Who.inspector, taps: ['open-inspector']),
  Case(
    's-inspect-run',
    Who.inspector,
    taps: ['open-inspector', 'insp-site-s-1'],
  ),
  Case(
    'sw-inspect-add-rec',
    Who.inspector,
    taps: ['open-inspector', 'insp-site-s-1', 'insp-to-sign', 'insp-add-rec'],
  ),
  Case(
    's-inspect-history',
    Who.inspector,
    push: () => const InspectHistoryScreen(),
    taps: ['open-inspector'],
  ),
];

Future<void> settle(WidgetTester tester) => tester
    .pumpAndSettle(
      const Duration(milliseconds: 50),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 5),
    )
    .catchError((_) => 0);

Map<String, dynamic> onSceneMission() => {
  ...FakeCrewServer.mission(acknowledgedAt: '2026-10-26T09:01:00Z'),
  'status': 'on_scene',
  'en_route_at': '2026-10-26T09:03:00Z',
  'on_scene_at': '2026-10-26T09:12:00Z',
  'call_card': callCard,
};

/// The call-taking card the room filled on the phone call [SIM].
const callCard = {
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
};

void main() {
  setUpAll(() async {
    if (!atlasSkip) await loadAtlasFonts();
  });
  final only = atlasOnly();
  for (final c in cases.where((c) => only == null || only.contains(c.id))) {
    testWidgets(
      'atlas ${c.id}',
      (tester) async {
        quietPlugins();
        final server = FakeCrewServer();
        final inspect = insp.FakeInspectServer();
        final crew = server.adapter.handler;
        server.adapter.handler = (r) =>
            r.path.startsWith('/api/v1/inspect') ? inspect.handle(r) : crew(r);
        MemorySecureStore store;
        switch (c.who) {
          case Who.signedOut || Who.inspectorNew:
            store = MemorySecureStore();
          case Who.inspector:
            store = await insp.activatedStore();
          default:
            store = await signedInStore();
            await StaffVault(store).setPin('123456', 'salt');
        }
        if (c.who == Who.onShift || c.who == Who.onScene) {
          server.shiftOpen = true;
        }
        if (c.who == Who.onShift) server.missions.add(FakeCrewServer.mission());
        if (c.who == Who.onScene) {
          server.missions.add(onSceneMission());
          server.addressWarnings.add({
            'marker_id': 'w-1',
            'category': 'gas',
            'category_name': 'مخزن غاز',
            'personal': false,
            'address': '12 نهج تونس',
            'description': 'قوارير غاز في الطابق الأرضي',
            'distance_m': 40,
            'critical': true,
            'off_hours': false,
            'team_ack_at': null,
          });
        }
        if (c.who == Who.auditor || c.who == Who.auditorInspected) {
          server
            ..roles = ['org_auditor']
            ..visits.add(
              fakeVisit(
                status: c.who == Who.auditor ? 'scheduled' : 'inspected',
              ),
            );
        }
        await pumpStaffApp(
          tester,
          server,
          store: store,
          locale: 'ar',
          publisher: FakeLivePublisher(),
        );
        sizePhone(tester);
        addTearDown(tester.view.reset);
        await settle(tester);
        var since = 0;
        for (final k in c.taps) {
          if (k == '__pin') {
            await enterPin(tester, '123456');
            await settle(tester);
            if (c.push != null) {
              since = server.adapter.requests.length;
              // ignore: unawaited_futures
              Navigator.of(tester.element(find.byType(Scaffold).last))
                  .push(MaterialPageRoute<void>(builder: (_) => c.push!()));
              await settle(tester);
            }
            continue;
          }
          if (k.startsWith('mission-') || k == 'open-inspector') {
            since = server.adapter.requests.length;
          }
          await tapKey(tester, k);
        }
        if (c.push != null && !c.taps.contains('__pin')) {
          since = server.adapter.requests.length;
          // ignore: unawaited_futures
          Navigator.of(tester.element(find.byType(Scaffold).last))
              .push(MaterialPageRoute<void>(builder: (_) => c.push!()));
          await settle(tester);
        }
        await shot(tester, c.id, adapter: server.adapter, since: since);
        await tester.pumpWidget(const SizedBox());
        await tester.pump(const Duration(seconds: 1));
      },
      skip: atlasSkip,
      timeout: const Timeout(Duration(seconds: 60)),
    );
  }
  tearDownAll(() {
    if (!atlasSkip) File('$atlasOut/staff.done').writeAsStringSync('ok');
  });
}
