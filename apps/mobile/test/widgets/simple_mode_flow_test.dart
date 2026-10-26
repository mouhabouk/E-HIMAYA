// covers: phase P5b (docs/phase-p5/design-simple.md): the simplified home (F-APP-142, NFR-09 in
// docs/01-requirements.html), rating the app and the introduction tour again (F-APP-143), an
// institution registering from the phone with its work e-mail confirmed by code (F-APP-12,
// FR-A-002).
import 'dart:async';

import 'package:ehimaya/core/config/app_config.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/home/simple_home.dart';
import 'package:ehimaya/features/onboarding/institution_screen.dart';
import 'package:ehimaya/features/onboarding/sign_in_screen.dart';
import 'package:ehimaya/features/settings/settings_screen.dart';
import 'package:ehimaya/features/welcome/intro_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

void main() {
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

  Future<void> goTo(WidgetTester tester, String route) async {
    GoRouter.of(tester.element(find.byType(Scaffold).first)).go(route);
    await settle(tester);
  }

  Future<void> tapVisible(WidgetTester tester, Key key) async {
    // Long lists build lazily: scroll until the target exists.
    if (find.byKey(key).evaluate().isEmpty) {
      await tester.scrollUntilVisible(
        find.byKey(key),
        300,
        scrollable: find.byType(Scrollable).last,
      );
    }
    await tester.ensureVisible(find.byKey(key));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.byKey(key));
    await settle(tester);
  }

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'simplified home: five large buttons, 198 dialled, back to all options',
    (tester) async {
      final h = await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
      expect(find.byKey(const Key('home-new-report')), findsOneWidget);

      await open(tester, Routes.accessibility);
      await tester.tap(find.byKey(const Key('a11y-simple-mode')));
      await settle(tester);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('a11y.simple_mode'), isTrue);
      await tester.binding.handlePopRoute();
      await settle(tester);

      expect(find.byType(SimpleHomeScreen), findsOneWidget);
      for (final key in [
        'simple-alerts',
        'simple-what-to-do',
        'simple-sos-message',
        'simple-report',
        'simple-call-198',
      ]) {
        final button = find.byKey(Key(key));
        expect(button, findsOneWidget);
        expect(tester.getSize(button).height, greaterThanOrEqualTo(88));
      }
      expect(find.text('Signaler un danger'), findsOneWidget);
      expect(find.byKey(const Key('home-new-report')), findsNothing);
      // One hand: the call button sits in the lower half of the screen.
      final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
      expect(
        tester.getCenter(find.byKey(const Key('simple-call-198'))).dy,
        greaterThan(screen.height / 2),
      );

      await tapVisible(tester, const Key('simple-call-198'));
      expect(h.dialled, [Uri.parse('tel:198')]);

      await tapVisible(tester, const Key('simple-show-all'));
      expect(find.byType(SimpleHomeScreen), findsNothing);
      expect(find.byType(HomeScreen), findsOneWidget);
      expect(find.byKey(const Key('home-new-report')), findsOneWidget);
      expect(prefs.getBool('a11y.simple_mode'), isFalse);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'simplified home: report and what-to-do open their screens',
    (tester) async {
      await pumpApp(
        tester,
        prefs: {
          ...onboardedPrefs(locale: 'fr'),
          'a11y.simple_mode': true,
        },
      );
      expect(find.byType(SimpleHomeScreen), findsOneWidget);
      await tapVisible(tester, const Key('simple-what-to-do'));
      expect(find.byType(SimpleHomeScreen), findsNothing);
      await tester.binding.handlePopRoute();
      await settle(tester);
      await tapVisible(tester, const Key('simple-report'));
      expect(find.byType(SimpleHomeScreen), findsNothing);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'rate the app: stars required, then sent with the build',
    (tester) async {
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        api: (r) => r.path == '/api/v1/app/feedback'
            ? const FakeResponse(
                201,
                json: {
                  'id': 'f1',
                  'stars': 4,
                  'created_at': '2026-10-26T10:00:00Z',
                },
              )
            : defaultApiResponse(r),
      );
      await goTo(tester, Routes.settings);
      await tapVisible(tester, const Key('settings-rate'));
      expect(find.text('Évaluer l\'application'), findsWidgets);

      await tester.tap(find.byKey(const Key('rate-send')));
      await settle(tester);
      expect(find.text("Choisissez un nombre d'étoiles."), findsOneWidget);
      expect(
        h.adapter.requests.where((r) => r.path == '/api/v1/app/feedback'),
        isEmpty,
      );

      expect(find.byTooltip('4 sur 5'), findsOneWidget);
      await tester.tap(find.byKey(const Key('rate-star-4')));
      await settle(tester);
      await tester.enterText(
        find.byKey(const Key('rate-remark')),
        'Très clair',
      );
      await tester.tap(find.byKey(const Key('rate-send')));
      await settle(tester);
      final sent = h.adapter.requests.singleWhere(
        (r) => r.path == '/api/v1/app/feedback',
      );
      expect(sent.json, {
        'stars': 4,
        'remark': 'Très clair',
        'platform': 'android',
        'build': AppConfig.appBuild,
        'version': AppConfig.appVersion,
        'locale': 'fr',
      });
      expect(find.byType(SettingsScreen), findsOneWidget);
      expect(find.text('Merci, votre évaluation est envoyée.'), findsOneWidget);
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'the introduction tour again from the settings',
    (tester) async {
      await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
      await goTo(tester, Routes.settings);
      await tapVisible(tester, const Key('settings-intro'));
      expect(find.byType(IntroScreen), findsOneWidget);
      expect(find.byKey(const Key('intro-card-1')), findsOneWidget);
      await tester.tap(find.byKey(const Key('intro-skip')));
      await settle(tester);
      expect(find.byType(IntroScreen), findsNothing);
      expect(find.byType(SettingsScreen), findsOneWidget);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('welcome.intro_seen'), isNot(false));
      await unmountApp(tester);
    },
  );

  testWidgets(
    timeout: const Timeout(Duration(seconds: 60)),
    'an institution registers from the phone: number, code, e-mail code, form',
    (tester) async {
      var emailVerified = false;
      final h = await pumpApp(
        tester,
        prefs: {
          ...languageAndIntroDone,
          'welcome.permissions_seen': true,
          'charter.accepted_version': '2026-11',
          'charter.accepted_at': '2026-10-19T10:00:00Z',
          'onboarding.role': 'institution',
          'settings.locale': 'fr',
        },
        api: (r) {
          if (r.path.endsWith('/protocol/openid-connect/token')) {
            if (!r.text.contains('otp=')) {
              return const FakeResponse(
                400,
                json: {
                  'error': 'otp_sent',
                  'expires_in': 300,
                  'resend_after': 60,
                  'sms_simulated': true,
                },
              );
            }
            return const FakeResponse(
              200,
              json: {
                'access_token': 'a.b.c',
                'expires_in': 300,
                'refresh_token': 'r',
                'token_type': 'Bearer',
              },
            );
          }
          if (r.path == '/api/v1/me/email') {
            return FakeResponse(
              200,
              json: {
                'email': emailVerified ? 'direction@hotel-sud.tn' : null,
                'verified': emailVerified,
                'source': emailVerified ? 'code' : null,
              },
            );
          }
          if (r.path == '/api/v1/me/email/code') {
            return const FakeResponse(
              200,
              json: {'sent': true, 'expires_at': '2026-10-26T10:10:00Z'},
            );
          }
          if (r.path == '/api/v1/me/email/verify') {
            final ok = (r.json! as Map)['code'] == '654321';
            if (!ok) {
              return const FakeResponse(422, json: {'detail': 'invalid_code'});
            }
            emailVerified = true;
            return const FakeResponse(
              200,
              json: {
                'email': 'direction@hotel-sud.tn',
                'verified': true,
                'source': 'code',
              },
            );
          }
          if (r.path == '/api/v1/orgs/mine') {
            return const FakeResponse(200, json: []);
          }
          return defaultApiResponse(r);
        },
      );
      await settle(tester);
      expect(find.byType(InstitutionScreen), findsOneWidget);
      expect(find.textContaining('depuis le téléphone'), findsOneWidget);
      expect(find.byKey(const Key('institution-login')), findsOneWidget);

      await tester.tap(find.byKey(const Key('institution-register')));
      await settle(tester);
      expect(find.byType(SignInScreen), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('signin-phone')),
        '98 123 456',
      );
      await tester.tap(find.byKey(const Key('signin-send')));
      await settle(tester);
      await tester.enterText(find.byKey(const Key('signin-code')), '123456');
      await settle(tester);

      // Signed in, still an institution, and on the registration: the e-mail comes first.
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('onboarding.role'), 'institution');
      expect(find.byKey(const Key('email-confirm')), findsOneWidget);
      expect(find.byKey(const Key('org-register-form')), findsNothing);

      await tester.enterText(
        find.byKey(const Key('email-address')),
        'pas-un-mail',
      );
      await tester.tap(find.byKey(const Key('email-send-code')));
      await settle(tester);
      expect(find.byKey(const Key('email-error')), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('email-address')),
        'Direction@Hotel-Sud.tn',
      );
      await tester.tap(find.byKey(const Key('email-send-code')));
      await settle(tester);
      final codeRequest = h.adapter.requests.singleWhere(
        (r) => r.path == '/api/v1/me/email/code',
      );
      expect(codeRequest.json, {
        'email': 'direction@hotel-sud.tn',
        'locale': 'fr',
      });
      expect(find.byKey(const Key('email-code-sent')), findsOneWidget);

      await tester.enterText(find.byKey(const Key('email-code')), '111111');
      await tester.tap(find.byKey(const Key('email-verify')));
      await settle(tester);
      expect(find.text('Code incorrect.'), findsOneWidget);

      await tester.enterText(find.byKey(const Key('email-code')), '654321');
      await tester.tap(find.byKey(const Key('email-verify')));
      await settle(tester);
      expect(find.byKey(const Key('email-confirm')), findsNothing);
      expect(find.byKey(const Key('org-register-form')), findsOneWidget);
      await unmountApp(tester);
    },
  );
}
