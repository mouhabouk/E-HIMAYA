// The citizen app's screens and windows for the flowchart atlas (Yamen, 2026-11-13). Skipped unless ATLAS_OUT is set:
//   ATLAS_OUT=/tmp/atlas-mobile flutter test test/atlas
// A case opens a route as a registered citizen (or at a first-launch step), then may tap its way to a window (a
// dialog, a bottom sheet, a tab) before the screenshot. The ids are those of scripts/atlas/apps_content.py.
import 'dart:io';

import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/guide/guide_providers.dart';
import 'package:ehimaya/features/places/nearest_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import 'atlas_api.dart';
import 'atlas_kit.dart';

/// Where the phone stands in its first launch.
enum Stage { fresh, language, intro, charter, identity, anonymous, registered }

Map<String, Object> prefsFor(Stage s) => switch (s) {
  Stage.fresh => const {},
  Stage.language => const {
    'welcome.language_chosen': true,
    'settings.locale': 'ar',
  },
  Stage.intro => {...languageAndIntroDone, 'settings.locale': 'ar'},
  Stage.charter => {
    ...languageAndIntroDone,
    'charter.accepted_version': '2026-11',
    'charter.accepted_at': '2026-10-19T10:00:00Z',
    'settings.locale': 'ar',
  },
  Stage.identity => {
    ...languageAndIntroDone,
    'welcome.permissions_seen': true,
    'charter.accepted_version': '2026-11',
    'charter.accepted_at': '2026-10-19T10:00:00Z',
    'settings.locale': 'ar',
  },
  Stage.anonymous => {
    ...languageAndIntroDone,
    'welcome.permissions_seen': true,
    ...onboardedPrefs(),
  },
  Stage.registered => {
    ...languageAndIntroDone,
    'welcome.permissions_seen': true,
    ...registeredPrefs(),
  },
};

class Case {
  const Case(
    this.id,
    this.route, {
    this.stage = Stage.registered,
    this.taps = const [],
    this.text,
  });

  final String id;
  final String? route;
  final Stage stage;

  /// Keys tapped in order after the route opened (scrolled into view first).
  final List<String> taps;

  /// A text tapped last (when the button has no key).
  final String? text;
}

final cases = <Case>[
  // first launch
  Case('c-welcome-language', null, stage: Stage.fresh),
  Case('c-welcome-intro', null, stage: Stage.language),
  Case('c-charter', null, stage: Stage.intro),
  Case('c-welcome-permissions', null, stage: Stage.charter),
  Case('c-sign-in', null, stage: Stage.identity),
  Case(
    'c-onboarding-institution',
    Routes.onboardingInstitution,
    stage: Stage.identity,
  ),
  Case('c-profile', Routes.profile),
  // the three tabs
  Case('c-home', Routes.home),
  Case('c-reports', Routes.reports),
  Case('c-settings', Routes.settings),
  // reporting
  Case('c-report-new', Routes.newReport),
  Case('c-report-fire', '/report/new/fire'),
  Case('c-report-queued', '/report/queued?code=TMP-ABC234'),
  Case('c-quota', '/quota?code=TMP-ABC234', stage: Stage.anonymous),
  Case('c-track', Routes.track),
  Case('c-live', Routes.live),
  // emergency hub
  Case('c-emergency', Routes.emergency),
  Case('c-nearest', Routes.nearest),
  Case('c-beaches', Routes.beaches),
  Case('c-beach', '/emergency/beaches/b-sidimansour'),
  Case('c-guide', Routes.guide),
  Case('c-guide-topic', '/emergency/guide/fire'),
  Case('c-guide-item', '/emergency/guide/fire/seed-fire-0'),
  Case('c-contact', Routes.contact),
  Case('c-contact-mine', Routes.contactMine),
  // personal safety
  Case('c-safety', Routes.safety),
  Case('c-safety-contacts', '/safety/contacts'),
  Case('c-safety-message', '/safety/message'),
  Case('c-safety-send', '/safety/send'),
  Case('c-safety-linked', '/safety/linked'),
  Case('c-safety-live', '/safety/live'),
  Case('c-safety-check', '/safety/check'),
  Case('c-safety-test', '/safety/test'),
  Case('c-safety-recent', '/safety/recent'),
  Case('c-safety-medical', '/safety/medical'),
  Case('c-safety-address', '/safety/address-warnings'),
  Case('c-safety-history', '/safety/location-history'),
  // alerts and tips
  Case('c-notifications', Routes.notifications),
  Case('c-alert', '/alerts/a1e70000-0000-4000-8000-000000000001'),
  Case('c-tips', Routes.tips),
  Case('c-tip', '/tips/flood'),
  Case('c-alert-check', Routes.alertCheck),
  Case('c-alert-critical', Routes.criticalAlerts),
  // institution
  Case('c-institutions', Routes.institutions),
  Case('c-institution-new', Routes.institutionRegister),
  Case('c-institution', '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60'),
  for (final s in [
    'messages',
    'card',
    'team',
    'equipment',
    'hazmat',
    'evacuation',
    'reports',
    'certificates',
    'records',
    'activities',
    'awareness',
    'members',
  ])
    Case(
      'c-institution-$s',
      '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/$s',
    ),
  // volunteers and doctors
  Case('c-volunteer', Routes.volunteer),
  Case('c-volunteer-apply', Routes.volunteerApply),
  Case('c-callouts', Routes.callouts),
  Case('c-availability', '/availability/volunteer'),
  Case('c-doctor', Routes.doctor),
  Case('c-doctor-apply', Routes.doctorApply),
  Case('c-doctor-directory', Routes.doctorDirectory),
  Case('c-doctor-files', Routes.doctorFiles),
  Case('c-rewards', Routes.rewards),
  // settings
  Case('c-accessibility', Routes.accessibility),
  Case('c-rate-app', Routes.rateApp),
  Case('c-intro-replay', Routes.introReplay),
  Case('c-charter-read', Routes.charterRead),
  Case('c-my-data', Routes.myData),
  Case('c-delete-account', Routes.deleteAccount),
  // windows: dialogs and bottom sheets
  Case('w-sos-confirm', Routes.reports, taps: ['sos-fab']),
  Case('w-contacts-add', '/safety/contacts', taps: ['contacts-add']),
  Case('w-groups-add', '/safety/contacts', taps: ['groups-add']),
  Case('w-linked-code', '/safety/linked', taps: ['linked-enter-code']),
  Case(
    'w-medical-show',
    '/safety/medical',
    taps: ['medical-consent', 'medical-create', 'medical-show'],
  ),
  Case(
    'w-callout-accept',
    Routes.callouts,
    taps: ['callout-accept-c0ffee00-0000-4000-8000-000000000001'],
  ),
  Case('w-volunteer-withdraw', Routes.volunteer, taps: ['volunteer-withdraw']),
  Case(
    'w-availability-add',
    '/availability/volunteer',
    taps: ['availability-add'],
  ),
  Case('w-doctor-withdraw', Routes.doctor, taps: ['doctor-withdraw']),
  Case('w-doctor-key-create', Routes.doctor, taps: ['doctor-key-create']),
  Case(
    'w-org-card-edit',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/card',
    taps: ['org-card-edit'],
  ),
  Case(
    'w-org-maintenance-log',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/equipment',
    taps: ['log-maintenance-e1'],
  ),
  Case(
    'w-org-activity-add',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/activities',
    taps: ['org-activity-add'],
  ),
  Case(
    'w-org-activity-delete',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/activities',
    taps: ['org-activity-delete-a1'],
  ),
  Case(
    'c-prealert',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/prealerts/p-1',
  ),
  Case('w-medical-openings', Routes.reports, taps: ['openings-r-1']),
  Case(
    'c-sign-in-institution',
    Routes.signInInstitution,
    stage: Stage.identity,
  ),
  Case(
    'w-prealert-false',
    '/institutions/7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60/prealerts/p-1',
    taps: ['prealert-false'],
  ),
  Case(
    'w-medical-delete',
    '/safety/medical',
    taps: ['medical-consent', 'medical-create', 'medical-delete'],
  ),
  Case('w-link-remove', '/safety/linked', taps: ['link-remove-link-1']),
  Case(
    'w-volunteer-location',
    Routes.volunteer,
    taps: ['volunteer-location-consent'],
  ),
];

Future<void> settle(WidgetTester tester) => tester
    .pumpAndSettle(
      const Duration(milliseconds: 50),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 5),
    )
    .catchError((_) => 0);

Future<void> go(WidgetTester tester, String location) async {
  final container = ProviderScope.containerOf(
    tester.element(find.byType(Navigator).first),
  );
  container.read(routerProvider).go(location);
  await settle(tester);
}

void main() {
  setUpAll(() async {
    if (!atlasSkip) await loadAtlasFonts();
  });
  final only = atlasOnly();
  for (final c in cases.where((c) => only == null || only.contains(c.id))) {
    testWidgets(
      'atlas ${c.id}',
      (tester) async {
        sizePhone(tester);
        quietPlugins();
        addTearDown(tester.view.reset);
        final h = await pumpApp(
          tester,
          prefs: prefsFor(c.stage),
          session: c.stage == Stage.registered
              ? AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100))
              : null,
          api: atlasApi,
          overrides: [
            myPositionProvider.overrideWith(
              (ref) async => const GeoPoint(lat: 34.7406, lon: 10.7603),
            ),
            bundledGuideLoaderProvider.overrideWithValue(
              () async =>
                  File('assets/emergency_guide.json').readAsStringSync(),
            ),
          ],
        );
        var since = 0;
        if (c.route != null) {
          since = h.adapter.requests.length;
          await go(tester, c.route!);
        }
        for (final k in c.taps) {
          await tapKey(tester, k);
        }
        if (c.text != null) {
          await tester.tap(find.text(c.text!).last);
          await settle(tester);
        }
        await shot(
          tester,
          c.id,
          adapter: h.adapter,
          since: since,
          extra: {'route': c.route ?? ''},
        );
        if (atlasMissed.isNotEmpty) {
          File('$atlasOut/missed.txt').writeAsStringSync(
            '${c.id}: ${atlasMissed.join(' ')}\n',
            mode: FileMode.append,
          );
          atlasMissed.clear();
        }
        await unmountApp(tester);
      },
      skip: atlasSkip,
      timeout: const Timeout(Duration(seconds: 60)),
    );
  }
}
