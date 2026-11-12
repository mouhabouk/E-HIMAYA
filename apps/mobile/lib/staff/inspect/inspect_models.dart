/// Phase I3 (docs/phase-i/design-i.md §6): the inspector's module of the staff app. The inspector
/// registers from the app, receives a code once the general inspectorate activates the account,
/// then runs the missions of their orders: one report per place, answered item by item, the
/// presence and the exit drill, then the recommendations and both signatures. A report signed
/// without network waits on the phone and is sent once (its `client_id`).
library;

/// The app's tokens, issued by the platform (not the identity provider).
class InspectTokens {
  const InspectTokens({
    required this.accessToken,
    required this.expiresAt,
    required this.refreshToken,
    required this.name,
    required this.kind,
    this.expiresOn,
  });

  factory InspectTokens.fromJson(Map<String, dynamic> j) => InspectTokens(
    accessToken: j['access_token'] as String,
    expiresAt: DateTime.parse(j['expires_at'] as String),
    refreshToken: j['refresh_token'] as String,
    name: j['name'] as String? ?? '',
    kind: j['kind'] as String? ?? 'internal',
    expiresOn: j['expires_on'] == null
        ? null
        : DateTime.parse(j['expires_on'] as String),
  );

  final String accessToken;
  final DateTime expiresAt;
  final String refreshToken;
  final String name;

  /// `internal` or `external` (an external account ends on [expiresOn]).
  final String kind;
  final DateTime? expiresOn;

  Map<String, dynamic> toJson() => {
    'access_token': accessToken,
    'expires_at': expiresAt.toUtc().toIso8601String(),
    'refresh_token': refreshToken,
    'name': name,
    'kind': kind,
    'expires_on': expiresOn == null ? null : _day(expiresOn!),
  };
}

String _day(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// One place of a mission order: a unit (gouvernorat, kind and name) or an operations room.
class InspectSite {
  const InspectSite({
    required this.id,
    required this.position,
    required this.target,
    required this.name,
    this.unitKind,
    this.room,
    this.gouvernoratCode,
    this.sections = const [],
    this.inspectionId,
    this.inspectionStatus,
    this.arrivedAt,
    this.arrivedOffline = false,
    this.leftAt,
    this.leftOffline = false,
  });

  factory InspectSite.fromJson(Map<String, dynamic> j) => InspectSite(
    id: j['id'] as String,
    position: (j['position'] as num?)?.toInt() ?? 0,
    target: j['target'] as String? ?? 'unit',
    name: j['name'] as String? ?? '',
    unitKind: j['unit_kind'] as String?,
    room: j['room'] as String?,
    gouvernoratCode: (j['gouvernorat_code'] as num?)?.toInt(),
    sections: [for (final s in (j['sections'] as List? ?? const [])) '$s'],
    inspectionId: j['inspection_id'] as String?,
    inspectionStatus: j['inspection_status'] as String?,
    arrivedAt: _when(j['arrived_at']),
    arrivedOffline: j['arrived_offline'] == true,
    leftAt: _when(j['left_at']),
    leftOffline: j['left_offline'] == true,
  );

  final String id;
  final int position;

  /// `unit` or `room`.
  final String target;
  final String name;
  final String? unitKind;

  /// `central` or `regional`.
  final String? room;
  final int? gouvernoratCode;
  final List<String> sections;
  final String? inspectionId;

  /// `in_progress`, `submitted` or null (not started).
  final String? inspectionStatus;

  /// The inspector's «arrived» and «left» as the server holds them (Yamen 2026-11-12).
  final DateTime? arrivedAt;
  final bool arrivedOffline;
  final DateTime? leftAt;
  final bool leftOffline;

  Map<String, dynamic> toJson() => {
    'id': id,
    'position': position,
    'target': target,
    'name': name,
    'unit_kind': unitKind,
    'room': room,
    'gouvernorat_code': gouvernoratCode,
    'sections': sections,
    'inspection_id': inspectionId,
    'inspection_status': inspectionStatus,
    'arrived_at': arrivedAt?.toUtc().toIso8601String(),
    'arrived_offline': arrivedOffline,
    'left_at': leftAt?.toUtc().toIso8601String(),
    'left_offline': leftOffline,
  };
}

DateTime? _when(Object? v) => v is String ? DateTime.tryParse(v) : null;

/// «Arrived» or «left» on one place, recorded on the phone at the moment of the tap, with or
/// without network, and sent when the network is there (as the agents' app does).
class PresenceMark {
  const PresenceMark({
    required this.siteId,
    required this.kind,
    required this.at,
    this.lat,
    this.lon,
    this.offline = false,
    this.sent = false,
  });

  factory PresenceMark.fromJson(Map<String, dynamic> j) => PresenceMark(
    siteId: j['site_id'] as String,
    kind: j['kind'] as String,
    at: DateTime.parse(j['at'] as String),
    lat: (j['lat'] as num?)?.toDouble(),
    lon: (j['lon'] as num?)?.toDouble(),
    offline: j['offline'] == true,
    sent: j['sent'] == true,
  );

  final String siteId;

  /// `arrived` or `left`.
  final String kind;
  final DateTime at;
  final double? lat;
  final double? lon;

  /// Recorded while the phone had no network.
  final bool offline;
  final bool sent;

  PresenceMark copyWith({bool? offline, bool? sent}) => PresenceMark(
    siteId: siteId,
    kind: kind,
    at: at,
    lat: lat,
    lon: lon,
    offline: offline ?? this.offline,
    sent: sent ?? this.sent,
  );

  Map<String, dynamic> toJson() => {
    'site_id': siteId,
    'kind': kind,
    'at': at.toUtc().toIso8601String(),
    'lat': lat,
    'lon': lon,
    'offline': offline,
    'sent': sent,
  };

  Map<String, dynamic> body() => {
    'kind': kind,
    'at': at.toUtc().toIso8601String(),
    'lat': ?lat,
    'lon': ?lon,
    'offline': offline,
  };
}

/// One of the inspector's reports, for «my inspections» (Yamen 2026-11-12).
class InspectHistoryRow {
  const InspectHistoryRow({
    required this.id,
    required this.missionRef,
    required this.onDate,
    required this.place,
    required this.status,
    required this.startedAt,
    this.kind = 'periodic',
    this.submittedAt,
    this.score,
    this.verdict,
    this.receipt,
  });

  factory InspectHistoryRow.fromJson(Map<String, dynamic> j) =>
      InspectHistoryRow(
        id: j['id'] as String,
        missionRef: j['mission_ref'] as String? ?? '',
        onDate: DateTime.parse(j['on_date'] as String),
        place: j['place'] as String? ?? '',
        status: j['status'] as String? ?? 'in_progress',
        startedAt: DateTime.parse(j['started_at'] as String),
        kind: j['kind'] as String? ?? 'periodic',
        submittedAt: _when(j['submitted_at']),
        score: (j['score'] as num?)?.toInt(),
        verdict: j['verdict'] as String?,
        receipt: j['receipt'] as String?,
      );

  final String id;
  final String missionRef;
  final DateTime onDate;
  final String place;

  /// `in_progress` or `submitted`.
  final String status;
  final DateTime startedAt;
  final String kind;
  final DateTime? submittedAt;
  final int? score;
  final String? verdict;
  final String? receipt;

  Map<String, dynamic> toJson() => {
    'id': id,
    'mission_ref': missionRef,
    'on_date':
        '${onDate.year.toString().padLeft(4, '0')}-${onDate.month.toString().padLeft(2, '0')}-${onDate.day.toString().padLeft(2, '0')}',
    'place': place,
    'status': status,
    'started_at': startedAt.toUtc().toIso8601String(),
    'kind': kind,
    'submitted_at': submittedAt?.toUtc().toIso8601String(),
    'score': score,
    'verdict': verdict,
    'receipt': receipt,
  };
}

/// A mission order assigned to the inspector.
class InspectMission {
  const InspectMission({
    required this.id,
    required this.ref,
    required this.onDate,
    required this.atTime,
    required this.kind,
    required this.sites,
    this.profile,
  });

  factory InspectMission.fromJson(Map<String, dynamic> j) => InspectMission(
    id: j['id'] as String,
    ref: j['ref'] as String? ?? '',
    onDate: DateTime.parse(j['on_date'] as String),
    atTime: (j['at_time'] as String? ?? '').split(':').take(2).join(':'),
    kind: j['kind'] as String? ?? 'periodic',
    sites: [
      for (final s in (j['sites'] as List? ?? const []))
        InspectSite.fromJson(s as Map<String, dynamic>),
    ],
    profile: j['profile'] == null
        ? null
        : InspectProfile.fromJson(j['profile'] as Map<String, dynamic>),
  );

  final String id;

  /// The active model, downloaded with the missions: a place's report opens without network.
  final InspectProfile? profile;

  /// `OM-YYYY-NNNN`.
  final String ref;
  final DateTime onDate;

  /// `HH:MM`.
  final String atTime;

  /// `periodic` or `surprise`.
  final String kind;
  final List<InspectSite> sites;

  Map<String, dynamic> toJson() => {
    'id': id,
    'ref': ref,
    'on_date': _day(onDate),
    'at_time': atTime,
    'kind': kind,
    'sites': [for (final s in sites) s.toJson()],
    'profile': profile?.toJson(),
  };
}

class ProfileAxis {
  const ProfileAxis(this.key, this.name);
  final String key;
  final String name;
}

class ProfileItem {
  const ProfileItem(this.key, this.axis, this.text);
  final String key;
  final String axis;
  final String text;
}

/// The checklist of the model the report was opened with (its version is frozen server side).
class InspectProfile {
  const InspectProfile({required this.axes, required this.items, this.raw});

  factory InspectProfile.fromJson(Map<String, dynamic> j) => InspectProfile(
    axes: [
      for (final a in (j['axes'] as List? ?? const []))
        ProfileAxis(
          (a as Map<String, dynamic>)['key'] as String,
          a['name'] as String? ?? a['key'] as String,
        ),
    ],
    items: [
      for (final i in (j['items'] as List? ?? const []))
        ProfileItem(
          (i as Map<String, dynamic>)['key'] as String,
          i['axis'] as String? ?? '',
          i['text'] as String? ?? i['key'] as String,
        ),
    ],
    raw: j,
  );

  final List<ProfileAxis> axes;
  final List<ProfileItem> items;
  final Map<String, dynamic>? raw;

  List<ProfileItem> itemsOf(String axis) => [
    for (final i in items)
      if (i.axis == axis) i,
  ];

  ProfileItem? item(String key) {
    for (final i in items) {
      if (i.key == key) return i;
    }
    return null;
  }

  Map<String, dynamic> toJson() =>
      raw ??
      {
        'axes': [
          for (final a in axes) {'key': a.key, 'name': a.name},
        ],
        'items': [
          for (final i in items) {'key': i.key, 'axis': i.axis, 'text': i.text},
        ],
      };
}

/// The answers a checklist item takes.
const inspectAnswers = ['ok', 'note', 'ko'];
const inspectPriorities = ['high', 'medium', 'low'];

/// A recommendation written on the phone: detailed (on an item, with a priority) or general.
class RecDraft {
  const RecDraft({
    required this.kind,
    required this.text,
    this.itemKey,
    this.priority,
  });

  factory RecDraft.fromJson(Map<String, dynamic> j) => RecDraft(
    kind: j['kind'] as String,
    text: j['text'] as String,
    itemKey: j['item_key'] as String?,
    priority: j['priority'] as String?,
  );

  /// `detailed` or `general`.
  final String kind;
  final String text;
  final String? itemKey;
  final String? priority;

  Map<String, dynamic> toJson() => {
    'kind': kind,
    'item_key': itemKey,
    'text': text,
    'priority': priority,
  };
}

/// Where a report stands on the phone.
enum DraftState {
  /// Being filled.
  editing,

  /// Signed; waits for the network to be sent.
  queued,

  /// Received by the server: sealed, with its receipt.
  sent,
}

/// One report on the phone, from its opening to its receipt.
class InspectDraft {
  const InspectDraft({
    required this.inspectionId,
    required this.siteId,
    required this.missionRef,
    required this.siteName,
    required this.profile,
    required this.clientId,
    this.serverId,
    this.startedAt,
    this.lat,
    this.lon,
    this.answers = const {},
    this.present,
    this.expected,
    this.exitSeconds,
    this.summary = '',
    this.recs = const [],
    this.headName = '',
    this.inspectorSignature,
    this.headSignature,
    this.signedAt,
    this.state = DraftState.editing,
    this.receipt,
    this.score,
    this.verdict,
  });

  factory InspectDraft.fromJson(Map<String, dynamic> j) => InspectDraft(
    inspectionId: j['inspection_id'] as String,
    siteId: j['site_id'] as String,
    missionRef: j['mission_ref'] as String? ?? '',
    siteName: j['site_name'] as String? ?? '',
    profile: InspectProfile.fromJson(j['profile'] as Map<String, dynamic>),
    clientId: j['client_id'] as String,
    serverId: j['server_id'] as String?,
    startedAt: j['started_at'] == null
        ? null
        : DateTime.parse(j['started_at'] as String),
    lat: (j['lat'] as num?)?.toDouble(),
    lon: (j['lon'] as num?)?.toDouble(),
    answers: {
      for (final e in (j['answers'] as Map? ?? const {}).entries)
        '${e.key}': '${e.value}',
    },
    present: (j['present'] as num?)?.toInt(),
    expected: (j['expected'] as num?)?.toInt(),
    exitSeconds: (j['exit_seconds'] as num?)?.toInt(),
    summary: j['summary'] as String? ?? '',
    recs: [
      for (final r in (j['recs'] as List? ?? const []))
        RecDraft.fromJson(r as Map<String, dynamic>),
    ],
    headName: j['head_name'] as String? ?? '',
    inspectorSignature: j['inspector_signature'] as String?,
    headSignature: j['head_signature'] as String?,
    signedAt: j['signed_at'] == null
        ? null
        : DateTime.parse(j['signed_at'] as String),
    state: DraftState.values.byName(j['state'] as String? ?? 'editing'),
    receipt: j['receipt'] as String?,
    score: (j['score'] as num?)?.toInt(),
    verdict: j['verdict'] as String?,
  );

  final String inspectionId;
  final String siteId;
  final String missionRef;
  final String siteName;
  final InspectProfile profile;

  /// Sent with the report: the server applies it once.
  final String clientId;

  /// The report's id on the server, once it reached it (null while opened offline).
  final String? serverId;

  /// The arrival on the place, recorded on the phone and given to the server.
  final DateTime? startedAt;
  final double? lat;
  final double? lon;
  final Map<String, String> answers;
  final int? present;
  final int? expected;
  final int? exitSeconds;
  final String summary;
  final List<RecDraft> recs;
  final String headName;
  final String? inspectorSignature;
  final String? headSignature;
  final DateTime? signedAt;
  final DraftState state;
  final String? receipt;
  final int? score;
  final String? verdict;

  int get answered => answers.length;
  int get total => profile.items.length;

  /// What the server needs before it seals a report.
  bool get signable =>
      headName.trim().length >= 2 &&
      inspectorSignature != null &&
      headSignature != null &&
      recs.every((r) => r.kind != 'detailed' || r.priority != null);

  InspectDraft copyWith({
    String? serverId,
    InspectProfile? profile,
    Map<String, String>? answers,
    int? Function()? present,
    int? Function()? expected,
    int? Function()? exitSeconds,
    String? summary,
    List<RecDraft>? recs,
    String? headName,
    String? Function()? inspectorSignature,
    String? Function()? headSignature,
    DateTime? Function()? signedAt,
    DraftState? state,
    String? receipt,
    int? score,
    String? verdict,
  }) => InspectDraft(
    inspectionId: inspectionId,
    siteId: siteId,
    missionRef: missionRef,
    siteName: siteName,
    profile: profile ?? this.profile,
    clientId: clientId,
    serverId: serverId ?? this.serverId,
    startedAt: startedAt,
    lat: lat,
    lon: lon,
    answers: answers ?? this.answers,
    present: present == null ? this.present : present(),
    expected: expected == null ? this.expected : expected(),
    exitSeconds: exitSeconds == null ? this.exitSeconds : exitSeconds(),
    summary: summary ?? this.summary,
    recs: recs ?? this.recs,
    headName: headName ?? this.headName,
    inspectorSignature: inspectorSignature == null
        ? this.inspectorSignature
        : inspectorSignature(),
    headSignature: headSignature == null ? this.headSignature : headSignature(),
    signedAt: signedAt == null ? this.signedAt : signedAt(),
    state: state ?? this.state,
    receipt: receipt ?? this.receipt,
    score: score ?? this.score,
    verdict: verdict ?? this.verdict,
  );

  /// `PUT /inspect/inspections/{id}`: what was answered so far.
  Map<String, dynamic> progressJson() => {
    'answers': answers,
    'present': present,
    'expected': expected,
    'exit_seconds': exitSeconds,
  };

  /// `POST /inspect/inspections/{id}/submit`.
  Map<String, dynamic> submitJson() => {
    ...progressJson(),
    'client_id': clientId,
    'summary': summary.trim().isEmpty ? null : summary.trim(),
    'recommendations': [for (final r in recs) r.toJson()],
    'head_name': headName.trim(),
    'inspector_signature': inspectorSignature,
    'head_signature': headSignature,
    'signed_at': signedAt?.toUtc().toIso8601String(),
  };

  Map<String, dynamic> toJson() => {
    'inspection_id': inspectionId,
    'site_id': siteId,
    'mission_ref': missionRef,
    'site_name': siteName,
    'profile': profile.toJson(),
    'client_id': clientId,
    'server_id': serverId,
    'started_at': startedAt?.toUtc().toIso8601String(),
    'lat': lat,
    'lon': lon,
    'answers': answers,
    'present': present,
    'expected': expected,
    'exit_seconds': exitSeconds,
    'summary': summary,
    'recs': [for (final r in recs) r.toJson()],
    'head_name': headName,
    'inspector_signature': inspectorSignature,
    'head_signature': headSignature,
    'signed_at': signedAt?.toUtc().toIso8601String(),
    'state': state.name,
    'receipt': receipt,
    'score': score,
    'verdict': verdict,
  };
}
