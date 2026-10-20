/// DTOs of the phase-8 citizen rewards endpoint (`GET /api/v1/me/rewards`, contract §3, §5).
///
/// The parser is tolerant: unknown fields and unknown enum values are ignored, so a newer
/// server never breaks the screen. [RewardsSummary.source] keeps the raw JSON for the offline
/// copy.
library;

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

int _int(Object? v) => v is num && v.isFinite ? v.toInt() : 0;

String? _str(Object? v) => v is String && v.isNotEmpty ? v : null;

/// Badge levels, in ascending order (thresholds are server settings).
enum BadgeLevel {
  bronze,
  silver,
  gold,
  ambassador;

  static BadgeLevel? fromWire(Object? value) => values.asNameMap()[value];
}

/// A badge of the citizen. The server lists confirmed badges only (silver and above wait for
/// a staff confirmation before they show).
class RewardBadge {
  const RewardBadge({required this.level, this.confirmedAt});

  final BadgeLevel level;
  final DateTime? confirmedAt;

  static RewardBadge? fromJson(Object? json) {
    if (json is! Map) return null;
    final level = BadgeLevel.fromWire(json['level']);
    if (level == null) return null;
    return RewardBadge(level: level, confirmedAt: _date(json['confirmed_at']));
  }
}

/// The next badge and how far away it is.
class NextBadge {
  const NextBadge({
    required this.level,
    required this.threshold,
    required this.missingPoints,
  });

  final BadgeLevel level;
  final int threshold;
  final int missingPoints;

  static NextBadge? fromJson(Object? json) {
    if (json is! Map) return null;
    final level = BadgeLevel.fromWire(json['level']);
    if (level == null) return null;
    return NextBadge(
      level: level,
      threshold: _int(json['threshold']),
      missingPoints: _int(json['missing_points']),
    );
  }
}

/// Why points were added or removed (ledger `reason`).
enum PointsReason {
  reportVerified('report_verified'),
  reportHelpedRescue('report_helped_rescue'),
  accurateCategory('accurate_category'),
  volunteerMission('volunteer_mission'),
  manual('manual'),
  revocation('revocation');

  const PointsReason(this.wire);
  final String wire;

  static PointsReason? fromWire(Object? value) {
    for (final r in values) {
      if (r.wire == value) return r;
    }
    return null;
  }
}

/// One ledger row of the citizen (newest first).
class PointsEntry {
  const PointsEntry({
    required this.id,
    required this.delta,
    required this.reasonWire,
    this.reportId,
    this.trackingCode,
    this.interventionId,
    this.multiplier,
    this.capped = false,
    this.createdAt,
  });

  final String id;
  final int delta;

  /// Raw `reason`; [reason] is null for a value this app version does not know.
  final String reasonWire;
  final String? reportId;
  final String? trackingCode;
  final String? interventionId;
  final double? multiplier;

  /// The daily cap reduced this row ([delta] may then be 0).
  final bool capped;
  final DateTime? createdAt;

  PointsReason? get reason => PointsReason.fromWire(reasonWire);

  static PointsEntry? fromJson(Object? json) {
    if (json is! Map) return null;
    final m = json['multiplier'];
    return PointsEntry(
      id: '${json['id'] ?? ''}',
      delta: _int(json['delta']),
      reasonWire: _str(json['reason']) ?? '',
      reportId: _str(json['report_id']),
      trackingCode: _str(json['tracking_code']),
      interventionId: _str(json['intervention_id']),
      multiplier: m is num && m.isFinite ? m.toDouble() : null,
      capped: json['capped'] == true,
      createdAt: _date(json['created_at']),
    );
  }
}

/// A certificate the citizen can download as PDF (`GET /api/v1/me/rewards/certificates/{id}`).
class RewardCertificate {
  const RewardCertificate({
    required this.id,
    required this.distinction,
    this.code,
    this.year,
    this.issuedAt,
  });

  final String id;

  /// A badge level (`gold`, `ambassador`) or a nomination kind (`vigilant_citizen`, …).
  final String distinction;

  /// Public verification code (shown on the PDF's QR).
  final String? code;
  final int? year;
  final DateTime? issuedAt;

  static RewardCertificate? fromJson(Object? json) {
    if (json is! Map) return null;
    final id = _str(json['id']);
    if (id == null) return null;
    return RewardCertificate(
      id: id,
      distinction:
          _str(json['distinction']) ?? _str(json['kind']) ?? 'certificate',
      code: _str(json['code']),
      year: (json['year'] as num?)?.toInt(),
      issuedAt: _date(json['issued_at']),
    );
  }
}

/// A page of `GET /api/v1/me/rewards/history`.
class PointsHistoryPage {
  const PointsHistoryPage(this.items, this.nextCursor);
  final List<PointsEntry> items;
  final String? nextCursor;

  factory PointsHistoryPage.fromJson(Map<String, Object?> json) =>
      PointsHistoryPage([
        for (final h in (json['items'] as List? ?? const []))
          ?PointsEntry.fromJson(h),
      ], _str(json['next_cursor']));
}

/// `GET /api/v1/me/rewards`. Anonymous identities get zeros with [anonymous] set.
class RewardsSummary {
  const RewardsSummary({
    required this.balance,
    required this.badges,
    required this.history,
    required this.certificates,
    required this.paused,
    required this.source,
    this.anonymous = false,
    this.currentLevel,
    this.nextBadge,
    this.pendingPoints = 0,
    this.dailyCap,
    this.historyNextCursor,
  });

  final bool anonymous;
  final int balance;

  /// Confirmed badges.
  final List<RewardBadge> badges;
  final BadgeLevel? currentLevel;
  final NextBadge? nextBadge;

  /// Latest ledger rows, newest first; [historyNextCursor] continues it.
  final List<PointsEntry> history;
  final String? historyNextCursor;
  final List<RewardCertificate> certificates;

  /// Operational level `disaster`: new points are queued, not added.
  final bool paused;

  /// Points queued while [paused].
  final int pendingPoints;

  /// Most points a citizen can earn in one day (server setting).
  final int? dailyCap;

  /// The JSON this summary was read from (kept for the offline copy).
  final Map<String, Object?> source;

  /// Current badge: the server's `current_badge`, else the highest confirmed badge.
  BadgeLevel? get currentBadge {
    if (currentLevel != null) return currentLevel;
    BadgeLevel? best;
    for (final b in badges) {
      if (best == null || b.level.index > best.index) best = b.level;
    }
    return best;
  }

  /// Progress towards [nextBadge] in 0..1 (balance over its threshold).
  double? get progress {
    final next = nextBadge;
    if (next == null || next.threshold <= 0) return null;
    final done = (next.threshold - next.missingPoints).clamp(0, next.threshold);
    return done / next.threshold;
  }

  /// Points earned by one report (all its ledger rows, revocations included), or null when
  /// [history] has none.
  int? pointsForReport({String? trackingCode, String? reportId}) {
    int? total;
    for (final e in history) {
      final match =
          (trackingCode != null && e.trackingCode == trackingCode) ||
          (reportId != null && e.reportId == reportId);
      if (match) total = (total ?? 0) + e.delta;
    }
    return total;
  }

  factory RewardsSummary.fromJson(Map<String, Object?> json) => RewardsSummary(
    anonymous: json['anonymous'] == true,
    balance: _int(json['balance']),
    badges: [
      for (final b in (json['badges'] as List? ?? const []))
        ?RewardBadge.fromJson(b),
    ],
    currentLevel: BadgeLevel.fromWire(json['current_badge']),
    nextBadge: NextBadge.fromJson(json['next_badge']),
    history: [
      for (final h in (json['history'] as List? ?? const []))
        ?PointsEntry.fromJson(h),
    ],
    historyNextCursor: _str(json['history_next_cursor']),
    certificates: [
      for (final c in (json['certificates'] as List? ?? const []))
        ?RewardCertificate.fromJson(c),
    ],
    paused: json['paused'] == true,
    pendingPoints: _int(json['pending_points']),
    dailyCap: (json['daily_cap'] as num?)?.toInt(),
    source: json,
  );
}
