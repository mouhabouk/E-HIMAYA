// covers: phase A (docs/phase-a/design.md): first launch, phone sign-in, home, location strip,
// colours, update sheet, large text, required fields.
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/ui/required_label.dart';
import 'package:ehimaya/features/charter/charter_screen.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/onboarding/sign_in_screen.dart';
import 'package:ehimaya/features/welcome/intro_screen.dart';
import 'package:ehimaya/features/welcome/language_screen.dart';
import 'package:ehimaya/features/welcome/permissions_screen.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

class _LocationOff extends FakeLocationService {
  int settingsOpened = 0;
  @override
  Future<LocationAvailability> status() async =>
      LocationAvailability.serviceDisabled;
  @override
  Future<bool> openSettings() async {
    settingsOpened++;
    return true;
  }
}

FakeHandler _release({required int latest, required int min}) =>
    (r) => r.path == '/api/v1/app/version'
    ? FakeResponse(
        200,
        json: {
          'latest_version': '0.5.0',
          'latest_build': latest,
          'min_build': min,
          'notes': {'fr': 'Nouveautés de test', 'ar': 'جديد', 'en': 'New'},
          'channel': 'server',
          'download_url': 'https://apk.test/ehimaya-0.5.0.apk',
          'update_available': true,
          'mandatory': min > latest,
          'sms_simulated': true,
        },
      )
    : defaultApiResponse(r);

void main() {
  testWidgets('first launch: language, intro, terms, permissions, phone '
      'sign-in with the [SIM] code', (tester) async {
    var codeRequests = 0;
    final h = await pumpApp(
      tester,
      api: (r) {
        if (r.path.endsWith('/protocol/openid-connect/token')) {
          if (!r.text.contains('otp=')) {
            codeRequests++;
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
        return defaultApiResponse(r);
      },
    );

    // 1. Language, with the emergency numbers already one tap away.
    expect(find.byType(LanguageScreen), findsOneWidget);
    expect(find.byKey(const Key('emergency-numbers-action')), findsOneWidget);
    await tester.tap(find.byKey(const Key('language-choice-fr')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('language-continue')));
    await tester.pumpAndSettle();

    // 2. Introduction cards (skippable).
    expect(find.byType(IntroScreen), findsOneWidget);
    expect(find.byKey(const Key('intro-card-1')), findsOneWidget);
    await tester.tap(find.byKey(const Key('intro-skip')));
    await tester.pumpAndSettle();

    // 3. Terms: read to the end, tick, accept.
    expect(find.byType(CharterScreen), findsOneWidget);
    await tester.drag(
      find.byKey(const Key('terms-text')),
      const Offset(0, -20000),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('charter-checkbox')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('charter-continue')));
    await tester.pumpAndSettle();

    // 4. Permissions, each explained; continue without granting any.
    expect(find.byType(PermissionsScreen), findsOneWidget);
    expect(find.byKey(const Key('perm-location')), findsOneWidget);
    await tester.tap(find.byKey(const Key('permissions-continue')));
    await tester.pumpAndSettle();

    // 5. Phone number, then the code (simulated gateway: amber [SIM] banner).
    expect(find.byType(SignInScreen), findsOneWidget);
    await tester.enterText(find.byKey(const Key('signin-phone')), '22 333 444');
    await tester.tap(find.byKey(const Key('signin-send')));
    await tester.pumpAndSettle();
    expect(codeRequests, 1);
    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    expect(find.textContaining('+21622333444'), findsOneWidget);
    final send = h.adapter.requests.last;
    expect(send.text, contains('grant_type=password'));
    expect(send.text, contains('client_id=ehimaya-mobile'));

    await tester.enterText(find.byKey(const Key('signin-code')), '123456');
    await tester.pumpAndSettle();
    expect(find.byType(SignInScreen), findsNothing);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('onboarding.identity_mode'), 'registered');
    expect(prefs.getString('settings.locale'), 'fr');
    await unmountApp(tester);
  });

  testWidgets('a wrong code says how many tries are left', (tester) async {
    await pumpApp(
      tester,
      prefs: {
        ...languageAndIntroDone,
        'welcome.permissions_seen': true,
        'charter.accepted_version': '2026-11',
        'charter.accepted_at': '2026-10-19T10:00:00Z',
        'settings.locale': 'fr',
      },
      api: (r) {
        if (r.path.endsWith('/protocol/openid-connect/token')) {
          return r.text.contains('otp=')
              ? const FakeResponse(
                  401,
                  json: {'error': 'invalid_grant', 'tries_left': 2},
                )
              : const FakeResponse(
                  400,
                  json: {
                    'error': 'otp_sent',
                    'expires_in': 300,
                    'resend_after': 60,
                    'sms_simulated': false,
                  },
                );
        }
        return defaultApiResponse(r);
      },
    );
    expect(find.byType(SignInScreen), findsOneWidget);
    await tester.enterText(find.byKey(const Key('signin-phone')), '98123456');
    await tester.tap(find.byKey(const Key('signin-send')));
    await tester.pumpAndSettle();
    // A real SMS provider: no simulation banner.
    expect(find.byKey(const Key('sim-banner')), findsNothing);
    expect(
      tester
          .widget<TextButton>(find.byKey(const Key('signin-resend')))
          .onPressed,
      isNull,
    );
    await tester.enterText(find.byKey(const Key('signin-code')), '000000');
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('signin-error')), findsOneWidget);
    expect(find.textContaining('2'), findsWidgets);
    expect(find.byType(SignInScreen), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('home: 198, 197 and the SOS message are one tap away', (
    tester,
  ) async {
    final h = await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    expect(find.byType(HomeScreen), findsOneWidget);
    await tester.tap(find.byKey(const Key('home-call-198')));
    await tester.pumpAndSettle();
    await scrollHomeTo(tester, 'home-dial-197');
    await tester.tap(find.byKey(const Key('home-dial-197')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri.parse('tel:198'), Uri.parse('tel:197')]);

    await tester.tap(find.byKey(const Key('home-sos-message')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sos-confirm')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('location off: amber strip with a shortcut to the settings', (
    tester,
  ) async {
    final location = _LocationOff();
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'fr'),
      location: location,
    );
    expect(find.byKey(const Key('location-off')), findsOneWidget);
    expect(find.byKey(const Key('location-on')), findsNothing);
    await tester.tap(find.byKey(const Key('location-turn-on')));
    await tester.pumpAndSettle();
    expect(location.settingsOpened, 1);
    await unmountApp(tester);
  });

  testWidgets('location on: green strip', (tester) async {
    await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    expect(find.byKey(const Key('location-on')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('day/night toggle and the colour palette are kept', (
    tester,
  ) async {
    await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    Brightness brightness() =>
        Theme.of(tester.element(find.byType(HomeScreen))).brightness;
    final before = brightness();
    await tester.tap(find.byKey(const Key('theme-toggle')));
    await tester.pumpAndSettle();
    expect(brightness(), isNot(before));

    await tester.tap(find.text('Paramètres').last);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('palette-green')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('palette-green')));
    await tester.pumpAndSettle();
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('settings.palette'), 'green');
    await unmountApp(tester);
  });

  testWidgets('optional update: what is new, and "later"', (tester) async {
    final opened = <Uri>[];
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'fr'),
      api: _release(latest: 4, min: 1),
      opened: opened,
    );
    expect(find.byKey(const Key('update-optional')), findsOneWidget);
    expect(find.text('Nouveautés de test'), findsOneWidget);
    await tester.tap(find.byKey(const Key('update-later')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('update-optional')), findsNothing);
    expect(opened, isEmpty);
    await unmountApp(tester);
  });

  testWidgets('mandatory update: no "later", 198 still reachable', (
    tester,
  ) async {
    final opened = <Uri>[];
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'fr'),
      api: _release(latest: 4, min: 4),
      opened: opened,
    );
    expect(find.byKey(const Key('update-mandatory')), findsOneWidget);
    expect(find.byKey(const Key('update-later')), findsNothing);
    await tester.tap(find.byKey(const Key('update-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri.parse('tel:198')]);
    await tester.tap(find.byKey(const Key('update-now')));
    await tester.pumpAndSettle();
    expect(opened, [Uri.parse('https://apk.test/ehimaya-0.5.0.apk')]);
    await unmountApp(tester);
  });

  testWidgets('home at 200% text size: no overflow', (tester) async {
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await pumpApp(tester, prefs: onboardedPrefs());
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
    await unmountApp(tester);
  });

  testWidgets('a required field is announced as required', (tester) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      const MaterialApp(
        locale: Locale('fr'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(
          body: Column(children: [RequiredNote(), RequiredLabel('Nom')]),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('required-note')), findsOneWidget);
    expect(find.bySemanticsLabel('Nom, obligatoire'), findsOneWidget);
    semantics.dispose();
  });
}
