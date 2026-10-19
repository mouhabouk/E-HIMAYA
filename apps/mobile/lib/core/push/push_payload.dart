import '../routing/app_router.dart';

/// Kinds of push the server sends (contract §6). The payload never carries personal data.
enum PushKind {
  alert,
  alertCancelled('alert_cancelled'),
  info,
  callout,
  reportStatus('report_status');

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
  bool get urgent => this == alert || this == callout;
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

  /// Screen opened when the user taps the notification.
  String get route => switch (kind) {
    PushKind.alert when (id ?? '').isNotEmpty => Routes.alert(id!),
    PushKind.alert ||
    PushKind.alertCancelled ||
    PushKind.info => Routes.notifications,
    PushKind.callout => Routes.callouts,
    PushKind.reportStatus => Routes.reports,
  };
}
