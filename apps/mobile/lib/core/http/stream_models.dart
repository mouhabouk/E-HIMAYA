/// DTOs of the phase-6 live streaming endpoints (contract §2, snake_case JSON).
library;

/// `POST /api/v1/reports/{report_id}/streams` → 201: what the app needs to publish over WHIP.
class LiveStreamGrant {
  const LiveStreamGrant({
    required this.streamId,
    required this.path,
    required this.whipUrl,
    required this.publishToken,
    required this.maxDuration,
    required this.locationInterval,
    required this.simulated,
    this.expiresAt,
  });

  final String streamId;

  /// `live/<uuid>` on MediaMTX.
  final String path;
  final Uri whipUrl;

  /// Sent as `Authorization: Bearer` on the WHIP requests only; never logged nor stored.
  final String publishToken;

  /// Deadline to start publishing (10 minutes after creation).
  final DateTime? expiresAt;
  final Duration maxDuration;
  final Duration locationInterval;

  /// The platform runs in simulation (contract §6): the amber band is shown.
  final bool simulated;

  /// Defaults when a field is missing: 15 minutes, a position every 10 s (the server accepts at
  /// most one every 3 s).
  static const defaultMaxDuration = Duration(seconds: 900);
  static const defaultLocationInterval = Duration(seconds: 10);
  static const minLocationInterval = Duration(seconds: 3);

  factory LiveStreamGrant.fromJson(Map<String, Object?> json) {
    final maxS = (json['max_duration_s'] as num?)?.toInt();
    final locS = (json['location_interval_s'] as num?)?.toInt();
    return LiveStreamGrant(
      streamId: json['stream_id']! as String,
      path: json['path'] as String? ?? '',
      whipUrl: Uri.parse(json['whip_url']! as String),
      publishToken: json['publish_token']! as String,
      expiresAt: DateTime.tryParse(json['expires_at'] as String? ?? ''),
      maxDuration: maxS == null || maxS <= 0
          ? defaultMaxDuration
          : Duration(seconds: maxS),
      locationInterval: locS == null || locS <= 0
          ? defaultLocationInterval
          : Duration(seconds: locS),
      simulated: json['simulated'] == true,
    );
  }

  @override
  String toString() => 'LiveStreamGrant($streamId, simulated: $simulated)';
}

/// `pending|live|ended|expired|rejected` (contract §1).
enum LiveStreamStatus {
  pending,
  live,
  ended,
  expired,
  rejected;

  bool get isActive => this == pending || this == live;

  static LiveStreamStatus? fromWire(String? value) => values.asNameMap()[value];
}

/// `publisher_stopped|staff_stopped|max_duration|token_expired|error`.
enum LiveEndReasonWire {
  publisherStopped('publisher_stopped'),
  staffStopped('staff_stopped'),
  maxDuration('max_duration'),
  tokenExpired('token_expired'),
  error('error');

  const LiveEndReasonWire(this.wire);
  final String wire;

  static LiveEndReasonWire? fromWire(String? value) {
    for (final r in values) {
      if (r.wire == value) return r;
    }
    return null;
  }
}

/// `GET /api/v1/streams/{id}` and the `POST …/stop` summary.
class LiveStreamInfo {
  const LiveStreamInfo({
    required this.streamId,
    required this.status,
    this.startedAt,
    this.endedAt,
    this.endReason,
  });

  final String streamId;

  /// Null for a status this version does not know (treated as still active).
  final LiveStreamStatus? status;
  final DateTime? startedAt;
  final DateTime? endedAt;
  final LiveEndReasonWire? endReason;

  factory LiveStreamInfo.fromJson(Map<String, Object?> json) => LiveStreamInfo(
    streamId: (json['stream_id'] ?? json['id'] ?? '') as String,
    status: LiveStreamStatus.fromWire(json['status'] as String?),
    startedAt: DateTime.tryParse(json['started_at'] as String? ?? ''),
    endedAt: DateTime.tryParse(json['ended_at'] as String? ?? ''),
    endReason: LiveEndReasonWire.fromWire(json['end_reason'] as String?),
  );
}
