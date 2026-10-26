import '../core/http/models.dart';

/// Wire models of `/api/v1/crew` (docs/api/openapi.json, phase P4a).

DateTime? _date(Object? v) => v == null ? null : DateTime.parse(v as String);

class CrewVehicle {
  const CrewVehicle({
    required this.id,
    required this.label,
    required this.kind,
    required this.unitName,
    this.status,
    this.onShift = false,
  });

  factory CrewVehicle.fromJson(Map<String, dynamic> j) => CrewVehicle(
    id: j['id'] as String,
    label: j['label'] as String,
    kind: j['kind'] as String,
    unitName: j['unit_name'] as String,
    status: j['status'] as String?,
    onShift: j['on_shift'] as bool? ?? false,
  );

  final String id;
  final String label;
  final String kind;
  final String unitName;
  final String? status;
  final bool onShift;
}

class CrewShift {
  const CrewShift({
    required this.id,
    required this.vehicle,
    required this.crewSize,
    required this.startedAt,
    this.crewNames,
  });

  factory CrewShift.fromJson(Map<String, dynamic> j) => CrewShift(
    id: j['id'] as String,
    vehicle: CrewVehicle.fromJson(j['resource'] as Map<String, dynamic>),
    crewSize: j['crew_size'] as int,
    crewNames: j['crew_names'] as String?,
    startedAt: DateTime.parse(j['started_at'] as String),
  );

  final String id;
  final CrewVehicle vehicle;
  final int crewSize;
  final String? crewNames;
  final DateTime startedAt;
}

class CrewMe {
  const CrewMe({
    required this.name,
    required this.gouvernoratCode,
    required this.deviceId,
    this.shift,
  });

  factory CrewMe.fromJson(Map<String, dynamic> j) => CrewMe(
    name: j['name'] as String?,
    gouvernoratCode: j['gouvernorat_code'] as int,
    deviceId: (j['device'] as Map<String, dynamic>)['id'] as String,
    shift: j['shift'] == null
        ? null
        : CrewShift.fromJson(j['shift'] as Map<String, dynamic>),
  );

  final String? name;
  final int gouvernoratCode;
  final String deviceId;
  final CrewShift? shift;
}

enum MissionStatus { ordered, enRoute, onScene, released, cancelled }

MissionStatus _status(String s) => switch (s) {
  'en_route' => MissionStatus.enRoute,
  'on_scene' => MissionStatus.onScene,
  'released' => MissionStatus.released,
  'cancelled' => MissionStatus.cancelled,
  _ => MissionStatus.ordered,
};

/// The four live counters of an incident.
class Casualties {
  const Casualties({
    this.injured = 0,
    this.deceased = 0,
    this.rescued = 0,
    this.trapped = 0,
  });

  factory Casualties.fromJson(Map<String, dynamic> j) => Casualties(
    injured: j['injured'] as int? ?? 0,
    deceased: j['deceased'] as int? ?? 0,
    rescued: j['rescued'] as int? ?? 0,
    trapped: j['trapped'] as int? ?? 0,
  );

  final int injured;
  final int deceased;
  final int rescued;
  final int trapped;

  int of(CasualtyCounter c) => switch (c) {
    CasualtyCounter.injured => injured,
    CasualtyCounter.deceased => deceased,
    CasualtyCounter.rescued => rescued,
    CasualtyCounter.trapped => trapped,
  };
}

enum CasualtyCounter { injured, deceased, rescued, trapped }

enum Triage { red, yellow, green, black }

enum AgeBand { child, adult, elderly, unknown }

enum Sex { female, male, unknown }

class Transport {
  const Transport({
    required this.id,
    required this.triage,
    required this.ageBand,
    required this.sex,
    required this.hospital,
  });

  factory Transport.fromJson(Map<String, dynamic> j) => Transport(
    id: j['id'] as String,
    triage: Triage.values.byName(j['triage'] as String),
    ageBand: AgeBand.values.byName(j['age_band'] as String),
    sex: Sex.values.byName(j['sex'] as String),
    hospital: j['hospital'] as String,
  );

  final String id;
  final Triage triage;
  final AgeBand ageBand;
  final Sex sex;
  final String hospital;
}

class FieldReport {
  const FieldReport({
    required this.category,
    required this.severity,
    required this.backupNeeded,
    required this.crewDanger,
  });

  factory FieldReport.fromJson(Map<String, dynamic> j) => FieldReport(
    category: ReportCategory.fromWire(j['category'] as String?),
    severity: j['severity'] as int,
    backupNeeded: j['backup_needed'] as bool? ?? false,
    crewDanger: j['crew_danger'] as bool? ?? false,
  );

  final ReportCategory? category;
  final int severity;
  final bool backupNeeded;
  final bool crewDanger;
}

class Mission {
  const Mission({
    required this.id,
    required this.status,
    required this.createdAt,
    required this.incidentId,
    this.order,
    this.acknowledgedAt,
    this.category,
    this.title,
    this.location,
    this.delegationAr,
    this.delegationFr,
    this.opLevel = 1,
    this.fieldReport,
    this.casualties = const Casualties(),
    this.transports = const [],
    this.distanceM,
  });

  factory Mission.fromJson(Map<String, dynamic> j) {
    final inc = j['incident'] as Map<String, dynamic>;
    final loc = inc['location'] as Map<String, dynamic>?;
    return Mission(
      id: j['id'] as String,
      status: _status(j['status'] as String),
      order: j['order'] as String?,
      createdAt: DateTime.parse(j['created_at'] as String),
      acknowledgedAt: _date(j['acknowledged_at']),
      incidentId: inc['id'] as String,
      category: ReportCategory.fromWire(inc['category'] as String?),
      title: inc['title'] as String?,
      location: loc == null
          ? null
          : GeoPoint(
              lat: (loc['lat'] as num).toDouble(),
              lon: (loc['lon'] as num).toDouble(),
            ),
      delegationAr: inc['delegation_ar'] as String?,
      delegationFr: inc['delegation_fr'] as String?,
      opLevel: inc['op_level'] as int? ?? 1,
      fieldReport: j['field_report'] == null
          ? null
          : FieldReport.fromJson(j['field_report'] as Map<String, dynamic>),
      casualties: Casualties.fromJson(
        j['casualties'] as Map<String, dynamic>? ?? const {},
      ),
      transports: [
        for (final t in j['transports'] as List? ?? const [])
          Transport.fromJson(t as Map<String, dynamic>),
      ],
      distanceM: j['distance_m'] as int?,
    );
  }

  final String id;
  final MissionStatus status;
  final String? order;
  final DateTime createdAt;
  final DateTime? acknowledgedAt;
  final String incidentId;
  final ReportCategory? category;
  final String? title;
  final GeoPoint? location;
  final String? delegationAr;
  final String? delegationFr;
  final int opLevel;
  final FieldReport? fieldReport;
  final Casualties casualties;
  final List<Transport> transports;
  final int? distanceM;

  bool get active =>
      status == MissionStatus.ordered ||
      status == MissionStatus.enRoute ||
      status == MissionStatus.onScene;

  /// Rings full screen until the leader acknowledges it.
  bool get unacknowledged => active && acknowledgedAt == null;
}
