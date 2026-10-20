/// `GET /api/v1/me/rewards` answers as documented by the rewards module (phase 8 §3).
Map<String, Object?> rewardsJson({
  int balance = 320,
  bool paused = false,
  int pendingPoints = 0,
  bool anonymous = false,
  String? historyNextCursor,
}) => {
  'anonymous': anonymous,
  'balance': balance,
  'pending_points': pendingPoints,
  'paused': paused,
  'daily_cap': 200,
  'badges': [
    {'id': 'b1', 'level': 'bronze', 'confirmed_at': '2026-09-01T09:00:00Z'},
  ],
  'current_badge': 'bronze',
  'next_badge': {'level': 'silver', 'threshold': 500, 'missing_points': 180},
  'history': [
    {
      'id': 12,
      'delta': 25,
      'reason': 'accurate_category',
      'report_id': 'r1',
      'tracking_code': 'EH-26-11-0000042',
      'intervention_id': null,
      'multiplier': 1.5,
      'capped': false,
      'created_at': '2026-10-18T10:00:00Z',
    },
    {
      'id': 11,
      'delta': 50,
      'reason': 'report_verified',
      'report_id': 'r1',
      'tracking_code': 'EH-26-11-0000042',
      'intervention_id': null,
      'multiplier': null,
      'capped': false,
      'created_at': '2026-10-18T10:00:00Z',
    },
    {
      'id': 10,
      'delta': 0,
      'reason': 'volunteer_mission',
      'report_id': null,
      'tracking_code': null,
      'intervention_id': 'i7',
      'multiplier': null,
      'capped': true,
      'created_at': '2026-10-10T18:00:00Z',
    },
  ],
  'history_next_cursor': historyNextCursor,
  'certificates': [
    {
      'id': 'c-1',
      'code': 'CERT-7K2P',
      'distinction': 'vigilant_citizen',
      'year': 2026,
      'issued_at': '2026-10-01T09:00:00Z',
      'verify_url': 'https://ehimaya.tn/api/v1/rewards/certificates/CERT-7K2P',
    },
  ],
  'prizes_notice': {'ar': '…', 'fr': '…', 'en': '…'},
  'safety_notice': {'ar': '…', 'fr': '…', 'en': '…'},
};

/// Start of a PDF file (enough for the viewer stub).
const fakePdf = [0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x37, 0x0A];
