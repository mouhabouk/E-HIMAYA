/// Phase 4 §8 shapes used by the app.
const orgId = '7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60';

Map<String, Object?> summaryJson({String status = 'active'}) => {
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
};

Map<String, Object?> orgRow(String id, String name, String status) => {
  'id': id,
  'name': name,
  'kind': 'industrial',
  'status': status,
  'my_role': 'member',
  'alerts_count': 0,
};
