/// Phase 4 §8 shapes used by the app.
const orgId = '7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60';

Map<String, Object?> summaryJson({
  String status = 'active',
  int messagesPending = 0,
}) => {
  'id': orgId,
  'name': 'Société X',
  'kind': 'industrial',
  'status': status,
  'capacity': 420,
  'address': 'Route de Gabès km 4',
  'location': {'lat': 34.70, 'lon': 10.72},
  'classification': {
    'family': 'industrial',
    'category': null,
    'high_rise': false,
    'required': ['safety_file', 'safety_team'],
    'provisional': true,
  },
  'team': [
    {
      'full_name': 'Amel Ben Salah',
      'team_role': 'representative',
      'phone': '+21698123456',
      'training_status': 'valid',
    },
    {
      'full_name': 'Karim Trabelsi',
      'team_role': 'member',
      'phone': null,
      'training_status': 'expired',
    },
  ],
  'hazmat_count': 1,
  'hazmat': [
    {'name': 'Acétone', 'un_number': '1090', 'quantity': 2.5, 'unit': 't'},
  ],
  'alerts_count': 2,
  // Phase P2a.
  'readiness': 50,
  'missing': ['safety_file'],
  'kind_fields': {'workers_per_shift': 35, 'tanks': 2},
  'alerts': [
    {'kind': 'training_expired', 'ref': 't2', 'since': '2026-09-01'},
    {'kind': 'maintenance_overdue', 'ref': 'e1', 'since': '2026-08-15'},
  ],
  // Phase P2b.
  'messages_pending': messagesPending,
};

/// `GET /api/v1/orgs/{id}` (phase 4 §1, P2a fields included).
Map<String, Object?> cardJson({String role = 'admin', int version = 3}) => {
  'id': orgId,
  'name': 'Société X',
  'kind': 'industrial',
  'status': 'active',
  'version': version,
  'my_role': role,
  'identifier_type': 'mf',
  'identifier': '1234567A',
  'activity_sector': 'Peintures',
  'activity_type': null,
  'capacity': 420,
  'floors': 2,
  'height_m': 9.5,
  'receives_public': false,
  'address': 'Route de Gabès km 4',
  'location': {'lat': 34.70, 'lon': 10.72},
  'manager': {
    'full_name': 'Karim Trabelsi',
    'phone': '+21620123456',
    'email': null,
  },
  'contact_email': 'contact@societe-x.tn',
  'contact_phone': null,
  'kind_fields': {'workers_per_shift': 35, 'tanks': 2},
  'kind_review': false,
  'readiness': 50,
};

Map<String, Object?> equipmentJson() => {
  'id': 'e1',
  'kind': 'extinguisher',
  'count': 12,
  'location': 'Atelier',
  'last_maintenance_on': '2025-06-01',
  'maintenance_interval_months': 12,
  'maintenance_status': 'overdue',
  'next_maintenance_on': '2026-06-01',
};

Map<String, Object?> orgRow(
  String id,
  String name,
  String status, {
  String role = 'member',
}) => {
  'id': id,
  'name': name,
  'kind': 'industrial',
  'status': status,
  'my_role': role,
  'alerts_count': 0,
};
