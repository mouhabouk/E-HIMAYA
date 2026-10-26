// Accessibility, P3c: NFR-09 in docs/01-requirements.html (number 10 among the non-functional
// requirements of the project description). Every screen keeps 48dp touch targets, labels on what can be tapped and
// readable contrast, in both languages and both themes, and lays out without clipping
// when the text is enlarged to 200%.
import 'dart:async';

import 'package:ehimaya/core/routing/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../helpers/app_harness.dart';
import '../helpers/org_fixtures.dart';
import 'institution_flow_test.dart' show api;

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 200));
  }
}

const _charter = {
  'charter.accepted_version': '2026-11',
  'charter.accepted_at': '2026-10-19T10:00:00Z',
};

void main() {
  final routes = <String>[
    Routes.home,
    Routes.emergency,
    Routes.guide,
    Routes.nearest,
    Routes.newReport,
    Routes.reports,
    Routes.track,
    Routes.settings,
    Routes.profile,
    Routes.notifications,
    Routes.tips,
    Routes.contact,
    Routes.volunteer,
    Routes.doctor,
    Routes.safety,
    Routes.safetyContacts,
    Routes.rewards,
    Routes.myData,
    Routes.institutions,
    Routes.institution(orgId),
    Routes.institutionSection(orgId, 'records'),
    Routes.institutionSection(orgId, 'equipment'),
    Routes.institutionSection(orgId, 'activities'),
    Routes.institutionSection(orgId, 'card'),
    Routes.institutionRegister,
    Routes.live,
  ];
  final welcome = <String, Map<String, Object>>{
    'language': {},
    'intro': {'welcome.language_chosen': true},
    'charter': {'welcome.language_chosen': true, 'welcome.intro_seen': true},
    'permissions': {
      'welcome.language_chosen': true,
      'welcome.intro_seen': true,
      ..._charter,
    },
    'onboarding': {
      'welcome.language_chosen': true,
      'welcome.intro_seen': true,
      'welcome.permissions_seen': true,
      ..._charter,
    },
  };
  // (name, prefs, route, text scale)
  final cases = <(String, Map<String, Object>, String?, double)>[
    for (final locale in ['ar', 'fr'])
      for (final e in welcome.entries)
        (
          'welcome ${e.key} $locale',
          {...e.value, if (e.key != 'language') 'settings.locale': locale},
          null,
          2.0,
        ),
    for (final r in routes) ...[
      ('$r ar', registeredPrefs(locale: 'ar'), r, 2.0),
      ('$r fr', registeredPrefs(locale: 'fr'), r, 2.0),
      (
        '$r ar dark',
        {...registeredPrefs(locale: 'ar'), 'settings.theme': 'dark'},
        r,
        1.0,
      ),
    ],
  ];
  for (final (name, prefs, route, scale) in cases) {
    testWidgets('a11y $name x$scale', (tester) async {
      tester.view.physicalSize = const Size(1080, 2340);
      tester.view.devicePixelRatio = 2.625;
      tester.platformDispatcher.textScaleFactorTestValue = scale;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final handle = tester.ensureSemantics();
      final errors = <String>[];
      final previous = FlutterError.onError;
      FlutterError.onError = (d) => errors.add(d.exceptionAsString());
      try {
        await pumpApp(
          tester,
          prefs: prefs,
          session: route == null ? null : testSession,
          api: (r) => api(r, role: 'admin'),
        );
        await _settle(tester);
        if (route != null) {
          unawaited(
            GoRouter.of(tester.element(find.byType(Scaffold).first))
                .push(route),
          );
          await _settle(tester);
        }
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
      } finally {
        FlutterError.onError = previous;
      }
      expect(errors, isEmpty, reason: 'layout errors on $name x$scale');
      handle.dispose();
      await unmountApp(tester);
    });
  }
}
