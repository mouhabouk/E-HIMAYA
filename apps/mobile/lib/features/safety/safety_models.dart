import '../../core/http/models.dart';

/// Personal safety (phase B2, docs/phase-b/design-b2.md): what the API returns, and the pure
/// helpers that build the SOS message, the SMS and WhatsApp links and the live location link.

DateTime _date(Object? v) => DateTime.parse(v! as String);
DateTime? _dateOrNull(Object? v) => v is String ? DateTime.parse(v) : null;

/// Another e-Himaya user linked by an accepted invitation (both ways).
class SafetyLink {
  const SafetyLink({
    required this.id,
    required this.createdAt,
    this.firstName,
    this.phone,
  });

  final String id;
  final String? firstName;
  final String? phone;
  final DateTime createdAt;

  factory SafetyLink.fromJson(Map<String, Object?> json) => SafetyLink(
    id: json['id']! as String,
    firstName: json['first_name'] as String?,
    phone: json['phone'] as String?,
    createdAt: _date(json['created_at']),
  );
}

class InvitationCode {
  const InvitationCode({required this.code, required this.expiresAt});

  final String code;
  final DateTime expiresAt;

  factory InvitationCode.fromJson(Map<String, Object?> json) => InvitationCode(
    code: json['code']! as String,
    expiresAt: _date(json['expires_at']),
  );
}

class InvitationPreview {
  const InvitationPreview({
    required this.expiresAt,
    this.firstName,
    this.phoneHint,
  });

  final String? firstName;
  final String? phoneHint;
  final DateTime expiresAt;

  factory InvitationPreview.fromJson(Map<String, Object?> json) =>
      InvitationPreview(
        firstName: json['first_name'] as String?,
        phoneHint: json['phone_hint'] as String?,
        expiresAt: _date(json['expires_at']),
      );
}

class SafetyPoint {
  const SafetyPoint({required this.point, required this.at});

  final GeoPoint point;
  final DateTime at;

  static SafetyPoint? fromJson(Object? json) {
    final p = GeoPoint.fromJson(json);
    if (p == null || json is! Map || json['at'] is! String) return null;
    return SafetyPoint(point: p, at: DateTime.parse(json['at'] as String));
  }
}

class LiveState {
  const LiveState({
    required this.active,
    required this.points,
    required this.expiresAt,
    this.battery,
    this.updatedAt,
    this.stoppedAt,
  });

  final bool active;
  final List<SafetyPoint> points;
  final int? battery;
  final DateTime? updatedAt;
  final DateTime expiresAt;
  final DateTime? stoppedAt;

  SafetyPoint? get last => points.isEmpty ? null : points.last;

  factory LiveState.fromJson(Map<String, Object?> json) => LiveState(
    active: json['active'] == true,
    points: [
      for (final p in (json['points'] as List?) ?? const [])
        ?SafetyPoint.fromJson(p),
    ],
    battery: json['battery'] as int?,
    updatedAt: _dateOrNull(json['updated_at']),
    expiresAt: _date(json['expires_at']),
    stoppedAt: _dateOrNull(json['stopped_at']),
  );
}

/// An alert sent in the app to linked contacts: an SOS message (`sos`) or a fired safety check
/// (`check`). [mine]: sent by this user (then [recipients] and [seenBy] are known).
class SafetyAlertView {
  const SafetyAlertView({
    required this.id,
    required this.kind,
    required this.mine,
    required this.message,
    required this.createdAt,
    required this.expiresAt,
    required this.seen,
    this.senderFirstName,
    this.senderPhone,
    this.position,
    this.battery,
    this.recipients,
    this.seenBy,
    this.live,
  });

  final String id;
  final String kind;
  final bool mine;
  final String? senderFirstName;
  final String? senderPhone;
  final String message;
  final SafetyPoint? position;
  final int? battery;
  final DateTime createdAt;
  final DateTime expiresAt;
  final bool seen;
  final int? recipients;
  final int? seenBy;
  final LiveState? live;

  bool get isCheck => kind == 'check';

  /// The newest known position: the live share when it moved, else the one sent with the alert.
  SafetyPoint? get latest => live?.last ?? position;

  factory SafetyAlertView.fromJson(Map<String, Object?> json) =>
      SafetyAlertView(
        id: json['id']! as String,
        kind: json['kind']! as String,
        mine: json['mine'] == true,
        senderFirstName: json['sender_first_name'] as String?,
        senderPhone: json['sender_phone'] as String?,
        message: json['message']! as String,
        position: SafetyPoint.fromJson(json['position']),
        battery: json['battery'] as int?,
        createdAt: _date(json['created_at']),
        expiresAt: _date(json['expires_at']),
        seen: json['seen'] == true,
        recipients: json['recipients'] as int?,
        seenBy: json['seen_by'] as int?,
        live: json['live'] is Map
            ? LiveState.fromJson(json['live']! as Map<String, Object?>)
            : null,
      );
}

class LiveShareStart {
  const LiveShareStart({
    required this.id,
    required this.token,
    required this.expiresAt,
  });

  final String id;
  final String token;
  final DateTime expiresAt;

  factory LiveShareStart.fromJson(Map<String, Object?> json) => LiveShareStart(
    id: json['id']! as String,
    token: json['token']! as String,
    expiresAt: _date(json['expires_at']),
  );
}

class SafetyCheckState {
  const SafetyCheckState({
    required this.id,
    required this.dueAt,
    required this.status,
    required this.contacts,
    this.alertId,
  });

  final String id;
  final DateTime dueAt;

  /// `active` | `ok` | `fired` | `cancelled`.
  final String status;
  final String? alertId;

  /// Linked contacts the server would alert now.
  final int contacts;

  bool get active => status == 'active';

  factory SafetyCheckState.fromJson(Map<String, Object?> json) =>
      SafetyCheckState(
        id: json['id']! as String,
        dueAt: _date(json['due_at']),
        status: json['status']! as String,
        alertId: json['alert_id'] as String?,
        contacts: (json['contacts'] as int?) ?? 0,
      );
}

/// The 72-hour location history (off for the platform until the legal review).
class HistoryState {
  const HistoryState({
    required this.available,
    required this.enabled,
    required this.noticeVersion,
    this.until,
  });

  final bool available;
  final bool enabled;
  final DateTime? until;
  final String noticeVersion;

  static const off = HistoryState(
    available: false,
    enabled: false,
    noticeVersion: '',
  );

  factory HistoryState.fromJson(Map<String, Object?> json) => HistoryState(
    available: json['available'] == true,
    enabled: json['enabled'] == true,
    until: _dateOrNull(json['until']),
    noticeVersion: (json['notice_version'] as String?) ?? '',
  );
}

// ---------------------------------------------------------------- pure helpers

abstract final class SafetyRules {
  static const maxContacts = 10;
  static const messageMax = 500;
  static const liveMinutes = [15, 30, 60, 120, 240, 480];
  static const checkMinutes = [30, 60, 120, 240, 480, 720];

  /// The 7b consent text this app shows (the server keeps it with the consent).
  static const medicalConsentVersion = '7b-2026-10';
}

/// A number the SMS and WhatsApp apps accept: 8 Tunisian digits get `+216`, `00…` becomes `+…`.
/// Null when it cannot be a phone number.
String? normalizeContactPhone(String raw) {
  var n = raw.replaceAll(RegExp(r'[\s\-().]'), '');
  if (n.startsWith('00')) n = '+${n.substring(2)}';
  if (RegExp(r'^\d{8}$').hasMatch(n)) n = '+216$n';
  if (RegExp(r'^216\d{8}$').hasMatch(n)) n = '+$n';
  return RegExp(r'^\+\d{6,15}$').hasMatch(n) ? n : null;
}

/// Labels of the SOS message, in the user's language (from the ARB files).
class SosLabels {
  const SosLabels({
    required this.position,
    required this.accuracy,
    required this.time,
    required this.battery,
    required this.noPosition,
    this.subject = 'e-Himaya SOS',
  });

  /// Subject of the e-mail channel (review point 6).
  final String subject;
  final String position;
  final String accuracy;
  final String time;
  final String battery;
  final String noPosition;
}

/// OpenStreetMap link of a position (opens in any browser; no account, no app needed).
Uri mapLink(GeoPoint p) => Uri.parse(
  'https://www.openstreetmap.org/?mlat=${p.lat.toStringAsFixed(5)}'
  '&mlon=${p.lon.toStringAsFixed(5)}#map=17/${p.lat.toStringAsFixed(5)}/${p.lon.toStringAsFixed(5)}',
);

/// Addition 5: the user's text, then the position link, its accuracy, the time and the battery.
String sosMessageText({
  required String template,
  required SosLabels labels,
  required DateTime at,
  GeoPoint? position,
  int? battery,
  Uri? liveLink,
}) {
  final hh = at.hour.toString().padLeft(2, '0');
  final mm = at.minute.toString().padLeft(2, '0');
  final lines = <String>[template.trim()];
  if (position == null) {
    lines.add(labels.noPosition);
  } else {
    lines.add('${labels.position}: ${mapLink(position)}');
    final acc = position.accuracyM;
    if (acc != null && acc.isFinite && acc > 0) {
      lines.add('${labels.accuracy}: ± ${acc.ceil()} m');
    }
  }
  if (liveLink != null) lines.add(liveLink.toString());
  lines.add('${labels.time}: $hh:$mm');
  if (battery != null) lines.add('${labels.battery}: $battery%');
  return lines.join('\n');
}

/// `sms:` URI for several recipients at once (RFC 5724: comma-separated); the user presses Send.
Uri smsGroupUri(List<String> phones, String body) =>
    Uri.parse('sms:${phones.join(',')}?body=${Uri.encodeComponent(body)}');

/// Review point 6: the mail app with every address in blind copy and the text ready (the user
/// presses Send there, as for the SMS).
Uri emailGroupUri(List<String> emails, String subject, String body) => Uri(
  scheme: 'mailto',
  query: [
    'bcc=${emails.map(Uri.encodeComponent).join(',')}',
    'subject=${Uri.encodeComponent(subject)}',
    'body=${Uri.encodeComponent(body)}',
  ].join('&'),
);

/// A plausible e-mail address (the mail app checks the rest), lower-cased; null otherwise.
String? normalizeContactEmail(String? value) {
  final v = value?.trim().toLowerCase() ?? '';
  return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v) ? v : null;
}

/// WhatsApp chat with one contact and the text ready; WhatsApp never sends on its own.
Uri whatsAppUri(String phone, String text) => Uri.parse(
  'https://wa.me/${phone.replaceAll('+', '')}?text=${Uri.encodeComponent(text)}',
);

/// WhatsApp's own picker (a group chosen by the user), with the text ready.
Uri whatsAppShareUri(String text) =>
    Uri.parse('https://wa.me/?text=${Uri.encodeComponent(text)}');

/// The portal page of a live location share. The token travels in the fragment, which browsers
/// never send to a server, so it never lands in an access log.
Uri liveLink(String portalUrl, String token) {
  final base = portalUrl.endsWith('/')
      ? portalUrl.substring(0, portalUrl.length - 1)
      : portalUrl;
  return Uri.parse('$base/live#$token');
}

/// A contact belongs to a group (groups kept as `,3,7,`).
bool inGroup(String groups, int groupId) => groups.contains(',$groupId,');

String withGroup(String groups, int groupId, bool member) {
  final ids = groups.split(',').where((s) => s.isNotEmpty).toSet();
  member ? ids.add('$groupId') : ids.remove('$groupId');
  return ids.isEmpty ? ',' : ',${ids.join(',')},';
}

/// The 7b medical file (all optional), as kept in the phone's encrypted database and sent with a
/// report only when the user ticks it.
class MedicalFile {
  const MedicalFile({
    this.sex,
    this.birthDate,
    this.bloodGroup,
    this.treatmentCard,
    this.allergies,
    this.conditions,
    this.medications,
    this.other,
    this.contactName,
    this.contactPhone,
    this.card,
  });

  /// Wire names of the fields, in the order they are shown.
  static const fieldKeys = [
    'sex',
    'birth_date',
    'blood_group',
    'treatment_card',
    'allergies',
    'conditions',
    'medications',
    'other',
    'contact_name',
    'contact_phone',
  ];

  /// Phase C1-b: what the emergency card shows unless the user chose otherwise (readable by the
  /// operations room and the rescuers; the rest is locked for the doctors).
  static const defaultCard = {
    'blood_group',
    'allergies',
    'conditions',
    'medications',
    'contact_name',
    'contact_phone',
  };

  static const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

  final String? sex;
  final DateTime? birthDate;
  final String? bloodGroup;
  final String? treatmentCard;
  final String? allergies;
  final String? conditions;
  final String? medications;
  final String? other;
  final String? contactName;
  final String? contactPhone;

  /// The fields the user chose for the emergency card; null: [defaultCard].
  final Set<String>? card;

  Set<String> get cardFields => card ?? defaultCard;

  static String? _s(Object? v) =>
      v is String && v.trim().isNotEmpty ? v.trim() : null;

  factory MedicalFile.fromJson(Map<String, Object?> json) => MedicalFile(
    sex: _s(json['sex']),
    birthDate: json['birth_date'] is String
        ? DateTime.tryParse(json['birth_date']! as String)
        : null,
    bloodGroup: _s(json['blood_group']),
    treatmentCard: _s(json['treatment_card']),
    allergies: _s(json['allergies']),
    conditions: _s(json['conditions']),
    medications: _s(json['medications']),
    other: _s(json['other']),
    contactName: _s(json['contact_name']),
    contactPhone: _s(json['contact_phone']),
    card: json['_card'] is List
        ? {
            for (final k in json['_card']! as List)
              if (fieldKeys.contains(k)) k as String,
          }
        : null,
  );

  /// Only the fields filled in (the API refuses unknown keys and stores nothing for an empty file).
  Map<String, Object?> toJson() {
    final d = birthDate;
    return {
      'sex': ?sex,
      if (d != null)
        'birth_date':
            '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}',
      'blood_group': ?bloodGroup,
      'treatment_card': ?treatmentCard,
      'allergies': ?allergies,
      'conditions': ?conditions,
      'medications': ?medications,
      'other': ?other,
      'contact_name': ?contactName,
      'contact_phone': ?contactPhone,
    };
  }

  bool get isEmpty => toJson().isEmpty;

  /// As kept in the phone's encrypted database: the fields and the card choice.
  Map<String, Object?> toStorageJson() => {
    ...toJson(),
    if (card != null) '_card': [...card!]..sort(),
  };

  /// The emergency card sent with a report (`medical`).
  Map<String, Object?> cardJson() => {
    for (final e in toJson().entries)
      if (cardFields.contains(e.key)) e.key: e.value,
  };

  /// The rest, locked on the phone for the doctors before it leaves (`medical_locked`).
  Map<String, Object?> lockedJson() => {
    for (final e in toJson().entries)
      if (!cardFields.contains(e.key)) e.key: e.value,
  };
}
