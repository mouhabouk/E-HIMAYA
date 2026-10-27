import '../../core/http/models.dart';

/// Wire models of `/api/v1/crew/prevention` and the inspector's draft (phase P4c,
/// docs/phase-p4/design-staff.md §8).

DateTime? _date(Object? v) => v == null ? null : DateTime.parse(v as String);

/// One line of the grid, built by the server from what the institution declared.
class ChecklistItem {
  const ChecklistItem({
    required this.key,
    required this.section,
    this.declared,
  });

  factory ChecklistItem.fromJson(Map<String, dynamic> j) => ChecklistItem(
    key: j['key'] as String,
    section: j['section'] as String,
    declared: j['declared'],
  );

  final String key;
  final String section;
  final Object? declared;

  /// A count the inspector checks with − and + (equipment, assembly points, floors…).
  int? get declaredCount => switch (declared) {
    final int n => n,
    final double d when d == d.roundToDouble() => d.toInt(),
    _ => null,
  };
}

class VisitReservation {
  const VisitReservation({
    required this.text,
    required this.dueOn,
    required this.state,
    this.itemKey,
  });

  factory VisitReservation.fromJson(Map<String, dynamic> j) => VisitReservation(
    text: j['text'] as String,
    dueOn: DateTime.parse(j['due_on'] as String),
    state: j['state'] as String,
    itemKey: j['item_key'] as String?,
  );

  final String text;
  final DateTime dueOn;
  final String state;
  final String? itemKey;
}

/// A visit as the inspector's phone sees it. [json] is kept as it came, for the offline copy.
class FieldVisit {
  FieldVisit(this.json)
    : id = json['id'] as String,
      status = json['status'] as String,
      orgName = json['org_name'] as String,
      orgKind = json['org_kind'] as String,
      orgAddress = json['org_address'] as String?,
      orgLocation = json['org_location'] == null
          ? null
          : GeoPoint(
              lat: ((json['org_location'] as Map)['lat'] as num).toDouble(),
              lon: ((json['org_location'] as Map)['lon'] as num).toDouble(),
            ),
      scheduledOn = _date(json['scheduled_on']),
      inspectorName = json['inspector_name'] as String?,
      mine = json['mine'] as bool? ?? false,
      takenByOther = json['taken_by_other'] as bool? ?? false,
      decision = json['decision'] as String?,
      checklist = [
        for (final i in json['checklist'] as List? ?? const [])
          ChecklistItem.fromJson(i as Map<String, dynamic>),
      ],
      nonconform = [
        for (final i
            in ((json['comparison'] as Map?)?['items'] as List?) ?? const [])
          if ((i as Map)['result'] == 'nonconform') i['key'] as String,
      ],
      reservations = [
        for (final r in json['reservations'] as List? ?? const [])
          VisitReservation.fromJson(r as Map<String, dynamic>),
      ],
      certificateCode = (json['certificate'] as Map?)?['code'] as String?,
      photoCount = (json['photos'] as List?)?.length ?? 0,
      signed = json['signatures'] != null;

  final Map<String, dynamic> json;
  final String id;
  final String status;
  final String orgName;
  final String orgKind;
  final String? orgAddress;
  final GeoPoint? orgLocation;
  final DateTime? scheduledOn;
  final String? inspectorName;
  final bool mine;
  final bool takenByOther;
  final String? decision;
  final List<ChecklistItem> checklist;

  /// Keys found non-conforming by the inspection recorded on the server.
  final List<String> nonconform;
  final List<VisitReservation> reservations;
  final String? certificateCode;
  final int photoCount;
  final bool signed;

  bool get scheduled => status == 'scheduled';
  bool get inspected => status == 'inspected';
  bool get decided => status == 'decided';

  /// The declared safety team representative, offered as a chip for the attendees.
  String? get declaredRepresentative {
    for (final i in checklist) {
      if (i.key == 'safety_team.representative' && i.declared is String) {
        return i.declared! as String;
      }
    }
    return null;
  }
}

enum Finding {
  conform('conform'),
  nonconform('nonconform'),
  notChecked('not_checked');

  const Finding(this.wire);
  final String wire;
}

/// What the inspector found for one item: a result, and for a non-conformity what was seen
/// (a count, reason chips, a short optional note).
class ItemDraft {
  const ItemDraft({
    this.result = Finding.notChecked,
    this.count,
    this.reasons = const [],
    this.note,
  });

  factory ItemDraft.fromJson(Map<String, dynamic> j) => ItemDraft(
    result: Finding.values.firstWhere(
      (f) => f.wire == j['result'],
      orElse: () => Finding.notChecked,
    ),
    count: j['count'] as int?,
    reasons: [for (final r in j['reasons'] as List? ?? const []) r as String],
    note: j['note'] as String?,
  );

  final Finding result;
  final int? count;
  final List<String> reasons;
  final String? note;

  ItemDraft copyWith({
    Finding? result,
    int? count,
    List<String>? reasons,
    String? note,
    bool clearCount = false,
  }) => ItemDraft(
    result: result ?? this.result,
    count: clearCount ? null : count ?? this.count,
    reasons: reasons ?? this.reasons,
    note: note ?? this.note,
  );

  Map<String, dynamic> toJson() => {
    'result': result.wire,
    'count': ?count,
    'reasons': reasons,
    'note': ?note,
  };
}

/// A photo taken on site, kept encrypted on the phone until the server has it.
class DraftPhoto {
  const DraftPhoto({
    required this.id,
    required this.contentType,
    required this.takenAt,
    this.itemKey,
    this.sent = false,
  });

  factory DraftPhoto.fromJson(Map<String, dynamic> j) => DraftPhoto(
    id: j['id'] as String,
    contentType: j['content_type'] as String,
    takenAt: DateTime.parse(j['taken_at'] as String),
    itemKey: j['item_key'] as String?,
    sent: j['sent'] as bool? ?? false,
  );

  /// Also the `client_id` the server keeps the photo once under.
  final String id;
  final String contentType;
  final DateTime takenAt;
  final String? itemKey;
  final bool sent;

  Map<String, dynamic> toJson() => {
    'id': id,
    'content_type': contentType,
    'taken_at': takenAt.toIso8601String(),
    'item_key': ?itemKey,
    'sent': sent,
  };
}

/// The inspection being filled on the phone, and what waits to be sent: photos first, then the
/// inspection with both signatures, then the decision (design §8.6).
class InspectionDraft {
  const InspectionDraft({
    this.items = const {},
    this.attendees = const [],
    this.representativeName,
    this.representativeRole,
    this.inspectorSignature,
    this.representativeSignature,
    this.photos = const [],
    this.inspection,
    this.inspectionSent = false,
    this.decision,
    this.error,
  });

  factory InspectionDraft.fromJson(Map<String, dynamic> j) => InspectionDraft(
    items: {
      for (final e in (j['items'] as Map? ?? const {}).entries)
        e.key as String: ItemDraft.fromJson(e.value as Map<String, dynamic>),
    },
    attendees: [
      for (final a in j['attendees'] as List? ?? const []) a as String,
    ],
    representativeName: j['representative_name'] as String?,
    representativeRole: j['representative_role'] as String?,
    inspectorSignature: j['inspector_signature'] as String?,
    representativeSignature: j['representative_signature'] as String?,
    photos: [
      for (final p in j['photos'] as List? ?? const [])
        DraftPhoto.fromJson(p as Map<String, dynamic>),
    ],
    inspection: j['inspection'] as Map<String, dynamic>?,
    inspectionSent: j['inspection_sent'] as bool? ?? false,
    decision: j['decision'] as Map<String, dynamic>?,
    error: j['error'] as String?,
  );

  final Map<String, ItemDraft> items;
  final List<String> attendees;
  final String? representativeName;

  /// A role chip key (`director`, `safety_officer`…).
  final String? representativeRole;

  /// PNG in base64, drawn with the finger.
  final String? inspectorSignature;
  final String? representativeSignature;
  final List<DraftPhoto> photos;

  /// The inspection as it will be sent (built when the inspector signs off), null before.
  final Map<String, dynamic>? inspection;
  final bool inspectionSent;

  /// The decision as it will be sent, null before.
  final Map<String, dynamic>? decision;

  /// The server's refusal of the last write (`visit_taken`…), shown until the next try.
  final String? error;

  ItemDraft item(String key) => items[key] ?? const ItemDraft();

  int get unsentPhotos => photos.where((p) => !p.sent).length;

  /// Writes still on the phone.
  int get pending =>
      unsentPhotos +
      (inspection != null && !inspectionSent ? 1 : 0) +
      (decision != null ? 1 : 0);

  bool get signedOff => inspection != null;

  InspectionDraft copyWith({
    Map<String, ItemDraft>? items,
    List<String>? attendees,
    String? representativeName,
    String? representativeRole,
    String? inspectorSignature,
    String? representativeSignature,
    List<DraftPhoto>? photos,
    Map<String, dynamic>? inspection,
    bool? inspectionSent,
    Map<String, dynamic>? decision,
    String? error,
    bool clearError = false,
    bool clearDecision = false,
    bool clearInspectorSignature = false,
    bool clearRepresentativeSignature = false,
  }) => InspectionDraft(
    items: items ?? this.items,
    attendees: attendees ?? this.attendees,
    representativeName: representativeName ?? this.representativeName,
    representativeRole: representativeRole ?? this.representativeRole,
    inspectorSignature: clearInspectorSignature
        ? null
        : inspectorSignature ?? this.inspectorSignature,
    representativeSignature: clearRepresentativeSignature
        ? null
        : representativeSignature ?? this.representativeSignature,
    photos: photos ?? this.photos,
    inspection: inspection ?? this.inspection,
    inspectionSent: inspectionSent ?? this.inspectionSent,
    decision: clearDecision ? null : decision ?? this.decision,
    error: clearError ? null : error ?? this.error,
  );

  Map<String, dynamic> toJson() => {
    'items': {for (final e in items.entries) e.key: e.value.toJson()},
    'attendees': attendees,
    'representative_name': ?representativeName,
    'representative_role': ?representativeRole,
    'inspector_signature': ?inspectorSignature,
    'representative_signature': ?representativeSignature,
    'photos': [for (final p in photos) p.toJson()],
    'inspection': ?inspection,
    'inspection_sent': inspectionSent,
    'decision': ?decision,
    'error': ?error,
  };
}

/// The live summary of the grid, with the decision the server will suggest (one non-conformity
/// suggests reservations).
class GridSummary {
  const GridSummary(this.conform, this.nonconform, this.notChecked);

  factory GridSummary.of(List<ChecklistItem> items, InspectionDraft draft) {
    var c = 0;
    var n = 0;
    for (final i in items) {
      switch (draft.item(i.key).result) {
        case Finding.conform:
          c++;
        case Finding.nonconform:
          n++;
        case Finding.notChecked:
          break;
      }
    }
    return GridSummary(c, n, items.length - c - n);
  }

  final int conform;
  final int nonconform;
  final int notChecked;

  String get suggested =>
      nonconform > 0 ? 'approved_with_reservations' : 'approved';
}

/// A visit downloaded on the phone with its draft.
class VisitPack {
  const VisitPack(this.visit, this.draft);

  factory VisitPack.fromJson(Map<String, dynamic> j) => VisitPack(
    FieldVisit(j['visit'] as Map<String, dynamic>),
    InspectionDraft.fromJson(j['draft'] as Map<String, dynamic>),
  );

  final FieldVisit visit;
  final InspectionDraft draft;

  VisitPack withVisit(FieldVisit v) => VisitPack(v, draft);
  VisitPack withDraft(InspectionDraft d) => VisitPack(visit, d);

  Map<String, dynamic> toJson() => {
    'visit': visit.json,
    'draft': draft.toJson(),
  };
}
