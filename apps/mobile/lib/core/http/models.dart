/// DTOs of the phase-2 and phase-4 contracts (snake_case JSON).
library;

/// Report status lifecycle (FR-A-032).
enum ReportStatus {
  received,
  inProgress('in_progress'),
  intervened,
  ongoing,
  closed,
  rejected;

  const ReportStatus([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static ReportStatus? fromWire(String? value) {
    for (final s in values) {
      if (s.wire == value) return s;
    }
    return null;
  }
}

/// Report categories (FR-A-040). `sos` is only sent by the SOS button.
enum ReportCategory {
  sos,
  fire,
  flood,
  trafficAccident('traffic_accident'),
  drowning,
  landslide,
  chemicalLeak('chemical_leak'),
  medical,
  other;

  const ReportCategory([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  /// Categories offered in the new-report grid (SOS has its own button).
  static const grid = [
    fire,
    flood,
    trafficAccident,
    drowning,
    landslide,
    chemicalLeak,
    medical,
    other,
  ];

  static ReportCategory? fromWire(String? value) {
    for (final c in values) {
      if (c.wire == value) return c;
    }
    return null;
  }
}

enum MediaKind { image, video, audio }

class GeoPoint {
  const GeoPoint({required this.lat, required this.lon, this.accuracyM});

  final double lat;
  final double lon;
  final double? accuracyM;

  /// Contract §3: lat 30.0–37.6, lon 7.4–11.7.
  bool get isInTunisiaBox =>
      lat >= 30.0 && lat <= 37.6 && lon >= 7.4 && lon <= 11.7;

  Map<String, Object?> toJson() => {
    'lat': lat,
    'lon': lon,
    if (accuracyM != null) 'accuracy_m': accuracyM,
  };

  static GeoPoint? fromJson(Object? json) {
    if (json is! Map) return null;
    final lat = json['lat'];
    final lon = json['lon'];
    if (lat is! num || lon is! num) return null;
    final acc = json['accuracy_m'];
    return GeoPoint(
      lat: lat.toDouble(),
      lon: lon.toDouble(),
      accuracyM: acc is num ? acc.toDouble() : null,
    );
  }
}

class ServerMedia {
  const ServerMedia({
    required this.id,
    required this.kind,
    required this.sha256,
    required this.status,
    this.bytes,
  });

  final String id;
  final String kind;
  final String sha256;

  /// `uploading` | `verifying` | `stored` | `rejected` (rejected media are hidden from lists).
  final String status;
  final int? bytes;

  factory ServerMedia.fromJson(Map<String, Object?> json) => ServerMedia(
    id: json['id']! as String,
    kind: json['kind'] as String? ?? '',
    sha256: (json['sha256'] as String? ?? '').toLowerCase(),
    status: json['status'] as String? ?? 'uploading',
    bytes: (json['bytes'] as num?)?.toInt(),
  );
}

class ServerReport {
  const ServerReport({
    required this.id,
    required this.trackingCode,
    required this.clientUuid,
    required this.category,
    required this.status,
    required this.media,
    this.text,
    this.lang,
    this.location,
    this.gouvernoratCode,
    this.createdAt,
    this.receivedAt,
    this.updatedAt,
    this.organization,
  });

  final String id;
  final String trackingCode;
  final String? clientUuid;
  final String category;
  final String status;
  final String? text;
  final String? lang;
  final GeoPoint? location;
  final int? gouvernoratCode;
  final DateTime? createdAt;
  final DateTime? receivedAt;
  final DateTime? updatedAt;
  final List<ServerMedia> media;

  /// Phase 4 §8: set when the report was sent on behalf of an institution.
  final OrgRef? organization;

  factory ServerReport.fromJson(Map<String, Object?> json) => ServerReport(
    id: json['id']! as String,
    trackingCode: json['tracking_code']! as String,
    clientUuid: json['client_uuid'] as String?,
    category: json['category'] as String? ?? 'other',
    status: json['status'] as String? ?? 'received',
    text: json['text'] as String?,
    lang: json['lang'] as String?,
    location: GeoPoint.fromJson(json['location']),
    gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
    createdAt: _date(json['created_at']),
    receivedAt: _date(json['received_at']),
    updatedAt: _date(json['updated_at']),
    media: [
      for (final m in (json['media'] as List? ?? const []))
        if (m is Map<String, Object?>) ServerMedia.fromJson(m),
    ],
    organization: OrgRef.fromJson(json['organization']),
  );
}

class ReportsPage {
  const ReportsPage(this.items, this.nextBefore);
  final List<ServerReport> items;
  final String? nextBefore;
}

class TrackingHistoryEntry {
  const TrackingHistoryEntry(this.status, this.at);
  final String status;
  final DateTime? at;
}

class TrackingResult {
  const TrackingResult({
    required this.trackingCode,
    required this.status,
    required this.history,
    this.receivedAt,
    this.updatedAt,
  });

  final String trackingCode;
  final String status;
  final DateTime? receivedAt;
  final DateTime? updatedAt;
  final List<TrackingHistoryEntry> history;

  factory TrackingResult.fromJson(Map<String, Object?> json) => TrackingResult(
    trackingCode: json['tracking_code']! as String,
    status: json['status']! as String,
    receivedAt: _date(json['received_at']),
    updatedAt: _date(json['updated_at']),
    history: [
      for (final h in (json['history'] as List? ?? const []))
        if (h is Map)
          TrackingHistoryEntry(h['status'] as String? ?? '', _date(h['at'])),
    ],
  );
}

class Gouvernorat {
  const Gouvernorat({
    required this.code,
    required this.name,
    required this.nameAr,
    required this.nameFr,
  });

  final int code;
  final String name;
  final String nameAr;
  final String nameFr;

  factory Gouvernorat.fromJson(Map<String, Object?> json) => Gouvernorat(
    code: (json['code']! as num).toInt(),
    name: json['name'] as String? ?? '',
    nameAr: json['name_ar'] as String? ?? '',
    nameFr: json['name_fr'] as String? ?? '',
  );
}

class Delegation {
  const Delegation({
    required this.id,
    required this.code,
    required this.gouvernoratCode,
    required this.name,
  });

  final int id;
  final String code;
  final int gouvernoratCode;
  final String name;

  factory Delegation.fromJson(Map<String, Object?> json) => Delegation(
    id: (json['id']! as num).toInt(),
    code: json['code'] as String? ?? '',
    gouvernoratCode: (json['gouvernorat_code']! as num).toInt(),
    name: json['name'] as String? ?? '',
  );
}

/// `PUT /api/v1/me/profile` body. The CIN is write-only: `GET` returns `cin_last4` instead.
class ProfileInput {
  const ProfileInput({
    required this.firstName,
    required this.lastName,
    required this.cin,
    required this.phone,
    required this.gouvernoratCode,
    required this.delegationId,
    required this.locale,
    this.address,
  });

  final String firstName;
  final String lastName;

  /// Exactly 8 digits.
  final String cin;

  /// `+216` followed by 8 digits.
  final String phone;
  final int gouvernoratCode;
  final int delegationId;
  final String? address;
  final String locale;

  Map<String, Object?> toJson() => {
    'first_name': firstName,
    'last_name': lastName,
    'cin': cin,
    'phone': phone,
    'gouvernorat_code': gouvernoratCode,
    'delegation_id': delegationId,
    'address': address,
    'locale': locale,
  };
}

/// `GET /api/v1/me/profile`: every field is null until the profile was filled.
class Profile {
  const Profile({
    this.firstName,
    this.lastName,
    this.cinLast4,
    this.phone,
    this.email,
    this.gouvernoratCode,
    this.delegationId,
    this.address,
    this.locale,
  });

  final String? firstName;
  final String? lastName;
  final String? cinLast4;
  final String? phone;
  final String? email;
  final int? gouvernoratCode;
  final int? delegationId;
  final String? address;
  final String? locale;

  bool get isComplete =>
      (firstName?.isNotEmpty ?? false) &&
      (lastName?.isNotEmpty ?? false) &&
      cinLast4 != null &&
      phone != null &&
      delegationId != null;

  factory Profile.fromJson(Map<String, Object?> json) => Profile(
    firstName: json['first_name'] as String?,
    lastName: json['last_name'] as String?,
    cinLast4: json['cin_last4'] as String?,
    phone: json['phone'] as String?,
    email: json['email'] as String?,
    gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
    delegationId: (json['delegation_id'] as num?)?.toInt(),
    address: json['address'] as String?,
    locale: json['locale'] as String?,
  );
}

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

// ---- Phase 4: institutions (FR-A-080, FR-A-081, FR-B-011) ------------------------------------

/// Institution status (phase 4 §1). Only `active` institutions can report.
enum OrgStatus {
  pendingReview('pending_review'),
  active,
  rejected,
  suspended;

  const OrgStatus([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static OrgStatus? fromWire(String? value) {
    for (final s in values) {
      if (s.wire == value) return s;
    }
    return null;
  }
}

/// Institution kind (الصبغة, phase 4 §1).
enum OrgKind {
  industrial,
  educational,
  hotel,
  government,
  private,
  other;

  String get wire => name;

  static OrgKind? fromWire(String? value) {
    for (final k in values) {
      if (k.wire == value) return k;
    }
    return null;
  }
}

/// `{"id", "name"}` attached to a report sent on behalf of an institution.
class OrgRef {
  const OrgRef({required this.id, required this.name});

  final String id;
  final String name;

  static OrgRef? fromJson(Object? json) {
    if (json is! Map) return null;
    final id = json['id'];
    if (id is! String) return null;
    final name = json['name'];
    return OrgRef(id: id, name: name is String ? name : '');
  }
}

/// One row of `GET /api/v1/orgs/mine`.
class MyOrg {
  const MyOrg({
    required this.id,
    required this.name,
    required this.kind,
    required this.status,
    this.myRole,
    this.alertsCount = 0,
  });

  final String id;
  final String name;

  /// Wire value; see [OrgKind].
  final String kind;

  /// Wire value; see [OrgStatus].
  final String status;

  /// `admin` | `editor` | `member`.
  final String? myRole;
  final int alertsCount;

  bool get isActive => status == OrgStatus.active.wire;

  factory MyOrg.fromJson(Map<String, Object?> json) => MyOrg(
    id: json['id']! as String,
    name: json['name'] as String? ?? '',
    kind: json['kind'] as String? ?? OrgKind.other.wire,
    status: json['status'] as String? ?? OrgStatus.pendingReview.wire,
    myRole: json['my_role'] as String?,
    alertsCount: (json['alerts_count'] as num?)?.toInt() ?? 0,
  );

  Map<String, Object?> toJson() => {
    'id': id,
    'name': name,
    'kind': kind,
    'status': status,
    'my_role': myRole,
    'alerts_count': alertsCount,
  };
}

/// Computed classification (phase 4 §1, FR-B-003).
class OrgClassification {
  const OrgClassification({
    required this.family,
    this.category,
    this.highRise = false,
    this.provisional = false,
  });

  /// `high_rise` | `industrial` | `erp` | `workplace`.
  final String family;

  /// 1–5 for `erp`, null otherwise.
  final int? category;
  final bool highRise;

  /// The thresholds still have to be validated against the official text.
  final bool provisional;

  static OrgClassification? fromJson(Object? json) {
    if (json is! Map) return null;
    final family = json['family'];
    if (family is! String) return null;
    final category = json['category'];
    return OrgClassification(
      family: family,
      category: category is num ? category.toInt() : null,
      highRise: json['high_rise'] == true,
      provisional: json['provisional'] == true,
    );
  }
}

/// Safety team member as shown by the app summary (phase 4 §8).
class OrgTeamMember {
  const OrgTeamMember({
    required this.fullName,
    required this.teamRole,
    required this.trainingStatus,
    this.phone,
  });

  final String fullName;

  /// `representative` | `member`.
  final String teamRole;
  final String? phone;

  /// `valid` | `expiring` | `expired` | `unknown`.
  final String trainingStatus;

  factory OrgTeamMember.fromJson(Map<String, Object?> json) => OrgTeamMember(
    fullName: json['full_name'] as String? ?? '',
    teamRole: json['team_role'] as String? ?? 'member',
    phone: json['phone'] as String?,
    trainingStatus: json['training_status'] as String? ?? 'unknown',
  );
}

/// Hazardous material as shown by the app summary (phase 4 §8).
class OrgHazmat {
  const OrgHazmat({
    required this.name,
    this.unNumber,
    this.quantity,
    this.unit,
  });

  final String name;
  final String? unNumber;
  final double? quantity;

  /// `kg` | `t` | `l` | `m3`.
  final String? unit;

  factory OrgHazmat.fromJson(Map<String, Object?> json) => OrgHazmat(
    name: json['name'] as String? ?? '',
    unNumber: json['un_number'] as String?,
    quantity: (json['quantity'] as num?)?.toDouble(),
    unit: json['unit'] as String?,
  );
}

/// `GET /api/v1/orgs/{id}/summary` (FR-A-081). [source] keeps the server JSON so the last
/// summary can be cached and shown offline.
class OrgSummary {
  const OrgSummary({
    required this.id,
    required this.name,
    required this.kind,
    required this.status,
    required this.team,
    required this.hazmat,
    required this.source,
    this.capacity,
    this.address,
    this.location,
    this.classification,
    this.hazmatCount = 0,
    this.alertsCount = 0,
  });

  final String id;
  final String name;
  final String kind;
  final String status;
  final int? capacity;
  final String? address;
  final GeoPoint? location;
  final OrgClassification? classification;
  final List<OrgTeamMember> team;
  final int hazmatCount;
  final List<OrgHazmat> hazmat;
  final int alertsCount;
  final Map<String, Object?> source;

  factory OrgSummary.fromJson(Map<String, Object?> json) {
    final hazmat = [
      for (final h in (json['hazmat'] as List? ?? const []))
        if (h is Map<String, Object?>) OrgHazmat.fromJson(h),
    ];
    return OrgSummary(
      id: json['id']! as String,
      name: json['name'] as String? ?? '',
      kind: json['kind'] as String? ?? OrgKind.other.wire,
      status: json['status'] as String? ?? OrgStatus.pendingReview.wire,
      capacity: (json['capacity'] as num?)?.toInt(),
      address: json['address'] as String?,
      location: GeoPoint.fromJson(json['location']),
      classification: OrgClassification.fromJson(json['classification']),
      team: [
        for (final t in (json['team'] as List? ?? const []))
          if (t is Map<String, Object?>) OrgTeamMember.fromJson(t),
      ],
      hazmatCount: (json['hazmat_count'] as num?)?.toInt() ?? hazmat.length,
      hazmat: hazmat,
      alertsCount: (json['alerts_count'] as num?)?.toInt() ?? 0,
      source: json,
    );
  }
}

/// One row of `GET /api/v1/orgs/{id}/reports`.
class OrgReport {
  const OrgReport({
    required this.id,
    required this.trackingCode,
    required this.category,
    required this.status,
    this.text,
    this.receivedAt,
    this.updatedAt,
    this.reporterDisplayName,
  });

  final String id;
  final String trackingCode;
  final String category;
  final String status;
  final String? text;
  final DateTime? receivedAt;
  final DateTime? updatedAt;
  final String? reporterDisplayName;

  factory OrgReport.fromJson(Map<String, Object?> json) => OrgReport(
    id: json['id']! as String,
    trackingCode: json['tracking_code']! as String,
    category: json['category'] as String? ?? 'other',
    status: json['status'] as String? ?? 'received',
    text: json['text'] as String?,
    receivedAt: _date(json['received_at']),
    updatedAt: _date(json['updated_at']),
    reporterDisplayName: json['reporter_display_name'] as String?,
  );
}

class OrgReportsPage {
  const OrgReportsPage(this.items, this.nextCursor);
  final List<OrgReport> items;
  final String? nextCursor;
}
