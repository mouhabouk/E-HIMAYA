import 'dart:typed_data';

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

/// The live counters of an incident (phase P4b: light and serious injuries); `transported`
/// is counted by the server from the hospital transports.
class Casualties {
  const Casualties({
    this.injuredLight = 0,
    this.injuredSerious = 0,
    this.deceased = 0,
    this.rescued = 0,
    this.trapped = 0,
    this.transported = 0,
  });

  factory Casualties.fromJson(Map<String, dynamic> j) => Casualties(
    injuredLight: j['injured_light'] as int? ?? 0,
    injuredSerious: j['injured_serious'] as int? ?? 0,
    deceased: j['deceased'] as int? ?? 0,
    rescued: j['rescued'] as int? ?? 0,
    trapped: j['trapped'] as int? ?? 0,
    transported: j['transported'] as int? ?? 0,
  );

  final int injuredLight;
  final int injuredSerious;
  final int deceased;
  final int rescued;
  final int trapped;
  final int transported;

  int get injured => injuredLight + injuredSerious;

  int of(CasualtyCounter c) => switch (c) {
    CasualtyCounter.injuredLight => injuredLight,
    CasualtyCounter.injuredSerious => injuredSerious,
    CasualtyCounter.deceased => deceased,
    CasualtyCounter.rescued => rescued,
    CasualtyCounter.trapped => trapped,
  };
}

enum CasualtyCounter {
  injuredLight('injured_light'),
  injuredSerious('injured_serious'),
  deceased('deceased'),
  rescued('rescued'),
  trapped('trapped');

  const CasualtyCounter(this.wire);

  final String wire;
}

enum Triage { green, yellow, red, black }

/// Approximate age (design §5.6); `legacy` reads the bands of phase P4a.
enum AgeBand {
  under12('under_12'),
  from12('12_17'),
  from18('18_29'),
  from30('30_44'),
  from45('45_59'),
  from60('60_plus'),
  unknown('unknown'),
  legacy('legacy');

  const AgeBand(this.wire);

  final String wire;

  static const choices = [
    under12,
    from12,
    from18,
    from30,
    from45,
    from60,
    unknown,
  ];

  static AgeBand fromWire(String v) => AgeBand.values.firstWhere(
    (a) => a.wire == v,
    orElse: () => AgeBand.legacy,
  );
}

enum Sex { female, male, unknown }

class Transport {
  const Transport({
    required this.id,
    required this.triage,
    required this.ageBand,
    required this.sex,
    required this.hospital,
    this.createdAt,
  });

  factory Transport.fromJson(Map<String, dynamic> j) => Transport(
    id: j['id'] as String,
    triage: Triage.values.byName(j['triage'] as String),
    ageBand: AgeBand.fromWire(j['age_band'] as String),
    sex: Sex.values.byName(j['sex'] as String),
    hospital: j['hospital'] as String,
    createdAt: _date(j['created_at']),
  );

  final String id;
  final Triage triage;
  final AgeBand ageBand;
  final Sex sex;
  final String hospital;
  final DateTime? createdAt;
}

/// Chips of "backup" (design §5.4), in the order shown.
const backupKinds = [
  'fire_engine',
  'ambulance',
  'extrication',
  'ladder',
  'water_tanker',
  'hazmat',
  'police',
  'heavy_equipment',
];

/// Chips of "danger to the crew".
const dangerKinds = [
  'fire_spread',
  'collapse',
  'gas',
  'electricity',
  'violence',
  'traffic',
];

/// A situation report (first, then updates) or the detailed report of a template.
class FieldReport {
  const FieldReport({
    required this.kind,
    required this.category,
    required this.severity,
    required this.backupNeeded,
    required this.crewDanger,
    this.backupKinds = const [],
    this.templateVersion,
    this.answers = const {},
    this.note,
    this.createdAt,
  });

  factory FieldReport.fromJson(Map<String, dynamic> j) => FieldReport(
    kind: j['kind'] as String? ?? 'first',
    category: ReportCategory.fromWire(j['category'] as String?),
    severity: j['severity'] as int?,
    backupNeeded: j['backup_needed'] as bool? ?? false,
    crewDanger: j['crew_danger'] as bool? ?? false,
    backupKinds: [
      for (final k in j['backup_kinds'] as List? ?? const []) k as String,
    ],
    templateVersion: j['template_version'] as int?,
    answers: j['answers'] as Map<String, dynamic>? ?? const {},
    note: j['note'] as String?,
    createdAt: _date(j['created_at']),
  );

  /// `first`, `update` or `detailed`.
  final String kind;
  final ReportCategory? category;
  final int? severity;
  final bool backupNeeded;
  final bool crewDanger;
  final List<String> backupKinds;
  final int? templateVersion;
  final Map<String, dynamic> answers;
  final String? note;
  final DateTime? createdAt;
}

/// "Backup" or "danger to the crew", and when the room saw it.
class CrewAlert {
  const CrewAlert({
    required this.id,
    required this.kind,
    required this.items,
    required this.createdAt,
    this.seenAt,
    this.seenBy,
  });

  factory CrewAlert.fromJson(Map<String, dynamic> j) => CrewAlert(
    id: j['id'] as String,
    kind: j['kind'] as String,
    items: [for (final k in j['items'] as List? ?? const []) k as String],
    createdAt: DateTime.parse(j['created_at'] as String),
    seenAt: _date(j['seen_at']),
    seenBy: j['seen_by_name'] as String?,
  );

  /// `backup` or `danger`.
  final String kind;
  final String id;
  final List<String> items;
  final DateTime createdAt;
  final DateTime? seenAt;
  final String? seenBy;
}

/// A photo, a voice note or a short text sent from the scene.
class FieldAttachment {
  const FieldAttachment({
    required this.id,
    required this.kind,
    required this.createdAt,
    this.body,
    this.durationS,
  });

  factory FieldAttachment.fromJson(Map<String, dynamic> j) => FieldAttachment(
    id: j['id'] as String,
    kind: j['kind'] as String,
    body: j['body'] as String?,
    durationS: (j['duration_s'] as num?)?.toDouble(),
    createdAt: DateTime.parse(j['created_at'] as String),
  );

  /// `photo`, `voice` or `text`.
  final String kind;
  final String id;
  final String? body;
  final double? durationS;
  final DateTime createdAt;
}

/// Words of a template in the three languages; falls back to Arabic, then to any.
class Localized {
  const Localized(this.values);

  factory Localized.fromJson(Object? j) => Localized({
    for (final e in (j as Map<String, dynamic>? ?? const {}).entries)
      e.key: e.value as String,
  });

  final Map<String, String> values;

  String of(String code) =>
      values[code] ?? values['ar'] ?? values.values.firstOrNull ?? '';
}

class TemplateOption {
  const TemplateOption(this.key, this.label);

  factory TemplateOption.fromJson(Map<String, dynamic> j) =>
      TemplateOption(j['key'] as String, Localized.fromJson(j['label']));

  final String key;
  final Localized label;
}

enum FieldType { single, multi, yesno, count }

/// One question of a detailed report, answered with a tap.
class TemplateField {
  const TemplateField({
    required this.key,
    required this.type,
    required this.label,
    this.options = const [],
    this.required = false,
    this.unit,
    this.max,
  });

  factory TemplateField.fromJson(Map<String, dynamic> j) => TemplateField(
    key: j['key'] as String,
    type: FieldType.values.byName(j['type'] as String),
    label: Localized.fromJson(j['label']),
    options: [
      for (final o in j['options'] as List? ?? const [])
        TemplateOption.fromJson(o as Map<String, dynamic>),
    ],
    required: j['required'] as bool? ?? false,
    unit: j['unit'] == null ? null : Localized.fromJson(j['unit']),
    max: j['max'] as int?,
  );

  final String key;
  final FieldType type;
  final Localized label;
  final List<TemplateOption> options;
  final bool required;
  final Localized? unit;
  final int? max;
}

class ReportTemplate {
  const ReportTemplate({
    required this.id,
    required this.version,
    required this.fields,
    this.simulated = false,
  });

  factory ReportTemplate.fromJson(Map<String, dynamic> j) => ReportTemplate(
    id: j['id'] as String,
    version: j['version'] as int,
    simulated: j['simulated'] as bool? ?? false,
    fields: [
      for (final f in j['fields'] as List)
        TemplateField.fromJson(f as Map<String, dynamic>),
    ],
  );

  final String id;
  final int version;
  final bool simulated;
  final List<TemplateField> fields;
}

/// A hospital of the map layers near the incident.
class Hospital {
  const Hospital({
    required this.id,
    required this.name,
    required this.distanceM,
    this.simulated = false,
  });

  factory Hospital.fromJson(Map<String, dynamic> j) => Hospital(
    id: j['id'] as String,
    name: j['name'] as String,
    distanceM: j['distance_m'] as int,
    simulated: j['simulated'] as bool? ?? false,
  );

  final String id;
  final String name;
  final int distanceM;
  final bool simulated;
}

class Mission {
  const Mission({
    required this.id,
    required this.status,
    required this.createdAt,
    required this.incidentId,
    this.order,
    this.acknowledgedAt,
    this.enRouteAt,
    this.onSceneAt,
    this.releasedAt,
    this.category,
    this.classification,
    this.title,
    this.location,
    this.delegationAr,
    this.delegationFr,
    this.opLevel = 1,
    this.fieldReport,
    this.detailedReport,
    this.casualties = const Casualties(),
    this.transports = const [],
    this.alerts = const [],
    this.attachments = const [],
    this.template,
    this.contactPhone,
    this.distanceM,
  });

  factory Mission.fromJson(Map<String, dynamic> j) {
    final inc = j['incident'] as Map<String, dynamic>;
    final loc = inc['location'] as Map<String, dynamic>?;
    Map<String, dynamic>? obj(String k) => j[k] as Map<String, dynamic>?;
    List<Map<String, dynamic>> list(String k) => [
      for (final x in j[k] as List? ?? const []) x as Map<String, dynamic>,
    ];
    return Mission(
      id: j['id'] as String,
      status: _status(j['status'] as String),
      order: j['order'] as String?,
      createdAt: DateTime.parse(j['created_at'] as String),
      acknowledgedAt: _date(j['acknowledged_at']),
      enRouteAt: _date(j['en_route_at']),
      onSceneAt: _date(j['on_scene_at']),
      releasedAt: _date(j['released_at']),
      incidentId: inc['id'] as String,
      category: ReportCategory.fromWire(inc['category'] as String?),
      classification: inc['classification'] as String?,
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
      fieldReport: obj('field_report') == null
          ? null
          : FieldReport.fromJson(obj('field_report')!),
      detailedReport: obj('detailed_report') == null
          ? null
          : FieldReport.fromJson(obj('detailed_report')!),
      casualties: Casualties.fromJson(obj('casualties') ?? const {}),
      transports: [for (final t in list('transports')) Transport.fromJson(t)],
      alerts: [for (final a in list('alerts')) CrewAlert.fromJson(a)],
      attachments: [
        for (final a in list('attachments')) FieldAttachment.fromJson(a),
      ],
      template: obj('template') == null
          ? null
          : ReportTemplate.fromJson(obj('template')!),
      contactPhone: j['contact_phone'] as String?,
      distanceM: j['distance_m'] as int?,
    );
  }

  final String id;
  final MissionStatus status;
  final String? order;
  final DateTime createdAt;
  final DateTime? acknowledgedAt;
  final DateTime? enRouteAt;
  final DateTime? onSceneAt;
  final DateTime? releasedAt;
  final String incidentId;
  final ReportCategory? category;
  final String? classification;
  final String? title;
  final GeoPoint? location;
  final String? delegationAr;
  final String? delegationFr;
  final int opLevel;

  /// The last situation report (first or update).
  final FieldReport? fieldReport;
  final FieldReport? detailedReport;
  final Casualties casualties;
  final List<Transport> transports;
  final List<CrewAlert> alerts;
  final List<FieldAttachment> attachments;

  /// The approved detailed-report template of the incident's type, if any.
  final ReportTemplate? template;

  /// A number the room added to call on the scene (never the citizen's own, automatically).
  final String? contactPhone;
  final int? distanceM;

  bool get active =>
      status == MissionStatus.ordered ||
      status == MissionStatus.enRoute ||
      status == MissionStatus.onScene;

  /// Rings full screen until the leader acknowledges it.
  bool get unacknowledged => active && acknowledgedAt == null;

  /// From the second operational level on, the card shows "high priority".
  bool get highPriority => opLevel >= 2;
}

/// A photo or a voice note ready to send, from the camera or the microphone.
class CapturedMedia {
  const CapturedMedia({
    required this.bytes,
    required this.contentType,
    this.durationS,
  });

  final Uint8List bytes;
  final String contentType;
  final double? durationS;
}
