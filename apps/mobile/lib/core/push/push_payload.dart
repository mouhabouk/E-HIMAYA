import '../routing/app_router.dart';

/// Kinds of push the server sends (contract §6). The payload never carries personal data.
enum PushKind {
  alert,
  alertCancelled('alert_cancelled'),
  info,
  callout,
  reportStatus('report_status'),
  // Phase B2: a linked contact's SOS message or fired safety check (critical channel), a new
  // link, the owner's own fired check, a staff search of the location history, and the local
  // safety-check reminders (never sent by the server).
  safetyAlert('safety_alert'),
  safetyLink('safety_link'),
  safetyCheckFired('safety_check_fired'),
  safetyHistoryViewed('safety_history_viewed'),
  safetyCheckReminder('safety_check_reminder'),
  // Phase C1-c: a medical file referred to this doctor, a specialist's opinion on a file they hold.
  medicalReferral('medical_referral'),
  medicalOpinion('medical_opinion'),
  // Phase P4d (F-APP-38): the reporter's team is on its way, then there (`team`: en_route |
  // on_scene).
  teamStatus('team_status'),
  // Review point 25 (phase D): a camera of the user's institution saw a fire or smoke; the room
  // is told when the owner confirms or when the delay runs out.
  prealert;

  const PushKind([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static PushKind? fromWire(Object? value) {
    for (final k in values) {
      if (k.wire == value) return k;
    }
    return null;
  }

  /// Shown on the high-importance Android channel (sound, heads-up).
  bool get urgent =>
      this == alert ||
      this == callout ||
      this == safetyAlert ||
      this == prealert ||
      this == safetyCheckFired ||
      this == safetyCheckReminder;
}

/// A push as the app sees it: its kind and data, plus the title and body to display.
class PushPayload {
  const PushPayload({
    required this.kind,
    required this.data,
    this.title,
    this.body,
  });

  final PushKind kind;
  final Map<String, String> data;
  final String? title;
  final String? body;

  /// Null for an unknown or malformed payload (ignored).
  static PushPayload? parse(
    Map<String, Object?> data, {
    String? title,
    String? body,
  }) {
    final kind = PushKind.fromWire(data['type']);
    if (kind == null) return null;
    return PushPayload(
      kind: kind,
      data: {
        for (final e in data.entries)
          if (e.value != null) e.key: '${e.value}',
      },
      title: title,
      body: body,
    );
  }

  String? get id => data['id'];

  /// `high` | `medium` | `low` for alerts.
  String? get severity => data['severity'];

  /// The most severe official alert: full-screen on Android, and through Do Not Disturb when
  /// the user opted in.
  bool get severe => kind == PushKind.alert && severity == 'high';

  /// A content-free personal push (A8): the text is fetched from the API with the user's
  /// identity and shown on the device only.
  bool get redacted => data['redacted'] == '1';

  /// The same push with other text (resolved redacted content, simulator prefix).
  PushPayload withText({String? title, String? body}) => PushPayload(
    kind: kind,
    data: data,
    title: title ?? this.title,
    body: body ?? this.body,
  );

  /// Screen opened when the user taps the notification.
  String get route => switch (kind) {
    PushKind.alert when (id ?? '').isNotEmpty => Routes.alert(id!),
    PushKind.alert ||
    PushKind.alertCancelled ||
    PushKind.info => Routes.notifications,
    PushKind.callout => Routes.callouts,
    PushKind.reportStatus || PushKind.teamStatus => Routes.reports,
    PushKind.safetyAlert when (id ?? '').isNotEmpty => Routes.safetyAlert(id!),
    PushKind.safetyAlert => Routes.safety,
    PushKind.safetyLink => Routes.safetyLinked,
    PushKind.safetyCheckFired ||
    PushKind.safetyCheckReminder => Routes.safetyCheck,
    PushKind.safetyHistoryViewed => Routes.safetyLocationHistory,
    PushKind.medicalReferral || PushKind.medicalOpinion => Routes.doctorFiles,
    PushKind.prealert
        when (data['org_id'] ?? '').isNotEmpty &&
            (data['prealert_id'] ?? '').isNotEmpty =>
      Routes.prealert(data['org_id']!, data['prealert_id']!),
    PushKind.prealert => Routes.institutions,
  };
}
