// covers: phase A (docs/phase-a/design.md): phone sign-in client, app release, version pins,
// no advertising, language action on every screen.
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:ehimaya/core/auth/phone_otp.dart';
import 'package:ehimaya/core/config/app_config.dart';
import 'package:ehimaya/features/update/app_release.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

const _config = AppConfig(
  apiBaseUrl: 'http://api.test',
  tusUrl: 'http://api.test/api/v1/uploads/',
  oidcIssuer: 'http://kc.test/realms/ehimaya-public',
  oidcClientId: 'ehimaya-mobile',
  oidcRedirectUrl: 'tn.gov.protectioncivile.ehimaya:/oauth2redirect',
  mapTileUrl: 'http://tiles.test/{z}/{x}/{y}.png',
  mapAttribution: 'test',
  portalUrl: 'http://portal.test',
);

PhoneOtpClient _client(FakeHandler handler) =>
    PhoneOtpClient(_config, Dio()..httpClientAdapter = FakeAdapter(handler));

void main() {
  group('Tunisian mobile numbers', () {
    test('accepted forms', () {
      for (final raw in [
        '22333444',
        '22 333 444',
        '+21622333444',
        '0021622333444',
      ]) {
        expect(normalizeTunisianMobile(raw), '+21622333444', reason: raw);
      }
      for (final p in ['2', '3', '4', '5', '9']) {
        expect(normalizeTunisianMobile('${p}0000000'), '+216${p}0000000');
      }
    });

    test('refused', () {
      for (final raw in [
        '',
        '7233344',
        '72333444',
        '12333444',
        '223334445',
        '+33612345678',
      ]) {
        expect(normalizeTunisianMobile(raw), isNull, reason: raw);
      }
    });
  });

  group('phone sign-in client (Keycloak direct grant)', () {
    test('code sent: the form, the language and the [SIM] flag', () async {
      final adapter = FakeAdapter(
        (r) => const FakeResponse(
          400,
          json: {
            'error': 'otp_sent',
            'expires_in': 300,
            'resend_after': 60,
            'sms_simulated': true,
          },
        ),
      );
      final client = PhoneOtpClient(
        _config,
        Dio()..httpClientAdapter = adapter,
      );
      final sent = await client.requestCode('+21622333444', 'fr');
      expect(sent.simulated, isTrue);
      expect(sent.resendAfter, const Duration(seconds: 60));
      final r = adapter.requests.single;
      expect(
        r.uri.toString(),
        'http://kc.test/realms/ehimaya-public/protocol/openid-connect/token',
      );
      final form = Uri.splitQueryString(r.text);
      expect(form['grant_type'], 'password');
      expect(form['client_id'], 'ehimaya-mobile');
      expect(form['phone'], '+21622333444');
      expect(form['ui_locales'], 'fr');
      expect(form.containsKey('otp'), isFalse);
    });

    test('errors map to their own messages', () async {
      final cases = {
        'invalid_phone': PhoneOtpError.invalidPhone,
        'otp_too_soon': PhoneOtpError.tooSoon,
        'otp_limit': PhoneOtpError.limit,
        'sms_unavailable': PhoneOtpError.smsUnavailable,
        'otp_expired': PhoneOtpError.expired,
        'something_else': PhoneOtpError.unknown,
      };
      for (final entry in cases.entries) {
        final client = _client(
          (r) => FakeResponse(429, json: {'error': entry.key}),
        );
        await expectLater(
          client.requestCode('+21622333444', 'ar'),
          throwsA(
            isA<PhoneOtpException>().having(
              (e) => e.error,
              'error',
              entry.value,
            ),
          ),
        );
      }
      final offline = _client((r) => const FakeResponse.network());
      await expectLater(
        offline.requestCode('+21622333444', 'ar'),
        throwsA(
          isA<PhoneOtpException>().having(
            (e) => e.error,
            'error',
            PhoneOtpError.network,
          ),
        ),
      );
    });

    test('right code gives a session, a wrong one the tries left', () async {
      final adapter = FakeAdapter((r) {
        final form = Uri.splitQueryString(r.text);
        return form['otp'] == '482913'
            ? const FakeResponse(
                200,
                json: {
                  'access_token': 'h.p.s',
                  'refresh_token': 'refresh',
                  'id_token': 'i.d.t',
                  'expires_in': 300,
                },
              )
            : const FakeResponse(
                401,
                json: {'error': 'invalid_grant', 'tries_left': 2},
              );
      });
      final client = PhoneOtpClient(
        _config,
        Dio()..httpClientAdapter = adapter,
      );
      final now = DateTime.utc(2026, 10, 23, 10);
      final session = await client.verify('+21622333444', '482913', now: now);
      expect(session.accessToken, 'h.p.s');
      expect(session.refreshToken, 'refresh');
      expect(session.expiresAt, now.add(const Duration(minutes: 5)));
      await expectLater(
        client.verify('+21622333444', '000000'),
        throwsA(
          isA<PhoneOtpException>()
              .having((e) => e.error, 'error', PhoneOtpError.wrongCode)
              .having((e) => e.triesLeft, 'tries', 2),
        ),
      );
    });
  });

  group('app release (addition 3)', () {
    Map<String, Object?> json({
      int latest = 1,
      int min = 1,
      String channel = 'server',
    }) => {
      'latest_version': '9.9.9',
      'latest_build': latest,
      'min_build': min,
      'notes': {'ar': 'جديد', 'fr': 'Nouveau', 'en': 'New'},
      'channel': channel,
      'download_url': 'https://downloads.ehimaya.tn/e.apk',
      'sms_simulated': false,
    };

    test('optional and mandatory updates', () {
      final same = AppRelease.tryParse(json(latest: AppConfig.appBuild))!;
      expect(same.updateAvailable, isFalse);
      expect(same.mandatory, isFalse);
      final newer = AppRelease.tryParse(json(latest: AppConfig.appBuild + 1))!;
      expect(newer.updateAvailable, isTrue);
      expect(newer.mandatory, isFalse);
      expect(newer.notesFor('fr'), 'Nouveau');
      final forced = AppRelease.tryParse(
        json(latest: AppConfig.appBuild + 2, min: AppConfig.appBuild + 1),
      )!;
      expect(forced.mandatory, isTrue);
    });

    test('download channel: our server, then the store', () {
      expect(
        AppRelease.tryParse(json())!.updateUri.toString(),
        'https://downloads.ehimaya.tn/e.apk',
      );
      expect(
        AppRelease.tryParse(json(channel: 'play'))!.updateUri.toString(),
        contains('play.google.com/store/apps/details?id=tn.ehimaya.app'),
      );
    });

    test('a malformed answer is ignored', () {
      expect(AppRelease.tryParse({'latest_version': 3}), isNull);
    });
  });

  test('AppConfig version and build match pubspec.yaml', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final match = RegExp(
      r'^version: (\d+\.\d+\.\d+)\+(\d+)$',
      multiLine: true,
    ).firstMatch(pubspec)!;
    expect(AppConfig.appVersion, match.group(1));
    expect(AppConfig.appBuild, int.parse(match.group(2)!));
  });

  // Rule 4: no advertising. The build fails if an advertising or tracking SDK is resolved.
  test('no advertising or tracking SDK in the mobile app', () {
    final lock = File('pubspec.lock').readAsStringSync();
    const banned = [
      'google_mobile_ads',
      'firebase_admob',
      'facebook_audience_network',
      'unity_ads',
      'applovin',
      'ironsource',
      'appodeal',
      'startapp',
      'firebase_analytics',
      'facebook_app_events',
      'appsflyer',
      'adjust_sdk',
      'branch_sdk',
      'mixpanel',
      'amplitude',
    ];
    for (final name in banned) {
      expect(
        lock.contains(RegExp('^  $name:', multiLine: true)),
        isFalse,
        reason: name,
      );
    }
  });

  // Rule 1: every app bar offers the language (full bar or compact menu).
  test('every screen with an app bar offers the language switch', () {
    final files = Directory('lib/features')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'));
    for (final file in files) {
      final source = file.readAsStringSync();
      final bars = 'AppBar('.allMatches(source).length;
      if (bars == 0) continue;
      final language = RegExp(
        r'StandardAppBarActions\(\)|LanguageMenuAction\(\)|LanguageBar\(\)',
      ).allMatches(source).length;
      // WelcomeScaffold puts the bar in the app bar of every first-launch screen.
      expect(language, greaterThanOrEqualTo(bars), reason: file.path);
    }
  });
}
