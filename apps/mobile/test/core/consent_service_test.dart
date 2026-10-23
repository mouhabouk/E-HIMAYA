import 'package:dio/dio.dart';
import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/consent/consent_service.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/fake_http.dart';

void main() {
  late FakeAdapter adapter;
  late AppPrefs prefs;
  late IdentityState identity;
  late ConsentService consent;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = AppPrefs(await SharedPreferences.getInstance());
    adapter = FakeAdapter(
      (_) => const FakeResponse(
        201,
        json: {'charter_version': '2026-11', 'accepted_at': 'x'},
      ),
    );
    identity = const IdentityState(mode: IdentityMode.none);
    consent = ConsentService(
      prefs: prefs,
      api: EHimayaApi(
        Dio(BaseOptions(baseUrl: 'http://api.test'))
          ..httpClientAdapter = adapter,
      ),
      identity: () => identity,
      locale: () => 'fr',
      clock: () => DateTime.utc(2026, 10, 19),
      platform: () => 'android',
    );
  });

  test('accepted locally first, sent once an identity exists', () async {
    await consent.acceptLocally();
    expect(consent.acceptedLocally, isTrue);
    expect(prefs.charterAcceptedVersion, '2026-11');

    // No identity yet: nothing is sent.
    expect(await consent.sendIfNeeded(), isTrue);
    expect(adapter.requests, isEmpty);

    identity = const IdentityState(
      mode: IdentityMode.anonymous,
      role: UserRole.citizen,
    );
    expect(consent.needsServerSend, isTrue);
    expect(await consent.sendIfNeeded(), isTrue);
    expect(adapter.requests.single.json, {
      'charter_version': '2026-11',
      'locale': 'fr',
      'platform': 'android',
    });
    // Same identity: not sent twice.
    await consent.sendIfNeeded();
    expect(adapter.requests, hasLength(1));

    // A new identity (login) sends it again.
    identity = IdentityState(
      mode: IdentityMode.registered,
      role: UserRole.citizen,
      session: AuthSession(accessToken: 'x.y.z', expiresAt: DateTime(2100)),
    );
    await consent.sendIfNeeded();
    expect(adapter.requests, hasLength(2));
  });

  test('offline: reported as not sent, retried later', () async {
    await consent.acceptLocally();
    identity = const IdentityState(
      mode: IdentityMode.anonymous,
      role: UserRole.citizen,
    );
    adapter.handler = (_) => const FakeResponse.network();
    expect(await consent.sendIfNeeded(), isFalse);
    expect(consent.needsServerSend, isTrue);
    adapter.handler = (_) => const FakeResponse(201, json: {});
    expect(await consent.sendIfNeeded(), isTrue);
    expect(consent.needsServerSend, isFalse);
  });
}
