/// DTOs of the phase-5 volunteer space (contract §5).
library;

/// Volunteer skills (FR-A-020).
enum VolunteerSkill {
  firstAid('first_aid'),
  diving('diving'),
  heavyVehicles('heavy_vehicles'),
  firefighting('firefighting'),
  searchRescue('search_rescue'),
  logistics('logistics'),
  medical('medical'),
  other('other');

  const VolunteerSkill(this.wire);
  final String wire;

  static VolunteerSkill? fromWire(String? value) {
    for (final s in values) {
      if (s.wire == value) return s;
    }
    return null;
  }
}

/// مباشر أو منقطع.
enum VolunteerAvailability {
  continuous,
  intermittent;

  String get wire => name;

  static VolunteerAvailability fromWire(String? value) =>
      value == 'intermittent' ? intermittent : continuous;
}

enum VolunteerStatus {
  pending,
  approved,
  rejected,
  suspended,
  withdrawn;

  static VolunteerStatus fromWire(String? value) =>
      values.asNameMap()[value] ?? pending;

  /// A rejected or withdrawn application is resubmitted with the same form.
  bool get canResubmit => this == rejected || this == withdrawn;
}

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

String _day(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// `GET /api/v1/me/volunteer`.
class Volunteer {
  const Volunteer({
    required this.status,
    required this.skills,
    required this.availability,
    required this.periodFrom,
    required this.submittedAt,
    required this.ready,
    required this.version,
    this.otherSkill,
    this.periodTo,
    this.notes,
    this.reviewReason,
    this.reviewedAt,
    this.readyUntil,
    this.locationConsent = false,
  });

  final VolunteerStatus status;
  final List<VolunteerSkill> skills;
  final String? otherSkill;
  final VolunteerAvailability availability;
  final DateTime periodFrom;
  final DateTime? periodTo;
  final String? notes;
  final String? reviewReason;
  final DateTime submittedAt;
  final DateTime? reviewedAt;
  final bool ready;
  final DateTime? readyUntil;
  final int version;

  /// The volunteer agreed to share their position while ready (phase 10 §4.2).
  final bool locationConsent;

  /// Ready and not past `ready_until` (the server ends readiness at that time).
  bool isReadyAt(DateTime now) =>
      ready && (readyUntil == null || readyUntil!.isAfter(now));

  /// Today (local date) within the declared period.
  bool inPeriod(DateTime now) {
    final today = DateTime(now.year, now.month, now.day);
    final from = DateTime(periodFrom.year, periodFrom.month, periodFrom.day);
    if (today.isBefore(from)) return false;
    final to = periodTo;
    return to == null || !today.isAfter(DateTime(to.year, to.month, to.day));
  }

  factory Volunteer.fromJson(Map<String, Object?> json) => Volunteer(
    status: VolunteerStatus.fromWire(json['status'] as String?),
    skills: [
      for (final s in (json['skills'] as List? ?? const []))
        ?VolunteerSkill.fromWire(s as String?),
    ],
    otherSkill: json['other_skill'] as String?,
    availability: VolunteerAvailability.fromWire(
      json['availability'] as String?,
    ),
    periodFrom: _date(json['period_from']) ?? DateTime(1970),
    periodTo: _date(json['period_to']),
    notes: json['notes'] as String?,
    reviewReason: json['review_reason'] as String?,
    submittedAt: _date(json['submitted_at']) ?? DateTime(1970),
    reviewedAt: _date(json['reviewed_at']),
    ready: json['ready'] == true,
    readyUntil: _date(json['ready_until']),
    version: (json['version'] as num?)?.toInt() ?? 1,
    locationConsent: json['location_consent'] == true,
  );
}

/// Body of `PUT /api/v1/me/volunteer`.
class VolunteerInput {
  const VolunteerInput({
    required this.skills,
    required this.availability,
    required this.periodFrom,
    this.periodTo,
    this.otherSkill,
    this.notes,
    this.version,
  });

  final Set<VolunteerSkill> skills;
  final VolunteerAvailability availability;
  final DateTime periodFrom;
  final DateTime? periodTo;
  final String? otherSkill;
  final String? notes;
  final int? version;

  Map<String, Object?> toJson() => {
    'skills': [
      for (final s in VolunteerSkill.values)
        if (skills.contains(s)) s.wire,
    ],
    'other_skill': skills.contains(VolunteerSkill.other)
        ? _blankToNull(otherSkill)
        : null,
    'availability': availability.wire,
    'period_from': _day(periodFrom),
    'period_to': periodTo == null ? null : _day(periodTo!),
    'notes': _blankToNull(notes),
    'version': ?version,
  };

  static String? _blankToNull(String? v) =>
      v == null || v.trim().isEmpty ? null : v.trim();
}

/// Answer of a target to a call-out.
enum CalloutTargetStatus {
  sent,
  accepted,
  declined,
  expired,
  arrived;

  static CalloutTargetStatus fromWire(String? value) =>
      values.asNameMap()[value] ?? sent;
}

enum CalloutStatus {
  open,
  filled,
  cancelled,
  closed;

  static CalloutStatus fromWire(String? value) =>
      values.asNameMap()[value] ?? closed;
}

/// `GET /api/v1/me/callouts` item (UC-05, FR-A-023).
class MyCallout {
  const MyCallout({
    required this.id,
    required this.incidentCategory,
    required this.skill,
    required this.status,
    required this.myStatus,
    required this.createdAt,
    this.message,
    this.distanceM,
    this.lat,
    this.lon,
    this.etaMinutes,
  });

  final String id;
  final String incidentCategory;
  final String? message;
  final VolunteerSkill? skill;
  final int? distanceM;
  final double? lat;
  final double? lon;
  final CalloutStatus status;
  final CalloutTargetStatus myStatus;
  final int? etaMinutes;
  final DateTime createdAt;

  /// The volunteer can still answer.
  bool get canRespond =>
      status == CalloutStatus.open && myStatus == CalloutTargetStatus.sent;

  /// Accepted and on the way: arrival can be reported.
  bool get canArrive =>
      myStatus == CalloutTargetStatus.accepted &&
      status != CalloutStatus.cancelled &&
      status != CalloutStatus.closed;

  factory MyCallout.fromJson(Map<String, Object?> json) {
    final location = json['location'];
    return MyCallout(
      id: json['id']! as String,
      incidentCategory: json['incident_category'] as String? ?? 'other',
      message: json['message'] as String?,
      skill: VolunteerSkill.fromWire(json['skill'] as String?),
      distanceM: (json['distance_m'] as num?)?.toInt(),
      lat: location is Map ? (location['lat'] as num?)?.toDouble() : null,
      lon: location is Map ? (location['lon'] as num?)?.toDouble() : null,
      status: CalloutStatus.fromWire(json['status'] as String?),
      myStatus: CalloutTargetStatus.fromWire(json['my_status'] as String?),
      etaMinutes: (json['eta_minutes'] as num?)?.toInt(),
      createdAt: _date(json['created_at']) ?? DateTime(1970),
    );
  }
}

/// Phase D (S2-5): the key of the volunteer's signed SMS answers (EH3) and the volunteer's id.
class VolunteerSmsKey {
  const VolunteerSmsKey(this.key, this.volunteerId);
  final String key;
  final String volunteerId;
}
