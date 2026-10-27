import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/staff_app.dart';
import 'package:ehimaya/staff/staff_capture.dart';
import 'package:ehimaya/staff/staff_controller.dart';
import 'package:ehimaya/staff/staff_models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

/// Keycloak's device grant and `/api/v1/crew`, in memory (phase P4a).
class FakeCrewServer {
  FakeCrewServer() {
    adapter = FakeAdapter(_handle);
  }

  late final FakeAdapter adapter;

  /// Polls answered "authorization_pending" before the grant.
  int pendingPolls = 1;
  bool revoked = false;
  bool refuseRefresh = false;
  int refreshes = 0;
  bool shiftOpen = false;
  final missions = <Map<String, dynamic>>[];
  final writes = <SeenRequest>[];

  Dio dio() => Dio()..httpClientAdapter = adapter;

  static const vehicle = {
    'id': 'v-1',
    'label': 'FPT 12',
    'kind': 'fire_engine',
    'unit_name': 'Unité Tunis-Centre',
    'status': 'available',
    'on_shift': false,
  };

  Map<String, dynamic> get _shift => {
    'id': 'sh-1',
    'resource': {
      'id': 'v-1',
      'label': 'FPT 12',
      'kind': 'fire_engine',
      'unit_name': 'Unité Tunis-Centre',
    },
    'crew_size': 5,
    'crew_names': null,
    'started_at': '2026-10-26T08:00:00Z',
    'ended_at': null,
  };

  static Map<String, dynamic> mission({
    String id = 'm-1',
    String status = 'ordered',
    String? acknowledgedAt,
  }) => {
    'id': id,
    'status': status,
    'order': 'Feu de forêt, route de Zaghouan km 4',
    'created_at': '2026-10-26T09:00:00Z',
    'acknowledged_at': acknowledgedAt,
    'en_route_at': null,
    'on_scene_at': null,
    'released_at': null,
    'cancelled_at': null,
    'incident': {
      'id': 'inc-1',
      'category': 'fire',
      'classification': null,
      'title': 'Forest fire',
      'location': {'lat': 36.8, 'lon': 10.18},
      'gouvernorat_code': 11,
      'delegation_ar': 'باب بحر',
      'delegation_fr': 'Bab Bhar',
      'op_level': 2,
      'status': 'open',
    },
    'field_report': null,
    'detailed_report': null,
    'casualties': {
      'injured_light': 0,
      'injured_serious': 0,
      'deceased': 0,
      'rescued': 0,
      'trapped': 0,
      'transported': 0,
    },
    'transports': <Object>[],
    'alerts': <Object>[],
    'attachments': <Object>[],
    'template': fireTemplate,
    'contact_phone': null,
    'distance_m': null,
  };

  /// The model fire template [SIM]: one question of each shape.
  static const fireTemplate = {
    'id': 'tpl-fire',
    'category': 'fire',
    'classification': null,
    'version': 1,
    'status': 'approved',
    'simulated': true,
    'fields': [
      {
        'key': 'place',
        'type': 'single',
        'label': {'ar': 'المكان', 'fr': 'Lieu', 'en': 'Place'},
        'required': true,
        'options': [
          {
            'key': 'home',
            'label': {'ar': 'مسكن', 'fr': 'Logement', 'en': 'Home'},
          },
          {
            'key': 'forest',
            'label': {'ar': 'غابة', 'fr': 'Forêt', 'en': 'Forest'},
          },
        ],
      },
      {
        'key': 'spread_risk',
        'type': 'yesno',
        'label': {
          'ar': 'خطر الانتشار',
          'fr': 'Risque de propagation',
          'en': 'Risk of spreading',
        },
      },
      {
        'key': 'area_ha',
        'type': 'count',
        'label': {'ar': 'المساحة', 'fr': 'Surface', 'en': 'Area'},
        'unit': {'ar': 'هكتار', 'fr': 'ha', 'en': 'ha'},
      },
    ],
  };

  static const hospitals = [
    {
      'id': 'h-1',
      'name': 'Hôpital Charles Nicolle',
      'phone': null,
      'distance_m': 1200,
      'simulated': true,
    },
    {
      'id': 'h-2',
      'name': 'Hôpital La Rabta',
      'phone': null,
      'distance_m': 2600,
      'simulated': true,
    },
  ];

  FakeResponse _handle(SeenRequest r) {
    final p = r.path;
    if (p.endsWith('/auth/device')) {
      return const FakeResponse(
        200,
        json: {
          'device_code': 'dc-1',
          'user_code': 'WXYZ-ABCD',
          'verification_uri': 'http://kc/realms/ehimaya-staff/device',
          'verification_uri_complete':
              'http://kc/realms/ehimaya-staff/device?user_code=WXYZ-ABCD',
          'interval': 1,
          'expires_in': 600,
        },
      );
    }
    if (p.endsWith('/openid-connect/token')) {
      final form = Uri.splitQueryString(r.text);
      if (form['grant_type'] == 'refresh_token') {
        refreshes++;
        if (refuseRefresh) {
          return const FakeResponse(400, json: {'error': 'invalid_grant'});
        }
        return const FakeResponse(
          200,
          json: {
            'access_token': 'at-2',
            'refresh_token': 'rt-2',
            'expires_in': 300,
          },
        );
      }
      if (pendingPolls > 0) {
        pendingPolls--;
        return const FakeResponse(
          400,
          json: {'error': 'authorization_pending'},
        );
      }
      return const FakeResponse(
        200,
        json: {
          'access_token': 'at-1',
          'refresh_token': 'rt-1',
          'expires_in': 300,
        },
      );
    }
    if (!p.startsWith('/api/v1/crew')) return const FakeResponse(404);
    if (revoked) {
      return const FakeResponse(410, json: {'detail': 'device_revoked'});
    }
    final sub = p.substring('/api/v1/crew'.length);
    if (r.method == 'POST') writes.add(r);
    switch ((r.method, sub)) {
      case ('POST', '/devices'):
        return const FakeResponse(201, json: {'id': 'dev-1'});
      case ('GET', '/me'):
        return FakeResponse(
          200,
          json: {
            'name': 'Sami Ben Ali',
            'gouvernorat_code': 11,
            'device': {'id': 'dev-1'},
            'shift': shiftOpen ? _shift : null,
          },
        );
      case ('GET', '/resources'):
        return const FakeResponse(200, json: [vehicle]);
      case ('POST', '/shifts'):
        shiftOpen = true;
        return FakeResponse(201, json: _shift);
      case ('POST', '/shifts/current/end'):
        shiftOpen = false;
        return FakeResponse(200, json: _shift);
      case ('GET', '/missions'):
        return FakeResponse(200, json: {'items': missions});
    }
    final m = RegExp(r'^/missions/([^/]+)/(.+)$').firstMatch(sub);
    if (m != null && r.method == 'GET' && m.group(2) == 'hospitals') {
      return const FakeResponse(200, json: hospitals);
    }
    if (m != null && r.method == 'POST') {
      final i = missions.indexWhere((x) => x['id'] == m.group(1));
      if (i < 0) return const FakeResponse(404, json: {'detail': 'not_found'});
      final x = Map<String, dynamic>.of(missions[i]);
      final now = '2026-10-26T09:3${writes.length % 10}:00Z';
      if (m.group(2) == 'attachments') {
        x['attachments'] = [
          ...x['attachments'] as List,
          {
            'id': 'a-${writes.length}',
            'kind': r.uri.queryParameters['kind'],
            'body': null,
            'duration_s': double.tryParse(
              r.uri.queryParameters['duration_s'] ?? '',
            ),
            'created_at': now,
          },
        ];
        missions[i] = x;
        return FakeResponse(200, json: x);
      }
      final body = r.json! as Map<String, dynamic>;
      switch (m.group(2)) {
        case 'ack':
          x['acknowledged_at'] = '2026-10-26T09:00:10Z';
        case 'status':
          x['status'] = body['status'];
          x['${body['status']}_at'] = now;
        case 'situation':
          if (x['status'] != 'on_scene') {
            return const FakeResponse(409, json: {'detail': 'not_on_scene'});
          }
          x['field_report'] = {
            'kind': x['field_report'] == null ? 'first' : 'update',
            'category': body['category'],
            'severity': body['severity'],
            'backup_needed': body['backup_needed'],
            'backup_kinds': body['backup_kinds'],
            'crew_danger': body['crew_danger'],
            'created_at': now,
          };
        case 'casualties':
          final c = Map<String, dynamic>.of(
            x['casualties'] as Map<String, dynamic>,
          );
          for (final k in CasualtyCounter.values) {
            c[k.wire] = (c[k.wire] as int) + (body[k.wire] as int? ?? 0);
          }
          x['casualties'] = c;
        case 'transports':
          final ref = body['hospital_ref'] as String?;
          x['transports'] = [
            ...x['transports'] as List,
            {
              'id': 't-${(x['transports'] as List).length + 1}',
              'triage': body['triage'],
              'age_band': body['age_band'],
              'sex': body['sex'],
              'hospital': ref == null
                  ? body['hospital']
                  : hospitals.firstWhere((h) => h['id'] == ref)['name'],
              'hospital_ref': ref,
              'created_at': now,
            },
          ];
        case 'alerts':
          x['alerts'] = [
            ...x['alerts'] as List,
            {
              'id': 'al-${writes.length}',
              'kind': body['kind'],
              'items': body['items'],
              'created_at': now,
              'seen_at': null,
              'seen_by_name': null,
            },
          ];
        case 'notes':
          x['attachments'] = [
            ...x['attachments'] as List,
            {
              'id': 'a-${writes.length}',
              'kind': 'text',
              'body': body['body'],
              'created_at': now,
            },
          ];
        case 'detailed-report':
          x['detailed_report'] = {
            'kind': 'detailed',
            'category': 'fire',
            'severity': null,
            'template_id': body['template_id'],
            'template_version': 1,
            'answers': body['answers'],
            'note': body['note'],
            'created_at': now,
          };
      }
      missions[i] = x;
      return FakeResponse(200, json: x);
    }
    return const FakeResponse(404);
  }
}

/// A camera and a microphone that answer at once.
class FakeCapture implements StaffCapture {
  @override
  Future<CapturedMedia?> photo() async => CapturedMedia(
    bytes: Uint8List.fromList([0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3]),
    contentType: 'image/jpeg',
  );

  @override
  Future<CapturedMedia?> voice(BuildContext context) async => CapturedMedia(
    bytes: Uint8List.fromList([0, 0, 0, 0x20, 0x66, 0x74, 0x79, 0x70]),
    contentType: 'audio/mp4',
    durationS: 7.5,
  );
}

/// A clock the tests move by hand (the five-minute lock).
class TestClock {
  DateTime now = DateTime.utc(2026, 10, 26, 9);
  DateTime call() => now;
}

/// Pumps the staff app over [server], with [store] as the phone's keystore.
Future<void> pumpStaffApp(
  WidgetTester tester,
  FakeCrewServer server, {
  MemorySecureStore? store,
  TestClock? clock,
  String locale = 'en',
  List<Uri>? launched,
  LocationService? location,
}) async {
  // A tall phone: the forms fit without scrolling.
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 2.5;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({'settings.locale': locale});
  final prefs = await SharedPreferences.getInstance();
  // The scope is disposed with the tree, and the mission polling with it.
  await tester.pumpWidget(
    ProviderScope(
      key: UniqueKey(),
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        secureStoreProvider.overrideWithValue(store ?? MemorySecureStore()),
        staffDioProvider.overrideWithValue(server.dio()),
        locationServiceProvider.overrideWithValue(
          location ?? FakeLocationService(),
        ),
        staffLauncherProvider.overrideWithValue((uri) async {
          launched?.add(uri);
          return true;
        }),
        staffCaptureProvider.overrideWithValue(FakeCapture()),
      ],
      child: StaffApp(clock: (clock ?? TestClock()).call),
    ),
  );
  await tester.pumpAndSettle();
}

/// A signed-in phone with a PIN (123456) and its device id, as left by a previous launch.
Future<MemorySecureStore> signedInStore({DateTime? expires}) async {
  final store = MemorySecureStore();
  await store.write(
    'staff_tokens_v1',
    '{"a":"at-1","r":"rt-1","e":"${(expires ?? DateTime.utc(2099)).toIso8601String()}"}',
  );
  await store.write('staff_device_v1', 'dev-1');
  return store;
}

Future<void> enterPin(WidgetTester tester, String pin) async {
  await tester.enterText(find.byKey(const Key('staff-pin')), pin);
  await tester.pumpAndSettle();
}
