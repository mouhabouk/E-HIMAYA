import 'dart:io';

import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/push/push_controller.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/core/security/locked_alert.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';
import '../helpers/phase5_fixtures.dart';
import 'phase5_flow_test.dart' show scrollTo;

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());

  Future<void> openSettings(WidgetTester tester, String label) async {
    await tester.tap(find.text(label).last);
    await tester.pumpAndSettle();
  }

  testWidgets('alert check lists blockers, fixes them, sends a test alert', (
    tester,
  ) async {
    final device = FakeDeviceServices(
      health: const AlertHealth(
        notificationsEnabled: true,
        channelImportance: {alertChannelId: 2},
        doNotDisturb: true,
        policyAccess: false,
      ),
    );
    final notifications = RecordingNotifications();
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [
        noPush,
        deviceServicesProvider.overrideWithValue(device),
        pushNotificationsProvider.overrideWithValue(notifications),
      ],
    );
    await openSettings(tester, 'Settings');
    await scrollTo(tester, 'settings-alert-check');
    await tester.tap(find.byKey(const Key('settings-alert-check')));
    await tester.pumpAndSettle();

    expect(find.text('Official alerts are muted'), findsOneWidget);
    expect(find.text('Do Not Disturb is on'), findsOneWidget);
    // FakePushMessaging never started: push reported unavailable.
    expect(
      find.byKey(const Key('alert-issue-pushUnavailable')),
      findsOneWidget,
    );
    // Not a ready volunteer: never asked about battery optimisation.
    expect(find.byKey(const Key('alert-issue-batteryOptimized')), findsNothing);

    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('alert-issue-alertChannelMuted')),
        matching: find.byType(FilledButton),
      ),
    );
    await tester.pumpAndSettle();
    expect(device.opened, ['channel:$alertChannelId']);

    await scrollTo(tester, 'alert-test');
    await tester.tap(find.byKey(const Key('alert-test')));
    await tester.pumpAndSettle();
    final shown = notifications.shown.single;
    expect(shown.channelId, alertChannelId);
    expect(shown.payload.title, 'Test — official alert');
    expect(find.text('Test alert sent.'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('critical alerts: explicit opt-in asks for DND access', (
    tester,
  ) async {
    final device = FakeDeviceServices(
      health: const AlertHealth(policyAccess: false),
    );
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [noPush, deviceServicesProvider.overrideWithValue(device)],
    );
    await openSettings(tester, 'Settings');
    await scrollTo(tester, 'settings-alert-check');
    await tester.tap(find.byKey(const Key('settings-alert-check')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'alert-critical');
    await tester.tap(find.byKey(const Key('alert-critical')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('critical-opt-in')), findsOneWidget);
    // Nothing enabled before the user agrees.
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool('alerts.critical_opt_in'), isNull);
    await tester.tap(find.byKey(const Key('critical-opt-in')));
    await tester.pumpAndSettle();
    expect(device.opened, ['dnd-access']);
    expect(prefs.getBool('alerts.critical_opt_in'), isNull);
    await unmountApp(tester);
  });

  testWidgets('battery saver can be switched on in settings', (tester) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [noPush],
    );
    await openSettings(tester, 'Settings');
    await scrollTo(tester, 'settings-battery-saver');
    await tester.tap(find.byKey(const Key('settings-battery-saver')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('battery-saver-on')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Always on · active'), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('power.battery_saver'), 'on');
    await unmountApp(tester);
  });

  testWidgets('delete account needs the typed word, then back to the charter', (
    tester,
  ) async {
    final harness = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'fr'),
      overrides: [
        noPush,
        pushNotificationsProvider.overrideWithValue(RecordingNotifications()),
        mediaDirProvider.overrideWithValue(
          () async =>
              Directory('${Directory.systemTemp.path}/ehimaya-wipe-none'),
        ),
      ],
      api: (r) => r.path == '/api/v1/me/delete'
          ? const FakeResponse(202, json: {'status': 'deleted'})
          : defaultApiResponse(r),
    );
    await openSettings(tester, 'Paramètres');
    await scrollTo(tester, 'settings-my-data');
    await tester.tap(find.byKey(const Key('settings-my-data')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('my-data-delete')));
    await tester.pumpAndSettle();

    final confirm = find.byKey(const Key('delete-confirm'));
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
    await tester.enterText(
      find.byKey(const Key('delete-confirm-field')),
      'supprim',
    );
    await tester.pump();
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);
    await tester.enterText(
      find.byKey(const Key('delete-confirm-field')),
      'supprimer',
    );
    await tester.pump();
    await tester.tap(confirm);
    // The charter screen may keep a progress indicator running: pump frames, not settle.
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }

    expect(lastTo(harness.adapter, 'POST', '/api/v1/me/delete')!.json, {
      'confirm': 'DELETE',
    });
    expect(find.byKey(const Key('charter-continue')), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('settings.locale'), 'fr');
    expect(prefs.getString('onboarding.role'), isNull);
    await unmountApp(tester);
  });

  testWidgets('download my data shows the JSON', (tester) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [noPush],
      api: (r) => r.path == '/api/v1/me/export'
          ? const FakeResponse(
              200,
              json: {
                'profile': {'full_name': null},
                'reports': [],
              },
            )
          : defaultApiResponse(r),
    );
    await openSettings(tester, 'Settings');
    await scrollTo(tester, 'settings-my-data');
    await tester.tap(find.byKey(const Key('settings-my-data')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('my-data-download')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('my-data-json')), findsOneWidget);
    expect(find.textContaining('"reports": []'), findsOneWidget);
    await unmountApp(tester);
  });

  group('over a locked phone', () {
    final severe = PushPayload.parse(
      {
        'type': 'alert',
        'id': 'a1e70000-0000-4000-8000-000000000001',
        'severity': 'high',
      },
      title: 'Alerte pluies abondantes',
      body: 'Évitez les oueds',
    )!;

    Future<FakeDeviceServices> pumpLocked(
      WidgetTester tester, {
      bool unlockSucceeds = true,
    }) async {
      final device = FakeDeviceServices(
        locked: true,
        unlockSucceeds: unlockSucceeds,
      );
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        overrides: [
          noPush,
          deviceServicesProvider.overrideWithValue(device),
          initialLockedAlertProvider.overrideWithValue(true),
        ],
        api: (r) => r.path == '/api/v1/alerts/active'
            ? FakeResponse(200, json: [alertJson()])
            : defaultApiResponse(r),
      );
      return device;
    }

    testWidgets('only the public alert view, no shell nor navigation', (
      tester,
    ) async {
      await pumpLocked(tester);
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
      expect(find.text('Settings'), findsNothing);
      expect(find.byKey(const Key('alert-tips')), findsNothing);
      // Deep links and pushed routes are sent back to the alert view.
      final context = tester.element(find.byKey(const Key('locked-alert')));
      GoRouter.of(context).go(Routes.myData);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);
      expect(find.byKey(const Key('my-data-download')), findsNothing);
      await unmountApp(tester);
    });

    testWidgets('a cancelled unlock stays on the alert', (tester) async {
      final device = await pumpLocked(tester, unlockSucceeds: false);
      await tester.tap(find.byKey(const Key('locked-alert-open-app')));
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 1);
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);
      // Back also asks for the unlock and stays.
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 2);
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('after the unlock the app opens on the alert', (tester) async {
      final device = await pumpLocked(tester);
      final context = tester.element(find.byKey(const Key('locked-alert')));
      await ProviderScope.containerOf(context)
          .read(pushControllerProvider)
          .handleOpened(severe);
      await tester.pumpAndSettle();
      // English text missing on the server: Arabic fallback, public content only.
      expect(find.text('تجنبوا الأودية'), findsOneWidget);
      await tester.tap(find.byKey(const Key('locked-alert-open-app')));
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 1);
      expect(find.byKey(const Key('locked-alert')), findsNothing);
      // The regular alert screen, inside the unlocked app.
      expect(find.byKey(const Key('alert-tips')), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('push taps: a severe alert stays locked, others need unlock', (
      tester,
    ) async {
      final device = await pumpLocked(tester, unlockSucceeds: false);
      final context = tester.element(find.byKey(const Key('locked-alert')));
      final container = ProviderScope.containerOf(context);
      final controller = container.read(pushControllerProvider);

      await controller.handleOpened(severe);
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 0);
      expect(container.read(lockedAlertProvider).alertId, severe.id);
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);

      await controller.handleOpened(
        PushPayload.parse({'type': 'callout', 'callout_id': 'c1'})!,
      );
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 1);
      expect(find.byKey(const Key('locked-alert')), findsOneWidget);

      device.unlockSucceeds = true;
      await controller.handleOpened(
        PushPayload.parse({'type': 'report_status', 'report_id': 'r1'})!,
      );
      await tester.pumpAndSettle();
      expect(device.unlockRequests, 2);
      expect(find.byKey(const Key('locked-alert')), findsNothing);
      await unmountApp(tester);
    });
  });
}
