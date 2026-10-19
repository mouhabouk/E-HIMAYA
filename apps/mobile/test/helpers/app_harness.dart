import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:ehimaya/app.dart';
import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/auth/oidc_client.dart';
import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/api_client.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/core/sync/sync_scheduler.dart';
import 'package:ehimaya/features/emergency/dialer.dart';
import 'package:ehimaya/features/institution/institution_providers.dart';
import 'package:ehimaya/features/sos/sos_service.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_http.dart';

class FakeSosService implements SosService {
  int calls = 0;
  final List<String?> organizations = [];
  @override
  Future<SosResult> send({String? organizationId}) async {
    calls++;
    organizations.add(organizationId);
    return const SosQueued('TMP-ABC234');
  }
}

class FakeLocationService extends LocationService {
  @override
  Future<LocationAvailability> ensurePermission() async =>
      LocationAvailability.granted;
  @override
  Future<GeoPoint?> current({Duration timeout = Duration.zero}) async =>
      const GeoPoint(lat: 36.8, lon: 10.18, accuracyM: 8);
  @override
  Future<GeoPoint?> lastKnown() async => null;
}

class FakeConnectivity implements ConnectivityMonitor {
  @override
  Future<bool> isOnline() async => true;
  @override
  Stream<bool> get onlineChanges => const Stream.empty();
}

class FakeOidc implements OidcClient {
  @override
  Future<void> endSession(AuthSession session) async {}
  @override
  Future<AuthSession> login({bool register = false}) async =>
      throw const OidcCancelled();
  @override
  Future<AuthSession> refresh(AuthSession session) async =>
      throw const OidcSessionExpired();
}

/// Preferences of a user who accepted the charter and continues anonymously.
Map<String, Object> onboardedPrefs({String locale = 'ar'}) => {
  'charter.accepted_version': '2026-10',
  'charter.accepted_at': '2026-10-19T10:00:00Z',
  'onboarding.role': 'citizen',
  'onboarding.identity_mode': 'anonymous',
  'settings.locale': locale,
};

class AppHarness {
  AppHarness(this.db, this.sos, this.dialled, this.adapter);
  final AppDatabase db;
  final FakeSosService sos;
  final List<Uri> dialled;
  final FakeAdapter adapter;
}

/// Preferences of a signed-in citizen (the profile form was already offered).
Map<String, Object> registeredPrefs({String locale = 'ar'}) => {
  'charter.accepted_version': '2026-10',
  'charter.accepted_at': '2026-10-19T10:00:00Z',
  'onboarding.role': 'citizen',
  'onboarding.identity_mode': 'registered',
  'profile.prompted': true,
  'settings.locale': locale,
};

/// Session of a signed-in account (never expires during a test).
final testSession = AuthSession(
  accessToken: 'a.b.c',
  expiresAt: DateTime(2100),
);

FakeResponse defaultApiResponse(SeenRequest r) {
  if (r.path == '/api/v1/reports/mine') {
    return const FakeResponse(200, json: {'items': [], 'next_before': null});
  }
  return const FakeResponse(404, json: {'detail': 'not_found'});
}

Future<AppHarness> pumpApp(
  WidgetTester tester, {
  Map<String, Object> prefs = const {},
  AuthSession? session,
  FakeHandler? api,
  MemorySecureStore? secure,
  List<Uri>? opened,
}) async {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  SharedPreferences.setMockInitialValues(prefs);
  final sp = await SharedPreferences.getInstance();
  final db = inMemoryDatabase();
  final sos = FakeSosService();
  final dialled = <Uri>[];
  final adapter = FakeAdapter(api ?? defaultApiResponse);
  addTearDown(db.close);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sp),
        secureStoreProvider.overrideWithValue(secure ?? MemorySecureStore()),
        initialAuthSessionProvider.overrideWithValue(session),
        urlOpenerProvider.overrideWithValue((url) async {
          opened?.add(url);
          return true;
        }),
        databaseProvider.overrideWithValue(db),
        httpAdapterProvider.overrideWithValue(adapter),
        locationServiceProvider.overrideWithValue(FakeLocationService()),
        connectivityProvider.overrideWithValue(FakeConnectivity()),
        oidcClientProvider.overrideWithValue(FakeOidc()),
        sosServiceProvider.overrideWithValue(sos),
        dialerProvider.overrideWithValue((uri) async {
          dialled.add(uri);
          return true;
        }),
        requestSyncProvider.overrideWithValue(() async {}),
      ],
      child: const EHimayaApp(),
    ),
  );
  await tester.pumpAndSettle();
  return AppHarness(db, sos, dialled, adapter);
}

/// Drift stream queries schedule a zero-duration timer on cancel: unmount and flush it.
Future<void> unmountApp(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump(Duration.zero);
}
