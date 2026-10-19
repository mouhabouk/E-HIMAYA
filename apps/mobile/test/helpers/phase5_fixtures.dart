import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/auth/oidc_client.dart';
import 'package:ehimaya/core/config/app_config.dart';
import 'package:ehimaya/core/config/providers.dart';
import 'package:ehimaya/core/http/api_client.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app_harness.dart' show FakeLocationService, FakeOidc;
import 'fake_http.dart';

const testConfig = AppConfig(
  apiBaseUrl: 'http://api.test',
  tusUrl: 'http://tus.test/api/v1/uploads/',
  oidcIssuer: 'http://kc.test/realms/ehimaya-public',
  oidcClientId: 'ehimaya-mobile',
  oidcRedirectUrl: 'tn.ehimaya.app:/oauth2redirect',
  mapTileUrl: 'http://tiles.test/{z}/{x}/{y}.png',
  mapAttribution: 'test',
  portalUrl: 'http://localhost:5174',
);

/// Push stand-in: a fixed token, nothing delivered.
class FakePushMessaging extends NoPushMessaging {
  FakePushMessaging({this.fixedToken = 'fcm-token-0123456789-abcdefghij'});

  final String? fixedToken;

  @override
  Future<String?> token() async => fixedToken;

  @override
  Future<PushPayload?> launchPayload() async => null;
}

/// A container for provider-level tests (registered citizen unless [registered] is false).
Future<ProviderContainer> phase5Container(
  FakeAdapter adapter, {
  bool registered = true,
  Map<String, Object> prefs = const {},
  DateTime Function()? clock,
  LocationService? location,
  PushMessaging? push,
  SecureStore? secure,
  List<Override> overrides = const [],
}) async {
  SharedPreferences.setMockInitialValues({
    'charter.accepted_version': '2026-10',
    'onboarding.role': 'citizen',
    'onboarding.identity_mode': registered ? 'registered' : 'anonymous',
    ...prefs,
  });
  final sp = await SharedPreferences.getInstance();
  final c = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(sp),
      secureStoreProvider.overrideWithValue(secure ?? MemorySecureStore()),
      appConfigProvider.overrideWithValue(testConfig),
      oidcClientProvider.overrideWithValue(FakeOidc()),
      httpAdapterProvider.overrideWithValue(adapter),
      locationServiceProvider.overrideWithValue(
        location ?? FakeLocationService(),
      ),
      pushMessagingProvider.overrideWithValue(push ?? FakePushMessaging()),
      if (clock != null) clockProvider.overrideWithValue(clock),
      initialAuthSessionProvider.overrideWithValue(
        registered
            ? AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100))
            : null,
      ),
      ...overrides,
    ],
  );
  addTearDown(c.dispose);
  return c;
}

Map<String, Object?> volunteerJson({
  String status = 'approved',
  bool ready = false,
  String? readyUntil,
  String periodFrom = '2026-10-01',
  String? periodTo,
}) => {
  'status': status,
  'skills': ['first_aid', 'diving'],
  'other_skill': null,
  'availability': 'continuous',
  'period_from': periodFrom,
  'period_to': periodTo,
  'notes': null,
  'review_reason': null,
  'submitted_at': '2026-10-01T08:00:00Z',
  'reviewed_at': '2026-10-02T08:00:00Z',
  'ready': ready,
  'ready_until': readyUntil,
  'version': 2,
};

Map<String, Object?> calloutJson({
  String id = 'c0ffee00-0000-4000-8000-000000000001',
  String status = 'open',
  String myStatus = 'sent',
  int? eta,
}) => {
  'id': id,
  'incident_category': 'fire',
  'message': 'حريق في مستودع',
  'skill': 'firefighting',
  'distance_m': 2350,
  'location': {'lat': 34.74, 'lon': 10.76},
  'status': status,
  'my_status': myStatus,
  'eta_minutes': eta,
  'created_at': '2026-10-19T09:00:00Z',
};

Map<String, Object?> alertJson({
  String id = 'a1e70000-0000-4000-8000-000000000001',
  String severity = 'high',
  String expiresAt = '2100-01-01T00:00:00Z',
  List<int> codes = const [61],
}) => {
  'id': id,
  'severity': severity,
  'category': 'weather',
  'hazard': 'heavy_rain',
  'title': {
    'ar': 'تنبيه أمطار غزيرة',
    'fr': 'Alerte pluies abondantes',
    'en': '',
  },
  'body': {'ar': 'تجنبوا الأودية', 'fr': 'Évitez les oueds', 'en': ''},
  'area': {'gouvernorat_codes': codes},
  'published_at': '2026-10-19T08:00:00Z',
  'expires_at': expiresAt,
};

Map<String, Object?> inboxItemJson(String id, {String kind = 'info'}) => {
  'id': id,
  'kind': kind,
  'topic': kind == 'info' ? 'awareness' : null,
  'severity': kind == 'alert' ? 'medium' : null,
  'title': {'ar': 'يوم تحسيسي', 'fr': 'Journée de sensibilisation'},
  'body': {'ar': 'يوم مفتوح', 'fr': 'Journée portes ouvertes'},
  'published_at': '2026-10-18T08:00:00Z',
  'expires_at': null,
  'active': false,
};

Map<String, Object?> tipsJson({int revision = 3}) => {
  'revision': revision,
  'items': [
    {
      'id': 't1',
      'hazard': 'flood',
      'position': 2,
      'content': {
        'ar': {
          'title': 'فيضان',
          'do': ['اصعد إلى مكان مرتفع'],
          'dont': ['لا تعبر الأودية'],
        },
        'fr': {
          'title': 'Inondation',
          'do': ['Montez en hauteur'],
          'dont': ['Ne traversez pas les oueds'],
        },
        'en': {'title': '', 'do': [], 'dont': []},
      },
      'updated_at': '2026-10-19T08:00:00Z',
    },
    {
      'id': 't2',
      'hazard': 'fire',
      'position': 1,
      'content': {
        'ar': {
          'title': 'حريق',
          'do': ['اتصل بالرقم 198'],
          'dont': [],
        },
      },
      'updated_at': '2026-10-19T08:00:00Z',
    },
  ],
};

/// Last request to [path], or null.
SeenRequest? lastTo(FakeAdapter adapter, String method, String path) => adapter
    .requests
    .where((r) => r.method == method && r.path == path)
    .lastOrNull;

/// Shared preferences handle used by a container.
AppPrefs prefsOf(ProviderContainer c) => c.read(appPrefsProvider);
