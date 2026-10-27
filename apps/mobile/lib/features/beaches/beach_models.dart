import '../../core/http/models.dart';
import '../../core/ui/tokens.dart';
import '../places/places_models.dart' show distanceM;

/// Phase L1b (docs/phase-l/design-l1b-coastal.md): the drowning risk of the beaches, as the public
/// API gives it. The colour supports the bather's own decision; it is never an official ban.
enum BeachLevel { green, yellow, red, unknown }

BeachLevel beachLevelOf(Object? wire) => switch (wire) {
  'green' => BeachLevel.green,
  'yellow' => BeachLevel.yellow,
  'red' => BeachLevel.red,
  _ => BeachLevel.unknown,
};

/// Design tokens of the three levels: red, amber (glyph in ink) and green; slate when unknown.
Tone toneOf(BeachLevel level) => switch (level) {
  BeachLevel.red => Tone.red,
  BeachLevel.yellow => Tone.amber,
  BeachLevel.green => Tone.green,
  BeachLevel.unknown => Tone.slate,
};

double? _num(Object? v) => v is num ? v.toDouble() : null;

/// One reason of the score (`waves`, `onshore_wind`, `current`, `season`, `crowd`, `unguarded`,
/// `past_drownings`) and the points it gave.
class RiskFactor {
  const RiskFactor(this.code, this.points, this.value);

  final String code;
  final int points;
  final Object? value;

  factory RiskFactor.fromJson(Map<String, Object?> json) => RiskFactor(
    '${json['code']}',
    (json['points'] as num?)?.toInt() ?? 0,
    json['value'],
  );
}

List<RiskFactor> _factors(Object? raw) => [
  if (raw is List)
    for (final f in raw)
      if (f is Map<String, Object?>) RiskFactor.fromJson(f),
];

class BeachRisk {
  const BeachRisk({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    this.gouvernoratCode,
    this.level = BeachLevel.unknown,
    this.score,
    this.factors = const [],
    this.waveHeightM,
    this.seaTempC,
    this.currentKmh,
    this.classification,
    this.guarded,
  });

  final String id;
  final String name;
  final double lat;
  final double lon;
  final int? gouvernoratCode;
  final BeachLevel level;
  final int? score;
  final List<RiskFactor> factors;
  final double? waveHeightM;
  final double? seaTempC;
  final double? currentKmh;
  final String? classification;
  final bool? guarded;

  GeoPoint get point => GeoPoint(lat: lat, lon: lon);

  factory BeachRisk.fromJson(Map<String, Object?> json) => BeachRisk(
    id: '${json['id']}',
    name: (json['name'] as String?) ?? '',
    lat: (json['lat']! as num).toDouble(),
    lon: (json['lon']! as num).toDouble(),
    gouvernoratCode: (json['gouvernorat_code'] as num?)?.toInt(),
    level: beachLevelOf(json['level']),
    score: (json['score'] as num?)?.toInt(),
    factors: _factors(json['factors']),
    waveHeightM: _num(json['wave_height_m']),
    seaTempC: _num(json['sea_temp_c']),
    currentKmh: _num(json['current_kmh']),
    classification: json['classification'] as String?,
    guarded: json['guarded'] as bool?,
  );
}

/// Where the data comes from: Open-Meteo (CC BY 4.0) or the [SIM] simulator.
String attributionText(Object? raw) => [
  if (raw is List)
    for (final a in raw)
      if (a is String)
        a
      else if (a is Map)
        [a['text'], a['licence']].whereType<String>().join(' · '),
].join('\n');

class BeachesReport {
  const BeachesReport({
    required this.day,
    required this.items,
    this.simulated = false,
    this.attribution = '',
    this.warnRadiusM = 1000,
  });

  final String day;
  final List<BeachRisk> items;
  final bool simulated;
  final String attribution;

  /// The phone warns within this distance of a yellow or red beach.
  final int warnRadiusM;

  factory BeachesReport.fromJson(Map<String, Object?> json) => BeachesReport(
    day: '${json['day']}',
    simulated: json['simulated'] == true,
    attribution: attributionText(json['attribution']),
    warnRadiusM: (json['warn_radius_m'] as num?)?.toInt() ?? 1000,
    items: [
      if (json['items'] case final List<Object?> items)
        for (final i in items)
          if (i is Map<String, Object?> && i['lat'] is num && i['lon'] is num)
            BeachRisk.fromJson(i),
    ],
  );
}

class DayRisk {
  const DayRisk({
    required this.day,
    required this.level,
    required this.score,
    this.factors = const [],
    this.waveHeightM,
    this.seaTempC,
  });

  final String day;
  final BeachLevel level;
  final int score;
  final List<RiskFactor> factors;
  final double? waveHeightM;
  final double? seaTempC;

  factory DayRisk.fromJson(Map<String, Object?> json) => DayRisk(
    day: '${json['day']}',
    level: beachLevelOf(json['level']),
    score: (json['score'] as num?)?.toInt() ?? 0,
    factors: _factors(json['factors']),
    waveHeightM: _num(json['wave_height_m']),
    seaTempC: _num(json['sea_temp_c']),
  );
}

class BeachDetail {
  const BeachDetail({
    required this.beach,
    required this.days,
    this.card = const {},
    this.sources = const {},
    this.simulated = false,
    this.attribution = '',
  });

  final BeachRisk beach;
  final List<DayRisk> days;

  /// The beach card fields the public may see (classification, blue flag, lifeguards…).
  final Map<String, Object?> card;
  final Map<String, String> sources;
  final bool simulated;
  final String attribution;

  factory BeachDetail.fromJson(Map<String, Object?> json) {
    final sources = json['sources'];
    return BeachDetail(
      beach: BeachRisk.fromJson(json['beach']! as Map<String, Object?>),
      days: [
        if (json['days'] case final List<Object?> days)
          for (final d in days)
            if (d is Map<String, Object?>) DayRisk.fromJson(d),
      ],
      card: {
        if (json['card'] case final Map<Object?, Object?> card)
          for (final e in card.entries)
            if (e.value != null && '${e.value}'.trim().isNotEmpty)
              '${e.key}': e.value,
      },
      sources: {
        if (sources is Map)
          for (final e in sources.entries)
            if (e.value case final Map<Object?, Object?> s)
              '${e.key}': [
                s['source'],
                s['date'],
              ].whereType<String>().join(', '),
      },
      simulated: json['simulated'] == true,
      attribution: attributionText(json['attribution']),
    );
  }
}

/// A beach with its distance from the user.
class NearBeach {
  const NearBeach(this.beach, this.distanceM);
  final BeachRisk beach;
  final double distanceM;
}

/// Every beach, nearest first (alphabetical while the position is unknown).
List<NearBeach> byDistance(List<BeachRisk> beaches, GeoPoint? here) {
  final all = [
    for (final b in beaches)
      NearBeach(
        b,
        here == null
            ? double.infinity
            : distanceM(here.lat, here.lon, b.lat, b.lon),
      ),
  ];
  all.sort(
    (a, b) => here == null
        ? a.beach.name.compareTo(b.beach.name)
        : a.distanceM.compareTo(b.distanceM),
  );
  return all;
}

/// The nearest yellow or red beach within [radiusM] of the user, computed on the phone: the
/// position never leaves it. Null when none (or no position).
NearBeach? dangerNear(List<BeachRisk> beaches, GeoPoint? here, int radiusM) {
  if (here == null) return null;
  for (final n in byDistance(beaches, here)) {
    if (n.distanceM > radiusM) return null;
    if (n.beach.level == BeachLevel.red || n.beach.level == BeachLevel.yellow) {
      return n;
    }
  }
  return null;
}

/// A yes/no column of an imported file ("True", "oui", "نعم"…), or null when it is something else.
bool? yesNo(Object? value) {
  if (value is bool) return value;
  final v = '$value'.trim().toLowerCase();
  if (const {'true', 'yes', 'oui', '1', 'نعم'}.contains(v)) return true;
  if (const {'false', 'no', 'non', '0', 'لا'}.contains(v)) return false;
  return null;
}
