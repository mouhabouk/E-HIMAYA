// covers: FR-A-001, FR-A-030, FR-A-033, NFR-08
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/charter/charter_screen.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/onboarding/role_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';

void main() {
  testWidgets('charter gate blocks everything until accepted', (tester) async {
    await pumpApp(tester);
    expect(find.byType(CharterScreen), findsOneWidget);

    // Continue is disabled while the box is unchecked.
    final button = find.byKey(const Key('charter-continue'));
    expect(tester.widget<FilledButton>(button).onPressed, isNull);
    await tester.tap(button, warnIfMissed: false);
    await tester.pumpAndSettle();
    expect(find.byType(CharterScreen), findsOneWidget);

    // Deep links are redirected back to the charter.
    GoRouter.of(tester.element(find.byType(CharterScreen))).go(Routes.home);
    await tester.pumpAndSettle();
    expect(find.byType(CharterScreen), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);

    // Accept → role choice.
    await tester.ensureVisible(find.byKey(const Key('charter-checkbox')));
    await tester.tap(find.byKey(const Key('charter-checkbox')));
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(find.byType(RoleScreen), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('emergency numbers are reachable before the charter', (
    tester,
  ) async {
    final h = await pumpApp(tester);
    await tester.tap(find.byKey(const Key('emergency-numbers-action')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('dial-198')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri.parse('tel:198')]);
    // No API call at all.
    expect(h.adapter.requests, isEmpty);
    await unmountApp(tester);
  });

  testWidgets('SOS from home is sent in 2 taps (NFR-09: ≤ 3)', (tester) async {
    final h = await pumpApp(tester, prefs: onboardedPrefs());
    expect(find.byType(HomeScreen), findsOneWidget);
    var taps = 0;
    await tester.tap(find.byKey(const Key('sos-button')));
    taps++;
    await tester.pump();
    expect(h.sos.calls, 0); // first tap only arms the button
    await tester.tap(find.byKey(const Key('sos-button')));
    taps++;
    await tester.pumpAndSettle();
    expect(h.sos.calls, 1);
    expect(taps, lessThanOrEqualTo(3));
    expect(find.text('TMP-ABC234'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('SOS from another main screen: FAB + confirm (2 taps)', (
    tester,
  ) async {
    final h = await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    await tester.tap(find.text('Mes signalements').last);
    await tester.pumpAndSettle();
    var taps = 1;
    await tester.tap(find.byKey(const Key('sos-fab')));
    taps++;
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-confirm')));
    taps++;
    await tester.pumpAndSettle();
    expect(h.sos.calls, 1);
    expect(
      taps - 1,
      lessThanOrEqualTo(3),
    ); // the tab switch is navigation, not SOS
    await unmountApp(tester);
  });

  testWidgets('a long press on the SOS button sends at once', (tester) async {
    final h = await pumpApp(tester, prefs: onboardedPrefs());
    await tester.longPress(find.byKey(const Key('sos-button')));
    await tester.pumpAndSettle();
    expect(h.sos.calls, 1);
    await unmountApp(tester);
  });

  testWidgets('Arabic (default) renders right-to-left', (tester) async {
    await pumpApp(tester, prefs: onboardedPrefs());
    final context = tester.element(find.byType(HomeScreen));
    expect(Directionality.of(context), TextDirection.rtl);
    expect(find.text('ء-حماية'), findsWidgets);
    await unmountApp(tester);
  });

  testWidgets('French renders left-to-right', (tester) async {
    await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    final context = tester.element(find.byType(HomeScreen));
    expect(Directionality.of(context), TextDirection.ltr);
    await unmountApp(tester);
  });

  testWidgets('language switch in settings is applied and persisted', (
    tester,
  ) async {
    await pumpApp(tester, prefs: onboardedPrefs());
    await tester.tap(find.text('الإعدادات').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('language-en')));
    await tester.pumpAndSettle();
    expect(find.text('Settings'), findsWidgets);
    final context = tester.element(find.text('Settings').first);
    expect(Directionality.of(context), TextDirection.ltr);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('settings.locale'), 'en');
    await unmountApp(tester);
  });
}
