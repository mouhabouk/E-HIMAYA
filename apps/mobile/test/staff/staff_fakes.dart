import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/staff/mission_box.dart';
import 'package:ehimaya/staff/prevention/prevention_store.dart';
import 'package:ehimaya/staff/prevention/sign_screen.dart';
import 'package:ehimaya/staff/staff_app.dart';
import 'package:ehimaya/staff/staff_capture.dart';
import 'package:ehimaya/staff/staff_config.dart';
import 'package:ehimaya/staff/staff_controller.dart';
import 'package:ehimaya/staff/staff_models.dart';
import 'package:ehimaya/staff/staff_push.dart';
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

  /// The account's field roles (phase P4c: `org_auditor` for inspectors).
  List<String> roles = ['team_leader'];

  /// No network at all: every API call fails as a dropped connection.
  bool down = false;

  /// The name the server gives the inspector who takes a visit.
  String inspectorName = 'Leila Inspectrice';

  /// Prevention visits of the inspector's scope.
  final visits = <Map<String, dynamic>>[];
  final writes = <SeenRequest>[];

  /// Positions received, mission by mission (phase P4d).
  final positions = <String, List<Map<String, dynamic>>>{};

  /// Writes applied once, by `client_id` (a write sent again answers the mission as it is).
  final applied = <String>{};

  /// Phase F: the round button's settings, an agent activated with a code, and the activations
  /// and renewals of its tokens.
  int holdMs = 600;
  int undoSeconds = 0;
  bool activatedAgent = false;
  bool charterAccepted = true;
  String activationCode = 'ABCD-EFGH';
  bool fieldRevoked = false;
  int fieldRefreshes = 0;
  final crewAgents = <Map<String, dynamic>>[
    {'id': 'ag-1', 'name': 'Mounir Haj', 'function': 'driver'},
  ];
  String? pushToken;

  Dio dio() => Dio()..httpClientAdapter = adapter;

  /// The phone's key for its text messages (phase P4d).
  static const smsKey = 'test-sms-key-0123456789abcdef';

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
    if (p == '/api/v1/field/activate') {
      final body = r.json! as Map;
      if (body['code'] != activationCode || body['matricule'] != 'M1234') {
        return const FakeResponse(401, json: {'detail': 'activation_refused'});
      }
      activatedAgent = true;
      charterAccepted = false;
      return FakeResponse(200, json: _fieldTokens('at-f1', 'rf-1'));
    }
    if (p == '/api/v1/field/token') {
      fieldRefreshes++;
      if (fieldRevoked) {
        return const FakeResponse(410, json: {'detail': 'device_revoked'});
      }
      return FakeResponse(200, json: _fieldTokens('at-f2', 'rf-2'));
    }
    if (!p.startsWith('/api/v1/crew')) return const FakeResponse(404);
    if (down) return const FakeResponse.network();
    if (revoked) {
      return const FakeResponse(410, json: {'detail': 'device_revoked'});
    }
    final sub = p.substring('/api/v1/crew'.length);
    if (r.method == 'POST') writes.add(r);
    switch ((r.method, sub)) {
      case ('POST', '/devices'):
        pushToken = (r.json! as Map)['push_token'] as String?;
        return const FakeResponse(201, json: {'id': 'dev-1'});
      case ('PATCH', '/devices/current'):
        pushToken = (r.json! as Map)['push_token'] as String?;
        return const FakeResponse(200, json: {'id': 'dev-1'});
      case ('POST', '/devices/current/sms-key'):
        return const FakeResponse(200, json: {'key': smsKey});
      case ('GET', '/me'):
        return FakeResponse(
          200,
          json: {
            'name': 'Sami Ben Ali',
            'gouvernorat_code': 11,
            'device': {'id': 'dev-1'},
            'shift': shiftOpen ? _shift : null,
            'roles': roles,
            'activated_agent': activatedAgent,
            'charter_accepted': charterAccepted,
            'field': {'hold_ms': holdMs, 'undo_seconds': undoSeconds},
          },
        );
      case ('POST', '/charter'):
        charterAccepted = true;
        return const FakeResponse(204);
      case ('GET', '/agents'):
        return FakeResponse(200, json: crewAgents);
      case ('POST', '/missions/open'):
        final body = r.json! as Map<String, dynamic>;
        final opened = {
          ...mission(id: 'm-open', acknowledgedAt: '2026-10-26T09:00:00Z'),
          'crew_nature': body['nature'],
          'field_initiated': true,
          'target': {'lat': body['lat'], 'lon': body['lon']},
        };
        missions.insert(0, opened);
        return FakeResponse(201, json: opened);
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
      case ('GET', '/prevention/visits'):
        return FakeResponse(
          200,
          json: [
            for (final v in visits)
              if (v['status'] == 'scheduled' || v['status'] == 'inspected') v,
          ],
        );
    }
    final pv = RegExp(r'^/prevention/visits/([^/]+)(?:/(.+))?$')
        .firstMatch(sub);
    if (pv != null) return _visit(r, pv.group(1)!, pv.group(2));
    final m = RegExp(r'^/missions/([^/]+)/(.+)$').firstMatch(sub);
    if (m != null && r.method == 'GET' && m.group(2) == 'hospitals') {
      return const FakeResponse(200, json: hospitals);
    }
    if (m != null && r.method == 'POST') {
      final i = missions.indexWhere((x) => x['id'] == m.group(1));
      if (i < 0) return const FakeResponse(404, json: {'detail': 'not_found'});
      if (m.group(2) == 'positions') {
        final points = [
          for (final p in (r.json! as Map)['points'] as List)
            p as Map<String, dynamic>,
        ];
        positions.putIfAbsent(m.group(1)!, () => []).addAll(points);
        return FakeResponse(200, json: {'accepted': points.length});
      }
      if (m.group(2) == 'voice') {
        return const FakeResponse(
          200,
          json: {
            'voice_id': 'v-1',
            'text': 'تم اخماد الحريق',
            'language': 'ar',
            'model': 'whisper-test',
            'duration_s': 4.2,
          },
        );
      }
      final clientId =
          r.uri.queryParameters['client_id'] ??
          (r.json as Map?)?['client_id'] as String?;
      if (clientId != null && !applied.add(clientId)) {
        return FakeResponse(200, json: missions[i]);
      }
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
        case 'nature':
          x['crew_nature'] = body['nature'];
        case 'skip':
          x['skipped'] = {
            ...x['skipped'] as Map? ?? const {},
            body['step'] as String: body['reason'],
          };
        case 'no-intervention':
          x['no_intervention_reason'] = body['reason'];
          x['status'] = x['status'] == 'on_scene' ? 'released' : 'cancelled';
        case 'toll':
          x['toll'] = {
            'kind': 'toll',
            'category': 'fire',
            'severity': null,
            'answers': {'damage': body['damage']},
            'note': body['description'],
            'created_at': now,
          };
        case 'report':
          x['intervention_report'] = {
            'kind': 'report',
            'category': 'fire',
            'severity': null,
            'note': body['text'],
            'created_at': now,
          };
        case 'ack':
          x['acknowledged_at'] = '2026-10-26T09:00:10Z';
        case 'status':
          x['status'] = body['status'];
          x['${body['status']}_at'] = now;
        case 'milestone':
          final step = body['step'] as String;
          x['${step}_at'] ??= now;
          if ((step == 'available' || step == 'back_at_unit') &&
              x['status'] == 'on_scene') {
            x['status'] = 'released';
            x['released_at'] = now;
          }
        case 'record':
          x['crew_count'] = body['crew_count'];
          x['consumables'] = body['consumables'];
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

Map<String, dynamic> _fieldTokens(String access, String refresh) => {
  'access_token': access,
  'expires_at': '2099-01-01T00:00:00Z',
  'refresh_token': refresh,
  'device_id': 'dev-f',
  'name': 'Mounir Haj',
  'function': 'leader',
  'gouvernorat_code': 11,
  'charter_accepted': false,
};

extension on FakeCrewServer {
  FakeResponse _visit(SeenRequest r, String id, String? action) {
    final i = visits.indexWhere((v) => v['id'] == id);
    if (i < 0) return const FakeResponse(404, json: {'detail': 'not_found'});
    final v = Map<String, dynamic>.of(visits[i]);
    if (action == null) return FakeResponse(200, json: v);
    if (v['taken_by_other'] == true) {
      return const FakeResponse(409, json: {'detail': 'visit_taken'});
    }
    switch (action) {
      case 'claim':
        v['mine'] = true;
        v['inspector_name'] = inspectorName;
      case 'photos':
        final q = r.uri.queryParameters;
        final photos = [...v['photos'] as List];
        if (!photos.any((x) => (x as Map)['id'] == q['client_id'])) {
          photos.add({
            'id': q['client_id'],
            'item_key': q['item_key'],
            'content_type': r.header('content-type'),
            'bytes': r.body?.length ?? 0,
          });
        }
        v['photos'] = photos;
      case 'inspection':
        final body = r.json! as Map<String, dynamic>;
        final items = [
          for (final x in body['items'] as List) x as Map<String, dynamic>,
        ];
        final bad = items.where((x) => x['result'] == 'nonconform').length;
        final good = items.where((x) => x['result'] == 'conform').length;
        v['status'] = 'inspected';
        v['inspected_on'] = body['inspected_on'];
        v['attendees'] = body['attendees'];
        v['comparison'] = {
          'items': items,
          'conform': good,
          'nonconform': bad,
          'not_checked': (v['checklist'] as List).length - good - bad,
          'suggested': bad > 0 ? 'approved_with_reservations' : 'approved',
        };
        v['signatures'] = {
          'representative_name': body['representative_name'],
          'representative_role': body['representative_role'],
        };
      case 'decision':
        if (v['status'] != 'inspected') {
          return const FakeResponse(
            409,
            json: {'detail': 'invalid_transition'},
          );
        }
        final body = r.json! as Map<String, dynamic>;
        v['status'] = 'decided';
        v['decision'] = body['decision'];
        v['checklist'] = <Object>[];
        v['reservations'] = [
          for (final x in body['reservations'] as List)
            {...x as Map<String, dynamic>, 'state': 'open'},
        ];
        if (body['decision'] != 'refused') {
          v['certificate'] = {'code': 'EHP-61-0001'};
        }
    }
    visits[i] = v;
    return FakeResponse(200, json: v);
  }
}

/// A visit the Office scheduled, with a small grid built from the declaration.
Map<String, dynamic> fakeVisit({
  String id = 'vis-1',
  String status = 'scheduled',
  bool mine = false,
  bool takenByOther = false,
}) => {
  'id': id,
  'org_id': 'org-1',
  'origin': 'office',
  'status': status,
  'org_name': 'Hôtel Les Palmiers',
  'org_kind': 'tourism',
  'org_status': 'active',
  'org_address': 'Route de la plage, Sfax',
  'org_location': {'lat': 34.74, 'lon': 10.76},
  'gouvernorat_code': 61,
  'scheduled_on': '2026-10-27',
  'inspector_name': 'Cdt Ben Salah',
  'mine': mine,
  'taken_by_other': takenByOther,
  'inspector_on_phone': mine || takenByOther,
  'comparison': null,
  'decision': null,
  'certificate': null,
  'reservations': <Object>[],
  'photos': <Object>[],
  'signatures': null,
  'has_report': false,
  'created_at': '2026-10-20T08:00:00Z',
  'checklist': [
    {'key': 'building.capacity', 'section': 'building', 'declared': 120},
    {'key': 'equipment.extinguisher', 'section': 'equipment', 'declared': 8},
    {'key': 'evacuation.points', 'section': 'evacuation', 'declared': 1},
    {
      'key': 'safety_team.representative',
      'section': 'safety_team',
      'declared': 'Sami Trabelsi',
    },
    {'key': 'site.exits', 'section': 'site', 'declared': null},
    {'key': 'site.alarm', 'section': 'site', 'declared': null},
  ],
};

/// A signature pad that answers at once with a tiny PNG.
Future<String> fakeSignature(List<List<Offset>> strokes, Size size) async =>
    base64.encode([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0]);

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
  MemoryBlobStore? blobs,
  MemoryBlobStore? missionBlobs,
  SignatureEncoder? signature,
  StaffPush? push,
  String smsNumber = '',
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
        blobStoreProvider.overrideWithValue(blobs ?? MemoryBlobStore()),
        missionBlobStoreProvider.overrideWithValue(
          missionBlobs ?? MemoryBlobStore(),
        ),
        staffPushProvider.overrideWithValue(push ?? const NoStaffPush()),
        if (smsNumber.isNotEmpty)
          staffConfigProvider.overrideWithValue(
            StaffConfig(
              apiBaseUrl: StaffConfig.fromEnvironment().apiBaseUrl,
              issuer: StaffConfig.fromEnvironment().issuer,
              clientId: StaffConfig.fromEnvironment().clientId,
              smsNumber: smsNumber,
            ),
          ),
        connectivityProvider.overrideWithValue(FakeConnectivity()),
        signatureEncoderProvider.overrideWithValue(signature ?? fakeSignature),
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

/// Scrolls the mission screen until the widget of [key] is on screen (the round button pushed
/// the cards below the fold).
Future<void> reveal(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key), skipOffstage: false));
  await tester.pump();
}

/// Phase F: records a step by holding the round button past the room's hold time.
Future<void> holdStep(WidgetTester tester, String step) async {
  final button = find.byKey(Key('step-$step'));
  await reveal(tester, 'step-$step');
  final g = await tester.startGesture(tester.getCenter(button));
  // The first frame starts the ring; the next ones fill it.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 700));
  await tester.pump(const Duration(milliseconds: 100));
  await g.up();
  await tester.pumpAndSettle();
}

Future<void> enterPin(WidgetTester tester, String pin) async {
  await tester.enterText(find.byKey(const Key('staff-pin')), pin);
  await tester.pumpAndSettle();
}
