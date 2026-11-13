// The API of the atlas screenshots [SIM]: one answer per route the citizen app reads, in the shapes of the widget
// tests' fixtures, so every screen opens on data rather than on an empty state (Yamen, 2026-11-13).
import 'dart:convert';
import 'dart:io';

import '../helpers/fake_http.dart';
import '../helpers/org_fixtures.dart';
import '../helpers/phase5_fixtures.dart';
import '../helpers/rewards_fixtures.dart';
import '../helpers/weather_fixtures.dart';
import '../widgets/institution_flow_test.dart' as institution show api;

const atlasGouvernorats = [
  {'code': 61, 'name': 'Sfax', 'name_ar': 'صفاقس', 'name_fr': 'Sfax'},
  {'code': 11, 'name': 'Tunis', 'name_ar': 'تونس', 'name_fr': 'Tunis'},
];

Map<String, Object?> atlasReport(
  String id,
  String code,
  String category,
  String status, {
  String created = '2026-11-12T10:15:00Z',
}) => {
  'id': id,
  'tracking_code': code,
  'client_uuid': 'c-$id',
  'category': category,
  'status': status,
  'text': null,
  'lang': 'ar',
  'location': {'lat': 34.74, 'lon': 10.76, 'accuracy_m': 12.5},
  'gouvernorat_code': 61,
  'created_at': created,
  'received_at': created,
  'updated_at': created,
  'media': <Object>[],
};

Map<String, Object?> atlasDoctor() => {
  'kind': 'civil_protection',
  'status': 'approved',
  'specialties': ['emergency_medicine'],
  'licence_no': 'TN-12345',
  'workplace': 'المستشفى الجامعي الحبيب بورقيبة',
  'gouvernorat_code': 61,
  'cp_unit': 'الإدارة الجهوية',
  'cp_staff_no': 'PC/4521',
  'review_reason': null,
  'submitted_at': '2026-10-24T08:00:00Z',
  'reviewed_at': '2026-10-25T08:00:00Z',
  'available': true,
  'available_until': '2100-01-01T00:00:00Z',
  'committee_until': null,
  'has_key': false,
  'version': 1,
};

Map<String, Object?> _beach(
  String id,
  String name,
  double lat,
  double lon,
  String level,
) => {
  'id': id,
  'name': name,
  'lat': lat,
  'lon': lon,
  'gouvernorat_code': 61,
  'level': level,
  'score': level == 'red' ? 75 : (level == 'yellow' ? 40 : 10),
  'factors': level == 'green'
      ? <Object>[]
      : [
          {'code': 'waves', 'points': 55, 'value': 2.8},
        ],
  'wave_height_m': level == 'green' ? 0.6 : 2.8,
  'sea_temp_c': 24.1,
  'current_kmh': 2.4,
  'classification': 'local',
  'guarded': level != 'red',
  'crowd': null,
  'present': null,
};

final atlasBeaches = {
  'day': '2026-07-04',
  'computed_at': '2026-07-04T07:00:00Z',
  'simulated': true,
  'attribution': [
    '[SIM] Simulated marine weather (e-Himaya simulator), not real data',
  ],
  'warn_radius_m': 1000,
  'items': [
    _beach('b-chaffar', 'شاطئ الشفار', 34.55, 10.55, 'green'),
    _beach('b-sidimansour', 'شاطئ سيدي منصور', 34.80, 10.86, 'yellow'),
    _beach('b-kerkennah', 'شاطئ قرقنة', 34.70, 11.20, 'red'),
  ],
};

/// Requests the atlas API had no answer for (written next to the screenshots as missed.txt).
final atlasMissed = <String>{};

/// The answer of the atlas API to [r]; writes are accepted as the server would.
FakeResponse atlasApi(SeenRequest r) {
  final a = _answer(r);
  if (a.status == 404) atlasMissed.add('${r.method} ${r.uri}');
  return a;
}

FakeResponse _answer(SeenRequest r) {
  final p = r.path;
  final get = r.method == 'GET';
  // The institution's sections: the answers of the institution widget test (an administrator).
  if (get &&
      p.startsWith('/api/v1/orgs/$orgId/') &&
      !p.endsWith('/summary') &&
      !p.endsWith('/prealerts')) {
    final a = institution.api(r, role: 'admin', pending: 1);
    if (a.status != 404) return a;
  }
  if (!get) {
    if (p == '/api/v1/consents') return const FakeResponse(201);
    return const FakeResponse(200, json: {});
  }
  if (p.startsWith('/api/v1/orgs/') && p.endsWith('/summary')) {
    return FakeResponse(200, json: summaryJson());
  }
  if (p.startsWith('/api/v1/orgs/') && p.endsWith('/equipment')) {
    return FakeResponse(200, json: [equipmentJson()]);
  }
  if (p.startsWith('/api/v1/orgs/') && p.endsWith('/reports')) {
    return FakeResponse(
      200,
      json: {
        'items': [
          atlasReport('r-o1', 'EH-26-61-0004790', 'fire', 'in_progress'),
        ],
        'next_before': null,
      },
    );
  }
  if (RegExp(r'^/api/v1/orgs/[^/]+$').hasMatch(p) && p != '/api/v1/orgs/mine') {
    return FakeResponse(200, json: cardJson());
  }
  if (p.startsWith('/api/v1/layers/') && p.endsWith('/package')) {
    return const FakeResponse(
      200,
      json: {
        'layer': 'hospitals',
        'etag': 'v1',
        'lang': 'ar',
        'items': [
          {
            'id': 'h-1',
            'name': 'مستشفى الهادي شاكر [SIM]',
            'lat': 34.742,
            'lon': 10.758,
            'kind': 'hospital',
            'phone': '74240000',
            'props': {},
          },
          {
            'id': 'h-2',
            'name': 'مستشفى الحبيب بورقيبة [SIM]',
            'lat': 34.735,
            'lon': 10.765,
            'kind': 'hospital',
            'phone': '74241511',
            'props': {},
          },
          {
            'id': 'h-3',
            'name': 'مركز الحماية المدنية صفاقس [SIM]',
            'lat': 34.748,
            'lon': 10.771,
            'kind': 'station',
            'phone': '198',
            'props': {},
          },
        ],
      },
    );
  }
  if (p.startsWith('/api/v1/coastal/beaches/')) {
    final b = (atlasBeaches['items']! as List)[1] as Map<String, Object?>;
    return FakeResponse(
      200,
      json: {
        'beach': b,
        'days': [
          for (final (d, l, sc) in [
            ('2026-07-04', 'yellow', 40),
            ('2026-07-05', 'green', 15),
            ('2026-07-06', 'red', 70),
            ('2026-07-07', 'yellow', 45),
          ])
            {
              'day': d,
              'level': l,
              'score': sc,
              'factors': b['factors'],
              'wave_height_m': 1.8,
              'sea_temp_c': 24.0,
            },
        ],
        'card': {
          'classification': 'شاطئ عمومي',
          'lifeguards': 'من 9:00 إلى 19:00',
          'blue_flag': true,
        },
        'sources': <String, Object?>{},
        'simulated': true,
        'attribution': '[SIM] Simulated marine weather (e-Himaya simulator), not real data',
      },
    );
  }
  return switch (p) {
    '/api/v1/reports/mine' => FakeResponse(
      200,
      json: {
        'items': [
          atlasReport('r-1', 'EH-26-61-0004821', 'fire', 'in_progress'),
          atlasReport(
            'r-2',
            'EH-26-61-0004650',
            'traffic',
            'closed',
            created: '2026-11-02T08:40:00Z',
          ),
        ],
        'next_before': null,
      },
    ),
    '/api/v1/reports/quota' => const FakeResponse(
      200,
      json: {'limit': 3, 'used': 1, 'remaining': 2, 'window_hours': 24},
    ),
    '/api/v1/alerts/active' => FakeResponse(200, json: [alertJson()]),
    '/api/v1/notifications' => FakeResponse(
      200,
      json: {
        'items': [inboxItemJson('n-1', kind: 'alert'), inboxItemJson('n-2')],
        'next_cursor': null,
      },
    ),
    '/api/v1/safety-tips' => FakeResponse(200, json: tipsJson()),
    '/api/v1/orgs/mine' => FakeResponse(
      200,
      json: [orgRow(orgId, 'Société X', 'active', role: 'admin')],
    ),
    '/api/v1/me/volunteer' => FakeResponse(
      200,
      json: volunteerJson(ready: true, readyUntil: '2100-01-01T00:00:00Z'),
    ),
    '/api/v1/me/callouts' => FakeResponse(200, json: [calloutJson()]),
    '/api/v1/me/rewards' => FakeResponse(200, json: rewardsJson()),
    '/api/v1/me/doctor' => FakeResponse(200, json: atlasDoctor()),
    '/api/v1/me/profile' => const FakeResponse(
      200,
      json: {
        'full_name': 'سامي بن علي',
        'phone': '+21698123456',
        'gouvernorat_code': 61,
        'delegation_id': null,
        'email': 'sami@example.tn',
        'email_verified': true,
      },
    ),
    '/api/v1/weather' => FakeResponse(200, json: weatherJson(simulated: true)),
    '/api/v1/geo/gouvernorats' => const FakeResponse(
      200,
      json: atlasGouvernorats,
    ),
    '/api/v1/coastal/beaches' => FakeResponse(200, json: atlasBeaches),
    '/api/v1/layers' => const FakeResponse(
      200,
      json: {
        'items': [
          {
            'key': 'hospitals',
            'names': {'ar': 'المستشفيات ومراكز الحماية', 'fr': 'Hôpitaux'},
            'icon': 'hospital',
            'colour': '#C62828',
            'source': 'OSM',
            'licence': 'ODbL',
            'simulated': true,
            'count': 3,
            'data_version': 1,
          },
        ],
      },
    ),
    '/api/v1/orgs/$orgId/prealerts' => FakeResponse(
      200,
      json: [
        {
          'id': 'p-1',
          'org_id': orgId,
          'org_name': 'Société X',
          'stream_id': 's-1',
          'source': 'camera',
          'label': 'smoke',
          'confidence': 0.82,
          'simulated': true,
          'state': 'pending',
          'stage': 'officer',
          'raised_at': DateTime.now().toUtc().toIso8601String(),
          'deadline_at': DateTime.now()
              .toUtc()
              .add(const Duration(seconds: 60))
              .toIso8601String(),
          'seconds_left': 60,
          'reason': null,
          'report_id': null,
          'has_frame': false,
        },
      ],
    ),
    '/api/v1/geo/gouvernorats/61/delegations' => const FakeResponse(
      200,
      json: [
        {'id': 6101, 'name_ar': 'صفاقس المدينة', 'name_fr': 'Sfax Ville'},
        {'id': 6102, 'name_ar': 'صفاقس الغربية', 'name_fr': 'Sfax Ouest'},
      ],
    ),
    '/api/v1/me/medical/openings' => const FakeResponse(
      200,
      json: [
        {
          'report_id': 'r-1',
          'tracking_code': 'EH-26-61-0004821',
          'kind': 'open',
          'role': 'committee',
          'gouvernorat_code': null,
          'specialties': <Object?>[],
          'workplace': null,
          'at': '2026-10-24T11:00:00Z',
        },
      ],
    ),
    '/api/v1/emergency-guide' => FakeResponse(
      200,
      json: jsonDecode(File('assets/emergency_guide.json').readAsStringSync()),
    ),
    '/api/v1/me/contact' => const FakeResponse(
      200,
      json: {
        'items': [
          {
            'id': 'c1',
            'number': 'CT-2026-000042',
            'kind': 'access_info',
            'status': 'answered',
            'subject': 'ميزانية المراكز',
            'message': 'أرغب في الاطلاع على ميزانية مراكز صفاقس.',
            'gouvernorat_code': 61,
            'created_at': '2026-10-23T09:00:00Z',
            'due_at': '2026-11-12T09:00:00Z',
            'answer': 'الميزانية منشورة على موقعنا.',
            'answered_at': '2026-10-24T09:00:00Z',
            'history': [
              {
                'action': 'created',
                'status': 'received',
                'gouvernorat_code': 61,
                'at': '2026-10-23T09:00:00Z',
              },
            ],
          },
        ],
      },
    ),
    '/api/v1/safety/links' => const FakeResponse(
      200,
      json: {
        'items': [
          {
            'id': 'link-1',
            'first_name': 'هالة',
            'phone': '+21620123456',
            'created_at': '2026-10-23T08:00:00Z',
          },
        ],
      },
    ),
    '/api/v1/safety/checks/current' => const FakeResponse(200, json: null),
    '/api/v1/safety/history' => const FakeResponse(
      200,
      json: {
        'available': true,
        'enabled': false,
        'until': null,
        'notice_version': '7b-2026-10',
      },
    ),
    '/api/v1/safety/alerts' => const FakeResponse(
      200,
      json: {'items': <Object>[]},
    ),
    '/api/v1/me/address-warnings' => const FakeResponse(
      200,
      json: {'consent': false, 'items': <Object>[]},
    ),
    '/api/v1/me/email' => const FakeResponse(
      200,
      json: {'email': 'sami@example.tn', 'verified': true, 'source': 'account'},
    ),
    '/api/v1/me/availability' => const FakeResponse(
      200,
      json: {
        'role': 'volunteer',
        'slots': [
          {
            'id': 'a1',
            'kind': 'available',
            'weekdays': [5, 6],
            'starts_on': '2026-11-01',
            'ends_on': null,
            'from_time': '08:00',
            'to_time': '14:00',
          },
          {
            'id': 'a2',
            'kind': 'unavailable',
            'weekdays': [1],
            'starts_on': '2026-11-01',
            'ends_on': '2026-12-31',
            'from_time': '18:00',
            'to_time': '22:00',
          },
        ],
        'planned_now': 'available',
      },
    ),
    '/api/v1/doctors/directory' => const FakeResponse(
      200,
      json: [
        {
          'id': 's-1',
          'full_name': 'د. سلمى',
          'kind': 'volunteer',
          'specialties': ['cardiology'],
          'workplace': 'المستشفى الجامعي الهادي شاكر',
          'gouvernorat_code': 61,
          'available': true,
          'public_key': null,
        },
      ],
    ),
    '/api/v1/medical/files' => const FakeResponse(
      200,
      json: [
        {
          'report_id': 'r-1',
          'tracking_code': 'EH-26-61-0004821',
          'category': 'medical',
          'gouvernorat_code': 61,
          'received_at': '2026-10-24T08:00:00Z',
          'report_status': 'received',
          'via': 'gouvernorat',
          'opened_at': null,
        },
      ],
    ),
    '/api/v1/app/version' => const FakeResponse(
      200,
      json: {'latest': '1.0.0', 'minimum': '1.0.0'},
    ),
    '/api/v1/app/features' => const FakeResponse(200, json: {'hidden': []}),
    _ => const FakeResponse(404, json: {'detail': 'not_found'}),
  };
}
