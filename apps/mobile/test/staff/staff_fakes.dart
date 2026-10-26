import 'package:dio/dio.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/staff_app.dart';
import 'package:ehimaya/staff/staff_controller.dart';
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
    'casualties': {'injured': 0, 'deceased': 0, 'rescued': 0, 'trapped': 0},
    'transports': <Object>[],
    'distance_m': null,
  };

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
    if (m != null && r.method == 'POST') {
      final i = missions.indexWhere((x) => x['id'] == m.group(1));
      if (i < 0) return const FakeResponse(404, json: {'detail': 'not_found'});
      final x = Map<String, dynamic>.of(missions[i]);
      final body = r.json! as Map<String, dynamic>;
      switch (m.group(2)) {
        case 'ack':
          x['acknowledged_at'] = '2026-10-26T09:00:10Z';
        case 'status':
          x['status'] = body['status'];
        case 'first-report':
          if (x['status'] != 'on_scene') {
            return const FakeResponse(409, json: {'detail': 'not_on_scene'});
          }
          x['field_report'] = {
            'category': body['category'],
            'severity': body['severity'],
            'backup_needed': body['backup_needed'],
            'crew_danger': body['crew_danger'],
          };
        case 'casualties':
          final c = Map<String, dynamic>.of(
            x['casualties'] as Map<String, dynamic>,
          );
          for (final k in ['injured', 'deceased', 'rescued', 'trapped']) {
            c[k] = (c[k] as int) + (body[k] as int? ?? 0);
          }
          x['casualties'] = c;
        case 'transports':
          x['transports'] = [
            ...x['transports'] as List,
            {
              'id': 't-${(x['transports'] as List).length + 1}',
              'triage': body['triage'],
              'age_band': body['age_band'],
              'sex': body['sex'],
              'hospital': body['hospital'],
            },
          ];
      }
      missions[i] = x;
      return FakeResponse(200, json: x);
    }
    return const FakeResponse(404);
  }
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
