/// DTOs of phase-5 notifications, alerts and safety tips (contract §7, §8).
library;

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

/// A text in the three app languages; empty French or English falls back to Arabic.
class Localized {
  const Localized(this.values);

  final Map<String, String> values;

  String of(String lang) {
    final v = values[lang];
    return v == null || v.trim().isEmpty ? (values['ar'] ?? '') : v;
  }

  factory Localized.fromJson(Object? json) => Localized({
    if (json is Map)
      for (final e in json.entries)
        if (e.value is String) '${e.key}': e.value as String,
  });
}

enum AlertSeverity {
  high,
  medium,
  low;

  static AlertSeverity fromWire(String? value) =>
      values.asNameMap()[value] ?? low;
}

/// Alert hazards (FR-C-18).
enum AlertHazard {
  heavyRain('heavy_rain'),
  flood('flood'),
  storm('storm'),
  wind('wind'),
  heatWave('heat_wave'),
  coldWave('cold_wave'),
  sea('sea'),
  forestFire('forest_fire'),
  chemical('chemical'),
  other('other');

  const AlertHazard(this.wire);
  final String wire;

  static AlertHazard fromWire(String? value) {
    for (final h in values) {
      if (h.wire == value) return h;
    }
    return other;
  }
}

enum NotificationTopic {
  activity,
  awareness,
  training,
  worldDay('world_day'),
  other;

  const NotificationTopic([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static NotificationTopic? fromWire(String? value) {
    for (final t in values) {
      if (t.wire == value) return t;
    }
    return null;
  }
}

/// `GET /api/v1/alerts/active` item.
class ActiveAlert {
  const ActiveAlert({
    required this.id,
    required this.severity,
    required this.category,
    required this.hazard,
    required this.title,
    required this.body,
    required this.gouvernoratCodes,
    required this.hasPolygon,
    required this.publishedAt,
    required this.expiresAt,
    this.source = const {},
  });

  final String id;
  final AlertSeverity severity;
  final String category;
  final AlertHazard hazard;
  final Localized title;
  final Localized body;

  /// Empty with no polygon: the whole country.
  final List<int> gouvernoratCodes;
  final bool hasPolygon;
  final DateTime publishedAt;
  final DateTime expiresAt;

  /// The JSON it was read from (kept for the offline copy).
  final Map<String, Object?> source;

  bool get isNational => gouvernoratCodes.isEmpty && !hasPolygon;

  bool activeAt(DateTime now) => expiresAt.isAfter(now);

  factory ActiveAlert.fromJson(Map<String, Object?> json) {
    final area = json['area'];
    return ActiveAlert(
      id: json['id']! as String,
      severity: AlertSeverity.fromWire(json['severity'] as String?),
      category: json['category'] as String? ?? 'hazard',
      hazard: AlertHazard.fromWire(json['hazard'] as String?),
      title: Localized.fromJson(json['title']),
      body: Localized.fromJson(json['body']),
      gouvernoratCodes: [
        if (area is Map)
          for (final c in (area['gouvernorat_codes'] as List? ?? const []))
            if (c is num) c.toInt(),
      ],
      hasPolygon: area is Map && area['polygon'] != null,
      publishedAt: _date(json['published_at']) ?? DateTime(1970),
      expiresAt: _date(json['expires_at']) ?? DateTime(1970),
      source: json,
    );
  }
}

/// `GET /api/v1/notifications` item.
class InboxItem {
  const InboxItem({
    required this.id,
    required this.isAlert,
    required this.title,
    required this.body,
    required this.publishedAt,
    required this.active,
    this.topic,
    this.severity,
    this.expiresAt,
  });

  final String id;
  final bool isAlert;
  final NotificationTopic? topic;
  final AlertSeverity? severity;
  final Localized title;
  final Localized body;
  final DateTime publishedAt;
  final DateTime? expiresAt;

  /// An alert still in force (published and not expired).
  final bool active;

  factory InboxItem.fromJson(Map<String, Object?> json) => InboxItem(
    id: json['id']! as String,
    isAlert: json['kind'] == 'alert',
    topic: NotificationTopic.fromWire(json['topic'] as String?),
    severity: json['severity'] == null
        ? null
        : AlertSeverity.fromWire(json['severity'] as String?),
    title: Localized.fromJson(json['title']),
    body: Localized.fromJson(json['body']),
    publishedAt: _date(json['published_at']) ?? DateTime(1970),
    expiresAt: _date(json['expires_at']),
    active: json['active'] == true,
  );
}

class InboxPage {
  const InboxPage(this.items, this.nextCursor);
  final List<InboxItem> items;
  final String? nextCursor;
}

/// Safety-tip hazards (FR-A-062).
enum TipHazard {
  fire,
  flood,
  trafficAccident('traffic_accident'),
  medical,
  drowning,
  landslide,
  chemicalLeak('chemical_leak'),
  heatWave('heat_wave'),
  storm,
  earthquake,
  other;

  const TipHazard([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static TipHazard fromWire(String? value) {
    for (final h in values) {
      if (h.wire == value) return h;
    }
    return other;
  }
}

class TipText {
  const TipText({
    required this.title,
    required this.doItems,
    required this.dontItems,
  });

  final String title;
  final List<String> doItems;
  final List<String> dontItems;

  bool get isEmpty =>
      title.trim().isEmpty && doItems.isEmpty && dontItems.isEmpty;

  factory TipText.fromJson(Object? json) {
    List<String> list(Object? v) => [
      for (final s in (v is List ? v : const []))
        if (s is String && s.trim().isNotEmpty) s,
    ];
    return json is Map
        ? TipText(
            title: json['title'] as String? ?? '',
            doItems: list(json['do']),
            dontItems: list(json['dont']),
          )
        : const TipText(title: '', doItems: [], dontItems: []);
  }
}

class SafetyTip {
  const SafetyTip({
    required this.hazard,
    required this.position,
    required this.content,
    this.id,
  });

  final String? id;
  final TipHazard hazard;
  final int position;
  final Map<String, TipText> content;

  /// The text in [lang], or Arabic when that language is missing.
  TipText textFor(String lang) {
    final t = content[lang];
    return t == null || t.isEmpty ? (content['ar'] ?? content.values.first) : t;
  }

  factory SafetyTip.fromJson(Map<String, Object?> json) {
    final content = json['content'];
    return SafetyTip(
      id: json['id'] as String?,
      hazard: TipHazard.fromWire(json['hazard'] as String?),
      position: (json['position'] as num?)?.toInt() ?? 0,
      content: {
        if (content is Map)
          for (final e in content.entries)
            '${e.key}': TipText.fromJson(e.value),
      },
    );
  }
}

/// The published tips. Accepts the API shape `{"revision", "items"}` and the bundled seed (a
/// plain list, revision 0).
class SafetyTips {
  const SafetyTips(this.revision, this.items);

  final int revision;
  final List<SafetyTip> items;

  factory SafetyTips.fromJson(Object? json) {
    final rawItems = json is Map ? json['items'] : json;
    final revision = json is Map ? (json['revision'] as num?)?.toInt() ?? 0 : 0;
    final items = [
      for (final t in (rawItems is List ? rawItems : const []))
        if (t is Map<String, Object?> && t['content'] is Map)
          SafetyTip.fromJson(t),
    ];
    // Stable order: position, then hazard (as the server orders them).
    final indexed = items.indexed.toList()
      ..sort((a, b) {
        final p = a.$2.position.compareTo(b.$2.position);
        return p != 0 ? p : a.$1.compareTo(b.$1);
      });
    return SafetyTips(revision, [for (final e in indexed) e.$2]);
  }
}
