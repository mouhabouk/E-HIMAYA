import 'dart:convert';

import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/auth/oidc_client.dart';
import 'package:ehimaya/core/config/app_config.dart';
import 'package:ehimaya/core/config/providers.dart';
import 'package:ehimaya/core/http/api_client.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/institution/institution_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart' show FakeOidc;
import '../helpers/fake_http.dart';
import '../helpers/org_fixtures.dart';

const pendingId = '0d9e8f7a-6b5c-4d3e-8f2a-1b0c9d8e7f6a';

const _config = AppConfig(
  apiBaseUrl: 'http://api.test',
  tusUrl: 'http://tus.test/api/v1/uploads/',
  oidcIssuer: 'http://kc.test/realms/ehimaya-public',
  oidcClientId: 'ehimaya-mobile',
  oidcRedirectUrl: 'tn.ehimaya.app:/oauth2redirect',
  mapTileUrl: 'http://tiles.test/{z}/{x}/{y}.png',
  mapAttribution: 'test',
  portalUrl: 'http://localhost:5174',
);

void main() {
  late FakeAdapter adapter;
  late MemorySecureStore secure;
  late SharedPreferences prefs;

  Future<ProviderContainer> container({
    bool registered = true,
    Map<String, Object> initialPrefs = const {},
    DateTime Function()? clock,
  }) async {
    SharedPreferences.setMockInitialValues({
      'charter.accepted_version': '2026-10',
      'onboarding.role': 'citizen',
      'onboarding.identity_mode': registered ? 'registered' : 'anonymous',
      ...initialPrefs,
    });
    prefs = await SharedPreferences.getInstance();
    final c = ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        secureStoreProvider.overrideWithValue(secure),
        appConfigProvider.overrideWithValue(_config),
        oidcClientProvider.overrideWithValue(FakeOidc()),
        if (clock != null) clockProvider.overrideWithValue(clock),
        httpAdapterProvider.overrideWithValue(adapter),
        initialAuthSessionProvider.overrideWithValue(
          registered
              ? AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100))
              : null,
        ),
      ],
    );
    addTearDown(c.dispose);
    return c;
  }

  setUp(() {
    secure = MemorySecureStore();
    adapter = FakeAdapter((r) {
      if (r.path == '/api/v1/orgs/mine') {
        return FakeResponse(
          200,
          json: [
            orgRow(orgId, 'Société X', 'active'),
            orgRow(pendingId, 'Lycée Y', 'pending_review'),
          ],
        );
      }
      if (r.path == '/api/v1/orgs/$orgId/summary') {
        return FakeResponse(200, json: summaryJson());
      }
      return const FakeResponse(404, json: {'detail': 'not_found'});
    });
  });

  test('fetched after sign-in, cached, only active ones can report', () async {
    final c = await container();
    final orgs = await c.read(myOrgsProvider.future);
    expect(orgs.map((o) => o.name), ['Société X', 'Lycée Y']);
    expect(c.read(activeOrgsProvider).map((o) => o.id), [orgId]);
    expect(c.read(hasInstitutionsProvider), isTrue);
    expect(adapter.requests.single.header('Authorization'), 'Bearer a.b.c');
    final cached = await OrgCache(secure).readMine('sub:unknown');
    expect(cached!.map((o) => o.id), [orgId, pendingId]);
  });

  test('never fetched for anonymous users', () async {
    final c = await container(registered: false);
    expect(await c.read(myOrgsProvider.future), isEmpty);
    expect(c.read(activeOrgsProvider), isEmpty);
    expect(adapter.requests, isEmpty);
  });

  test('offline: the cached list is used', () async {
    await OrgCache(secure).writeMine('sub:unknown', [
      MyOrg.fromJson(orgRow(orgId, 'Société X', 'active')),
    ]);
    adapter.handler = (_) => const FakeResponse.network();
    final c = await container();
    final orgs = await c.read(myOrgsProvider.future);
    expect(orgs.single.name, 'Société X');
    await pumpEventQueue();
    expect(c.read(myOrgsProvider).value!.single.name, 'Société X');
    expect(c.read(activeOrgsProvider).single.id, orgId);
  });

  test('another account never sees the cached list', () async {
    await OrgCache(secure).writeMine('sub:someone-else', [
      MyOrg.fromJson(orgRow(orgId, 'Société X', 'active')),
    ]);
    expect(await OrgCache(secure).readMine('sub:unknown'), isNull);
  });

  test('"report as" choice is persisted and validated', () async {
    final c = await container();
    await c.read(myOrgsProvider.future);
    expect(c.read(reportAsProvider), isNull); // default: myself

    await c.read(reportAsChoiceProvider.notifier).choose(orgId);
    expect(c.read(reportAsProvider), orgId);
    expect(prefs.getString('orgs.report_as'), orgId);

    // Back to myself.
    await c.read(reportAsChoiceProvider.notifier).choose(null);
    expect(prefs.getString('orgs.report_as'), isNull);
    expect(c.read(reportAsProvider), isNull);

    // A new start keeps the last choice.
    final again = await container(initialPrefs: {'orgs.report_as': orgId});
    await again.read(myOrgsProvider.future);
    expect(again.read(reportAsProvider), orgId);

    // An institution that is not active is never used.
    final pending = await container(
      initialPrefs: {'orgs.report_as': pendingId},
    );
    await pending.read(myOrgsProvider.future);
    expect(pending.read(reportAsProvider), isNull);
  });

  test('SOS defaults to myself unless chosen in settings', () async {
    final c = await container(initialPrefs: {'orgs.report_as': orgId});
    await c.read(myOrgsProvider.future);
    // The report form choice does not change the SOS default.
    expect(c.read(sosReportAsProvider), isNull);
    await c.read(sosReportAsChoiceProvider.notifier).choose(orgId);
    expect(c.read(sosReportAsProvider), orgId);
    expect(prefs.getString('orgs.sos_report_as'), orgId);
  });

  test('summary cached, shown offline with its date', () async {
    var now = DateTime.utc(2026, 10, 19, 9);
    final c = await container(clock: () => now);
    final sub = c.listen(orgSummaryProvider(orgId), (_, _) {});
    addTearDown(sub.close);
    final online = await c.read(orgSummaryProvider(orgId).future);
    expect(online.isOffline, isFalse);
    expect(online.summary.name, 'Société X');

    adapter.handler = (_) => const FakeResponse.network();
    now = DateTime.utc(2026, 10, 20);
    c.invalidate(orgSummaryProvider(orgId));
    final offline = await c.read(orgSummaryProvider(orgId).future);
    expect(offline.isOffline, isTrue);
    expect(offline.offlineSince, DateTime.utc(2026, 10, 19, 9));
    expect(offline.summary.team, hasLength(2));
  });

  test('logout deletes the cached institutions and choices', () async {
    final c = await container(
      initialPrefs: {'orgs.report_as': orgId, 'orgs.sos_report_as': orgId},
    );
    await c.read(myOrgsProvider.future);
    expect(secure.values.containsKey(SecureStoreKeys.orgCache), isTrue);
    await c.read(identityProvider.notifier).logout();
    expect(secure.values.containsKey(SecureStoreKeys.orgCache), isFalse);
    expect(prefs.getString('orgs.report_as'), isNull);
    expect(prefs.getString('orgs.sos_report_as'), isNull);
    expect(await c.read(myOrgsProvider.future), isEmpty);
  });

  test('cache entry is JSON tied to its owner', () async {
    final c = await container();
    await c.read(myOrgsProvider.future);
    final raw = jsonDecode(
      secure.values[SecureStoreKeys.orgCache]!,
    ) as Map<String, Object?>;
    expect(raw['owner'], 'sub:unknown');
  });
}
