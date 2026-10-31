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
    this.teamEnRouteAt,
    this.teamOnSceneAt,
  });

  final String trackingCode;
  final String status;
  final DateTime? receivedAt;
  final DateTime? updatedAt;
  final List<TrackingHistoryEntry> history;

  /// Phase P4d (F-APP-38): when the team set off, then reached the place.
  final DateTime? teamEnRouteAt;
  final DateTime? teamOnSceneAt;

  factory TrackingResult.fromJson(Map<String, Object?> json) => TrackingResult(
    trackingCode: json['tracking_code']! as String,
    status: json['status']! as String,
    receivedAt: _date(json['received_at']),
    updatedAt: _date(json['updated_at']),
    teamEnRouteAt: _date(json['team_en_route_at']),
    teamOnSceneAt: _date(json['team_on_scene_at']),
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

/// Institution kind (الصبغة): twelve since phase P2a (addition 12), a working list [SIM] until the
/// Office approves it.
enum OrgKind {
  health('health'),
  industrial('industrial'),
  energy('energy'),
  tourism('tourism'),
  education('education'),
  socialCare('social_care'),
  publicAdmin('public_admin'),
  cultureSport('culture_sport'),
  commercial('commercial'),
  transport('transport'),
  religious('religious'),
  other('other');

  const OrgKind(this.wire);

  final String wire;

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
    this.readiness,
    this.missing = const [],
    this.kindFields = const {},
    this.alerts = const [],
    this.messagesPending = 0,
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

  /// P2a: share of the safety requirements met, in percent (null from an older server).
  final int? readiness;

  /// Requirement codes still missing (`safety_file`, `safety_team`, ...).
  final List<String> missing;

  /// Answers to the kind's fields; members see them all.
  final Map<String, Object> kindFields;
  final List<OrgAlert> alerts;

  /// P2b: Office messages waiting for the institution's read acknowledgement.
  final int messagesPending;
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
      readiness: (json['readiness'] as num?)?.toInt(),
      missing: [
        for (final m in (json['missing'] as List? ?? const []))
          if (m is String) m,
      ],
      kindFields: kindFieldsFromJson(json['kind_fields']),
      alerts: [
        for (final a in (json['alerts'] as List? ?? const []))
          if (a is Map<String, Object?>) OrgAlert.fromJson(a),
      ],
      messagesPending: (json['messages_pending'] as num?)?.toInt() ?? 0,
      source: json,
    );
  }
}

/// `kind_fields` of an institution: numbers, yes/no and text only.
Map<String, Object> kindFieldsFromJson(Object? json) => {
  if (json is Map)
    for (final e in json.entries)
      if (e.key is String &&
          (e.value is num || e.value is bool || e.value is String))
        e.key as String: e.value is num && e.value is! int
            ? (e.value as num).toInt()
            : e.value as Object,
};

/// Alert of an institution (phase 4 §3–4): kind code, the register row it is about, since when.
class OrgAlert {
  const OrgAlert({required this.kind, this.ref, this.since});

  final String kind;
  final String? ref;
  final DateTime? since;

  factory OrgAlert.fromJson(Map<String, Object?> json) => OrgAlert(
    kind: json['kind'] as String? ?? '',
    ref: json['ref'] as String?,
    since: _date(json['since']),
  );
}

/// The full card of `GET /api/v1/orgs/{id}` (phase 4 §1), kept as JSON so an edit sends back
/// every field the app does not change.
class OrgCardData {
  const OrgCardData(this.json);

  final Map<String, Object?> json;

  String get id => json['id']! as String;
  String get name => json['name'] as String? ?? '';
  String get kind => json['kind'] as String? ?? OrgKind.other.wire;
  String get status =>
      json['status'] as String? ?? OrgStatus.pendingReview.wire;
  int get version => (json['version'] as num?)?.toInt() ?? 1;
  String? get myRole => json['my_role'] as String?;
  bool get canEdit => myRole == 'admin' || myRole == 'editor';
  String get identifierType => json['identifier_type'] as String? ?? 'mf';
  String get identifier => json['identifier'] as String? ?? '';
  String? get activitySector => json['activity_sector'] as String?;
  int? get capacity => (json['capacity'] as num?)?.toInt();
  int? get floors => (json['floors'] as num?)?.toInt();
  double? get heightM => (json['height_m'] as num?)?.toDouble();
  bool get receivesPublic => json['receives_public'] == true;
  String? get address => json['address'] as String?;
  GeoPoint? get location => GeoPoint.fromJson(json['location']);
  Map<String, Object?> get manager =>
      (json['manager'] as Map?)?.cast<String, Object?>() ?? const {};
  String? get contactEmail => json['contact_email'] as String?;
  String? get contactPhone => json['contact_phone'] as String?;
  Map<String, Object> get kindFields => kindFieldsFromJson(json['kind_fields']);
  int? get readiness => (json['readiness'] as num?)?.toInt();

  /// Body of `PUT /api/v1/orgs/{id}`: the card's editable fields, with [changes] applied.
  Map<String, Object?> toUpdate(Map<String, Object?> changes) => {
    for (final k in const [
      'name',
      'kind',
      'identifier_type',
      'identifier',
      'activity_sector',
      'activity_type',
      'capacity',
      'floors',
      'height_m',
      'receives_public',
      'address',
      'location',
      'manager',
      'contact_email',
      'contact_phone',
      'kind_fields',
    ])
      k: json[k],
    ...changes,
    'version': version,
  };
}

/// Safety equipment row (phase 4 §4).
class OrgEquipment {
  const OrgEquipment(this.json);

  final Map<String, Object?> json;

  String get id => json['id']! as String;
  String get kind => json['kind'] as String? ?? 'other';
  int get count => (json['count'] as num?)?.toInt() ?? 0;
  String? get location => json['location'] as String?;

  /// `ok` | `due_soon` | `overdue` | `unknown`.
  String get maintenanceStatus =>
      json['maintenance_status'] as String? ?? 'unknown';
  DateTime? get nextMaintenanceOn => _date(json['next_maintenance_on']);

  /// Body of `PUT .../equipment/{id}` recording a maintenance done on [day].
  Map<String, Object?> maintainedOn(DateTime day) => {
    'kind': kind,
    'count': count,
    'location': location,
    'last_maintenance_on': isoDay(day),
    'maintenance_interval_months':
        (json['maintenance_interval_months'] as num?)?.toInt() ?? 12,
  };
}

/// `YYYY-MM-DD` of a local day, as the API dates are written.
String isoDay(DateTime day) =>
    '${day.year.toString().padLeft(4, '0')}-'
    '${day.month.toString().padLeft(2, '0')}-'
    '${day.day.toString().padLeft(2, '0')}';

/// One maintenance of an equipment (phase P2b), with its photo once the server checked it.
class OrgMaintenance {
  const OrgMaintenance({
    required this.id,
    required this.doneOn,
    this.note,
    this.documentId,
    this.photoVersion,
    this.recordedBy,
  });

  final String id;
  final DateTime doneOn;
  final String? note;
  final String? documentId;

  /// Stored version of the photo; null while it is checked or when there is none.
  final int? photoVersion;
  final String? recordedBy;

  factory OrgMaintenance.fromJson(Map<String, Object?> json) => OrgMaintenance(
    id: json['id']! as String,
    doneOn: _date(json['done_on']) ?? DateTime(1970),
    note: json['note'] as String?,
    documentId: json['document_id'] as String?,
    photoVersion: (json['photo_version'] as num?)?.toInt(),
    recordedBy: json['recorded_by'] as String?,
  );
}

/// An Office message addressed to the institution (phase P2b), with its read acknowledgement.
class OrgMessage {
  const OrgMessage({
    required this.id,
    required this.title,
    required this.body,
    required this.publishedAt,
    this.topic,
    this.ackRequired = false,
    this.ackedAt,
    this.ackedBy,
  });

  final String id;
  final String? topic;
  final Map<String, String> title;
  final Map<String, String> body;
  final DateTime publishedAt;
  final bool ackRequired;
  final DateTime? ackedAt;
  final String? ackedBy;

  bool get waiting => ackRequired && ackedAt == null;

  /// The text in [lang], or Arabic when that language is empty.
  static String pick(Map<String, String> texts, String lang) {
    final t = texts[lang];
    return t == null || t.trim().isEmpty ? texts['ar'] ?? '' : t;
  }

  factory OrgMessage.fromJson(Map<String, Object?> json) {
    Map<String, String> texts(Object? v) => {
      if (v is Map)
        for (final e in v.entries)
          if (e.value is String) '${e.key}': e.value as String,
    };
    return OrgMessage(
      id: json['id']! as String,
      topic: json['topic'] as String?,
      title: texts(json['title']),
      body: texts(json['body']),
      publishedAt: _date(json['published_at']) ?? DateTime(1970),
      ackRequired: json['ack_required'] == true,
      ackedAt: _date(json['acked_at']),
      ackedBy: json['acked_by'] as String?,
    );
  }
}

/// A drill held or a public event declared by the institution (phase P2b).
class OrgActivity {
  const OrgActivity({
    required this.id,
    required this.kind,
    required this.title,
    required this.startsOn,
    this.endsOn,
    this.participants,
    this.notes,
    this.createdBy,
  });

  final String id;

  /// `drill` | `event`.
  final String kind;
  final String title;
  final DateTime startsOn;
  final DateTime? endsOn;
  final int? participants;
  final String? notes;
  final String? createdBy;

  factory OrgActivity.fromJson(Map<String, Object?> json) => OrgActivity(
    id: json['id']! as String,
    kind: json['kind'] as String? ?? 'drill',
    title: json['title'] as String? ?? '',
    startsOn: _date(json['starts_on']) ?? DateTime(1970),
    endsOn: _date(json['ends_on']),
    participants: (json['participants'] as num?)?.toInt(),
    notes: json['notes'] as String?,
    createdBy: json['created_by'] as String?,
  );
}

/// Point on the institution's map: evacuation point, water point or alarm (phase 4 §5).
class OrgFeature {
  const OrgFeature({required this.kind, this.label, this.location});

  final String kind;
  final String? label;
  final GeoPoint? location;

  factory OrgFeature.fromJson(Map<String, Object?> json) => OrgFeature(
    kind: json['kind'] as String? ?? 'evacuation_point',
    label: json['label'] as String?,
    location: GeoPoint.fromJson(json['location']),
  );
}

/// Safety certificate of the institution (phase 4 §7).
class OrgCertificate {
  const OrgCertificate({
    this.id = '',
    this.kind = 'safety',
    required this.code,
    required this.status,
    this.validUntil,
    this.superseded = false,
    this.needsUpdate,
    this.changes = const [],
    this.stamps = const [],
  });

  final String id;

  /// `safety` (the institution's own) | `prevention` (issued after a prevention visit, phase P3b).
  final String kind;
  final String code;

  /// `draft` | `submitted` | `approved` | `rejected` | `revoked`.
  final String status;
  final DateTime? validUntil;
  final bool superseded;

  /// Phase P3a, on the current approved certificate only (null otherwise): the institution changed
  /// substantively since approval.
  final bool? needsUpdate;
  final List<CertificateChange> changes;
  final List<CertificateStamp> stamps;

  factory OrgCertificate.fromJson(Map<String, Object?> json) => OrgCertificate(
    id: json['id'] as String? ?? '',
    kind: json['kind'] as String? ?? 'safety',
    code: json['code'] as String? ?? '',
    status: json['status'] as String? ?? 'draft',
    validUntil: _date(json['valid_until']),
    superseded: json['superseded'] == true,
    needsUpdate: json['needs_update'] as bool?,
    changes: [
      for (final c in (json['changes'] as List?) ?? const [])
        if (c is Map) CertificateChange.fromJson(c.cast<String, Object?>()),
    ],
    stamps: [
      for (final s in (json['stamps'] as List?) ?? const [])
        if (s is Map) CertificateStamp.fromJson(s.cast<String, Object?>()),
    ],
  );
}

/// One substantive difference between the approved certificate and the institution today (phase P3a §3.4).
class CertificateChange {
  const CertificateChange({required this.section, required this.field});

  /// `identity` | `building` | `classification` | `hazmat` | `documents` | `safety_team` | `evacuation`.
  final String section;
  final String field;

  factory CertificateChange.fromJson(Map<String, Object?> json) =>
      CertificateChange(
        section: json['section'] as String? ?? '',
        field: json['field'] as String? ?? '',
      );
}

/// A stamp put by hand on the paper certificate at a regional administration (phase P3a §3.2).
class CertificateStamp {
  const CertificateStamp({required this.place, this.stampedOn});

  final String place;
  final DateTime? stampedOn;

  factory CertificateStamp.fromJson(Map<String, Object?> json) =>
      CertificateStamp(
        place: json['place'] as String? ?? '',
        stampedOn: _date(json['stamped_on']),
      );
}

/// Member of the institution's account (phase 4 §2).
class OrgMember {
  const OrgMember({required this.role, this.displayName, this.email});

  final String? displayName;
  final String? email;

  /// `admin` | `editor` | `member`.
  final String role;

  factory OrgMember.fromJson(Map<String, Object?> json) => OrgMember(
    displayName: json['display_name'] as String?,
    email: json['email'] as String?,
    role: json['role'] as String? ?? 'member',
  );
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

// ---- Phase P3b: prevention visits and the annual report ----

/// One line of the comparison report: what the institution declared and what the inspector saw.
class VisitItem {
  const VisitItem({
    required this.key,
    required this.section,
    required this.result,
    this.declared,
    this.observed,
    this.note,
  });

  /// `building.capacity`, `hazmat.0`, `equipment.extinguisher`, `site.exits`...
  final String key;
  final String section;

  /// `conform` | `nonconform` | `not_checked`.
  final String result;
  final Object? declared;
  final String? observed;
  final String? note;

  factory VisitItem.fromJson(Map<String, Object?> json) => VisitItem(
    key: json['key'] as String? ?? '',
    section: json['section'] as String? ?? '',
    result: json['result'] as String? ?? 'not_checked',
    declared: json['declared'],
    observed: json['observed'] as String?,
    note: json['note'] as String?,
  );
}

/// The automatic comparison report of a visit (phase P3b §4).
class VisitComparison {
  const VisitComparison({
    this.items = const [],
    this.conform = 0,
    this.nonconform = 0,
    this.notChecked = 0,
    this.missing = const [],
  });

  final List<VisitItem> items;
  final int conform;
  final int nonconform;
  final int notChecked;

  /// Requirements of the institution's family still missing (`safety_file`, `training`...).
  final List<String> missing;

  factory VisitComparison.fromJson(Map<String, Object?> json) =>
      VisitComparison(
        items: [
          for (final i in (json['items'] as List?) ?? const [])
            if (i is Map) VisitItem.fromJson(i.cast<String, Object?>()),
        ],
        conform: (json['conform'] as num?)?.toInt() ?? 0,
        nonconform: (json['nonconform'] as num?)?.toInt() ?? 0,
        notChecked: (json['not_checked'] as num?)?.toInt() ?? 0,
        missing: [
          for (final m in (json['missing'] as List?) ?? const [])
            if (m is String) m,
        ],
      );
}

/// A reservation with its deadline, set by the decision of a visit.
class VisitReservation {
  const VisitReservation({
    required this.id,
    required this.text,
    required this.dueOn,
    required this.state,
    this.itemKey,
    this.responseNote,
    this.liftedAt,
  });

  final String id;
  final String text;
  final DateTime dueOn;

  /// `open` | `responded` | `overdue` | `lifted`.
  final String state;
  final String? itemKey;
  final String? responseNote;
  final DateTime? liftedAt;

  factory VisitReservation.fromJson(Map<String, Object?> json) =>
      VisitReservation(
        id: json['id']! as String,
        text: json['text'] as String? ?? '',
        dueOn: _date(json['due_on']) ?? DateTime(1970),
        state: json['state'] as String? ?? 'open',
        itemKey: json['item_key'] as String?,
        responseNote: json['response_note'] as String?,
        liftedAt: _date(json['lifted_at']),
      );
}

/// A prevention visit of `GET /api/v1/orgs/{id}/prevention/visits` (phase P3b).
class PreventionVisit {
  const PreventionVisit({
    required this.id,
    required this.origin,
    required this.status,
    this.scheduledOn,
    this.inspectorName,
    this.inspectedOn,
    this.comparison,
    this.decision,
    this.decisionReason,
    this.certificate,
    this.reservations = const [],
    this.hasReport = false,
    this.createdAt,
  });

  final String id;

  /// `request` (asked by the institution) | `office` (scheduled by the Office).
  final String origin;

  /// `requested` | `scheduled` | `inspected` | `decided` | `cancelled`.
  final String status;
  final DateTime? scheduledOn;
  final String? inspectorName;
  final DateTime? inspectedOn;
  final VisitComparison? comparison;

  /// `approved` | `approved_with_reservations` | `refused`.
  final String? decision;
  final String? decisionReason;
  final OrgCertificate? certificate;
  final List<VisitReservation> reservations;
  final bool hasReport;
  final DateTime? createdAt;

  factory PreventionVisit.fromJson(Map<String, Object?> json) =>
      PreventionVisit(
        id: json['id']! as String,
        origin: json['origin'] as String? ?? 'request',
        status: json['status'] as String? ?? 'requested',
        scheduledOn: _date(json['scheduled_on']),
        inspectorName: json['inspector_name'] as String?,
        inspectedOn: _date(json['inspected_on']),
        comparison: switch (json['comparison']) {
          final Map<Object?, Object?> c => VisitComparison.fromJson(
            c.cast<String, Object?>(),
          ),
          _ => null,
        },
        decision: json['decision'] as String?,
        decisionReason: json['decision_reason'] as String?,
        certificate: switch (json['certificate']) {
          final Map<Object?, Object?> c => OrgCertificate.fromJson(
            c.cast<String, Object?>(),
          ),
          _ => null,
        },
        reservations: [
          for (final r in (json['reservations'] as List?) ?? const [])
            if (r is Map) VisitReservation.fromJson(r.cast<String, Object?>()),
        ],
        hasReport: json['has_report'] == true,
        createdAt: _date(json['created_at']),
      );
}

/// Counts of the annual report: `valid` / `expiring` / `expired` / `unknown` trainings.
class AnnualTraining {
  const AnnualTraining({
    this.valid = 0,
    this.expiring = 0,
    this.expired = 0,
    this.unknown = 0,
  });

  final int valid;
  final int expiring;
  final int expired;
  final int unknown;

  factory AnnualTraining.fromJson(Map<String, Object?> json) => AnnualTraining(
    valid: (json['valid'] as num?)?.toInt() ?? 0,
    expiring: (json['expiring'] as num?)?.toInt() ?? 0,
    expired: (json['expired'] as num?)?.toInt() ?? 0,
    unknown: (json['unknown'] as num?)?.toInt() ?? 0,
  );
}

/// `GET /api/v1/orgs/{id}/annual-report?year=` (phase P3b §7): the year's activity in one place.
class AnnualReport {
  const AnnualReport({
    required this.year,
    this.drills = const [],
    this.events = const [],
    this.participants = 0,
    this.maintenance = 0,
    this.training = const AnnualTraining(),
    this.visits = const [],
    this.reservationsOpened = 0,
    this.reservationsLifted = 0,
    this.reservationsOverdue = 0,
    this.certificates = const [],
    this.stamps = 0,
    this.reports = 0,
  });

  final int year;
  final List<OrgActivity> drills;
  final List<OrgActivity> events;
  final int participants;
  final int maintenance;
  final AnnualTraining training;
  final List<PreventionVisit> visits;
  final int reservationsOpened;
  final int reservationsLifted;
  final int reservationsOverdue;
  final List<OrgCertificate> certificates;
  final int stamps;
  final int reports;

  factory AnnualReport.fromJson(Map<String, Object?> json) {
    final reservations =
        (json['reservations'] as Map?)?.cast<String, Object?>() ?? const {};
    int count(Object? v) => (v as num?)?.toInt() ?? 0;
    List<OrgActivity> activities(Object? list) => [
      for (final a in (list as List?) ?? const [])
        if (a is Map) OrgActivity.fromJson(a.cast<String, Object?>()),
    ];
    return AnnualReport(
      year: count(json['year']),
      drills: activities(json['drills']),
      events: activities(json['events']),
      participants: count(json['participants']),
      maintenance: count(json['maintenance']),
      training: AnnualTraining.fromJson(
        (json['training'] as Map?)?.cast<String, Object?>() ?? const {},
      ),
      visits: [
        for (final v in (json['visits'] as List?) ?? const [])
          if (v is Map) PreventionVisit.fromJson(v.cast<String, Object?>()),
      ],
      reservationsOpened: count(reservations['opened']),
      reservationsLifted: count(reservations['lifted']),
      reservationsOverdue: count(reservations['overdue']),
      certificates: [
        for (final c in (json['certificates'] as List?) ?? const [])
          if (c is Map) OrgCertificate.fromJson(c.cast<String, Object?>()),
      ],
      stamps: count(json['stamps']),
      reports: count(json['reports']),
    );
  }
}

/// Review point 25: what an institution's camera saw, before the room is told.
class OrgPrealert {
  const OrgPrealert(this.json);

  final Map<String, Object?> json;

  String get id => json['id']! as String;
  String get orgId => json['org_id']! as String;
  String? get orgName => json['org_name'] as String?;

  /// `fire` | `smoke`.
  String get label => json['label'] as String? ?? 'fire';
  double get confidence => (json['confidence'] as num?)?.toDouble() ?? 0;
  bool get simulated => json['simulated'] == true;

  /// `pending` | `cancelled` | `confirmed` | `escalated`.
  String get state => json['state'] as String? ?? 'pending';
  bool get pending => state == 'pending';
  int get secondsLeft => (json['seconds_left'] as num?)?.toInt() ?? 0;
  DateTime get raisedAt => DateTime.parse(json['raised_at']! as String);
  DateTime get deadlineAt => DateTime.parse(json['deadline_at']! as String);
  String? get reason => json['reason'] as String?;
  String? get reportId => json['report_id'] as String?;
  bool get hasFrame => json['has_frame'] == true;
}
