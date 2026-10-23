import 'package:flutter/material.dart';

/// One language of an item of the emergency guide: when to call 198 at once, the numbered steps
/// and what not to do.
class GuideText {
  const GuideText({
    required this.title,
    this.call = const [],
    this.steps = const [],
    this.dont = const [],
  });

  final String title;
  final List<String> call;
  final List<String> steps;
  final List<String> dont;

  bool get isEmpty => title.trim().isEmpty && steps.isEmpty;

  static List<String> _lines(Object? v) => [
    if (v is List)
      for (final s in v)
        if (s is String && s.trim().isNotEmpty) s,
  ];

  factory GuideText.fromJson(Object? json) {
    final m = json is Map ? json : const {};
    return GuideText(
      title: (m['title'] as String?) ?? '',
      call: _lines(m['call']),
      steps: _lines(m['steps']),
      dont: _lines(m['dont']),
    );
  }

  Map<String, Object?> toJson() => {
    'title': title,
    'call': call,
    'steps': steps,
    'dont': dont,
  };
}

/// An item of a topic (for example "Clothes on fire" under fires).
class GuideItem {
  const GuideItem({
    required this.id,
    required this.content,
    this.call198 = false,
    this.validated = false,
  });

  final String id;
  final Map<String, GuideText> content;

  /// Shows the "Call 198" button on the item.
  final bool call198;

  /// False until the Office's medical staff validates the text: the app shows the amber [SIM]
  /// banner.
  final bool validated;

  /// The text in [lang], or Arabic when that language is missing.
  GuideText textFor(String lang) {
    final t = content[lang];
    if (t != null && !t.isEmpty) return t;
    return content['ar'] ??
        content.values.firstOrNull ??
        const GuideText(title: '');
  }

  factory GuideItem.fromJson(Map<String, Object?> json) {
    final content = json['content'];
    return GuideItem(
      id: '${json['id']}',
      content: {
        if (content is Map)
          for (final e in content.entries)
            '${e.key}': GuideText.fromJson(e.value),
      },
      call198: json['call_198'] == true,
      validated: json['validated'] == true,
    );
  }

  Map<String, Object?> toJson() => {
    'id': id,
    'content': {for (final e in content.entries) e.key: e.value.toJson()},
    'call_198': call198,
    'validated': validated,
  };
}

/// A topic of the hub (fires, fractures, first aid, breathing problems…), in the order the
/// content editors chose. Hidden topics and items never reach the app.
class GuideTopic {
  const GuideTopic({
    required this.id,
    required this.key,
    required this.title,
    required this.icon,
    required this.colour,
    required this.items,
  });

  final String id;
  final String key;
  final Map<String, String> title;
  final String icon;
  final String colour;
  final List<GuideItem> items;

  String titleFor(String lang) {
    final t = title[lang];
    if (t != null && t.trim().isNotEmpty) return t;
    return title['ar'] ?? title.values.firstOrNull ?? key;
  }

  /// Some item still awaits medical validation.
  bool get hasSimulated => items.any((i) => !i.validated);

  factory GuideTopic.fromJson(Map<String, Object?> json) {
    final title = json['title'];
    final items = json['items'];
    return GuideTopic(
      id: '${json['id']}',
      key: (json['key'] as String?) ?? '',
      title: {
        if (title is Map)
          for (final e in title.entries)
            if (e.value is String) '${e.key}': e.value as String,
      },
      icon: (json['icon'] as String?) ?? 'pin',
      colour: (json['colour'] as String?) ?? '#37474F',
      items: [
        if (items is List)
          for (final i in items)
            if (i is Map<String, Object?>) GuideItem.fromJson(i),
      ],
    );
  }

  Map<String, Object?> toJson() => {
    'id': id,
    'key': key,
    'title': title,
    'icon': icon,
    'colour': colour,
    'items': [for (final i in items) i.toJson()],
  };
}

/// The published guide (`GET /api/v1/emergency-guide`), or the copy bundled with the app
/// (revision 0).
class EmergencyGuide {
  const EmergencyGuide(this.revision, this.topics);

  final int revision;
  final List<GuideTopic> topics;

  factory EmergencyGuide.fromJson(Object? json) {
    final m = json is Map ? json : const {};
    final topics = m['topics'];
    return EmergencyGuide((m['revision'] as num?)?.toInt() ?? 0, [
      if (topics is List)
        for (final t in topics)
          if (t is Map<String, Object?>) GuideTopic.fromJson(t),
    ]);
  }

  Map<String, Object?> toJson() => {
    'revision': revision,
    'topics': [for (final t in topics) t.toJson()],
  };

  GuideTopic? topic(String key) =>
      topics.where((t) => t.key == key).firstOrNull;
}

/// Icons of the topics, matching the names the dashboard offers (`GUIDE_ICONS` of the API).
IconData guideIcon(String name) => switch (name) {
  'fire' => Icons.local_fire_department,
  'bone' => Icons.accessibility_new,
  'first_aid' => Icons.medical_services,
  'lungs' => Icons.air,
  'burn' => Icons.whatshot,
  'drop' => Icons.water_drop,
  'heart' => Icons.favorite,
  'water' => Icons.pool,
  'electric' => Icons.bolt,
  'poison' => Icons.dangerous,
  _ => Icons.place,
};

/// `#RRGGBB` from the palette, or a neutral grey when unreadable.
Color guideColour(String hex) {
  final v = int.tryParse(hex.replaceFirst('#', ''), radix: 16);
  return v == null ? const Color(0xFF37474F) : Color(0xFF000000 | v);
}
