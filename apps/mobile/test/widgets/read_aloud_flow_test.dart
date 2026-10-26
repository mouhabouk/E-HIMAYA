// Phase P5a: reading aloud for blind users, flashes for deaf users. Accessibility requirement:
// NFR-09 in docs/01-requirements.html (number 10 among the non-functional requirements of the
// project description).
import 'dart:async';

import 'package:ehimaya/core/a11y/alert_cues.dart';
import 'package:ehimaya/core/a11y/speech.dart';
import 'package:ehimaya/core/push/push_controller.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());

  /// Some pages keep a spinner while the network fails: settle by time, not by frames.
  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }
  }

  Future<void> open(WidgetTester tester, String route) async {
    unawaited(
      GoRouter.of(tester.element(find.byType(Scaffold).first)).push(route),
    );
    await settle(tester);
  }

  ProviderContainer container(WidgetTester tester) =>
      ProviderScope.containerOf(tester.element(find.byType(Scaffold).first));

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'a tip is read aloud in the app language, then stopped',
    (tester) async {
      final speech = FakeSpeech();
      await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        speech: speech,
        overrides: [noPush],
        api: (_) => const FakeResponse.network(),
      );
      await open(tester, '${Routes.tips}/fire');
      final listen = find.byKey(const Key('listen-action'));
      expect(find.byTooltip('Écouter'), findsOneWidget);
      await tester.tap(listen);
      await settle(tester);
      expect(speech.spoken, hasLength(1));
      final (text, lang) = speech.spoken.single;
      expect(lang, 'fr');
      expect(text, contains('À faire'));
      expect(text, contains('198'));
      expect(find.byTooltip('Arrêter la lecture'), findsOneWidget);
      await tester.tap(listen);
      await settle(tester);
      expect(speech.stops, 1);
      expect(find.byTooltip('Écouter'), findsOneWidget);
      // The engine finishing on its own puts the button back too.
      await tester.tap(listen);
      await settle(tester);
      speech.finish();
      await settle(tester);
      expect(find.byTooltip('Écouter'), findsOneWidget);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'no voice for the language: the user is told how to add one',
    (tester) async {
      final speech = FakeSpeech(result: SpeechStart.noVoice);
      await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        speech: speech,
        overrides: [noPush],
        api: (r) => r.path == '/api/v1/alerts/active'
            ? FakeResponse(200, json: [alertJson()])
            : defaultApiResponse(r),
      );
      await open(tester, Routes.alert(alertJson()['id']! as String));
      await tester.tap(find.byKey(const Key('listen-action')));
      await settle(tester);
      expect(find.textContaining('Synthèse vocale'), findsOneWidget);
      expect(find.byTooltip('Écouter'), findsOneWidget);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'an alert is read with its severity, title and text',
    (tester) async {
      final speech = FakeSpeech();
      await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        speech: speech,
        overrides: [noPush],
        api: (r) => r.path == '/api/v1/alerts/active'
            ? FakeResponse(200, json: [alertJson()])
            : defaultApiResponse(r),
      );
      await open(tester, Routes.alert(alertJson()['id']! as String));
      await tester.tap(find.byKey(const Key('listen-action')));
      await settle(tester);
      expect(
        speech.spoken.single.$1,
        'Alerte rouge, Fortes pluies\nAlerte pluies abondantes\nÉvitez les oueds',
      );
      // Leaving the page stops the voice.
      await tester.binding.handlePopRoute();
      await settle(tester);
      expect(speech.stops, 1);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'accessibility settings: cues are off until chosen, then tried',
    (tester) async {
      final speech = FakeSpeech();
      final torch = FakeTorch();
      await pumpApp(
        tester,
        prefs: onboardedPrefs(),
        speech: speech,
        torch: torch,
        overrides: [noPush],
      );
      await tester.tap(find.text('الإعدادات'));
      await settle(tester);
      await tester.scrollUntilVisible(
        find.byKey(const Key('settings-accessibility')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('settings-accessibility')));
      await settle(tester);
      expect(find.text('النفاذ'), findsOneWidget);

      await tester.tap(find.byKey(const Key('a11y-try')));
      await settle(tester);
      expect(find.text('اختر وسيلة واحدة على الأقل.'), findsOneWidget);
      expect(speech.spoken, isEmpty);

      for (final k in [
        'a11y-screen-flash',
        'a11y-torch-flash',
        'a11y-read-alerts',
      ]) {
        await tester.tap(find.byKey(Key(k)));
        await settle(tester);
      }
      final c = container(tester);
      final cues = c.read(a11yCuesProvider);
      expect(
        [cues.screenFlash, cues.torchFlash, cues.readAlerts],
        [true, true, true],
      );

      await tester.tap(find.byKey(const Key('a11y-try')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 250));
      expect(find.byKey(const Key('screen-flash')), findsOneWidget);
      expect(torch.flashes, 1);
      expect(speech.spoken.single, (
        'تنبيه تجريبي من ء-حماية. لا يوجد أي خطر.',
        'ar',
      ));
      // Three pulses at one per second, then the veil is gone.
      await tester.pump(const Duration(seconds: 3));
      expect(find.byKey(const Key('screen-flash')), findsNothing);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'no camera light: its switch is disabled',
    (tester) async {
      await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        torch: FakeTorch(present: false),
        overrides: [noPush],
      );
      await open(tester, Routes.accessibility);
      expect(find.text('No light on this phone'), findsOneWidget);
      final s = tester.widget<Switch>(
        find.byKey(const Key('a11y-torch-flash')),
      );
      expect(s.onChanged, isNull);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'an urgent push brings the chosen cues; an ordinary one none',
    (tester) async {
      final speech = FakeSpeech();
      final torch = FakeTorch();
      await pumpApp(
        tester,
        prefs: {
          ...onboardedPrefs(locale: 'fr'),
          'a11y.screen_flash': true,
          'a11y.read_alerts': true,
        },
        speech: speech,
        torch: torch,
        overrides: [noPush],
      );
      final controller = container(tester).read(pushControllerProvider);
      controller.handleReceived(
        PushPayload.parse(
          {'type': 'info'},
          title: 'Journée portes ouvertes',
          body: 'Samedi',
        )!,
      );
      await tester.pump(const Duration(milliseconds: 250));
      expect(find.byKey(const Key('screen-flash')), findsNothing);
      expect(speech.spoken, isEmpty);

      controller.handleReceived(
        PushPayload.parse(
          {'type': 'alert', 'id': 'a1'},
          title: 'Alerte rouge',
          body: 'Évitez les oueds',
        )!,
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 250));
      expect(find.byKey(const Key('screen-flash')), findsOneWidget);
      expect(speech.spoken.single, ('Alerte rouge. Évitez les oueds', 'fr'));
      // The camera light was not chosen.
      expect(torch.flashes, 0);
      await tester.pump(const Duration(seconds: 3));
      await settle(tester);
      await unmountApp(tester);
    },
  );
}
