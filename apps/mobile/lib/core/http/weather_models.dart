/// DTOs of the phase-7 public weather endpoint (`GET /api/v1/weather`, contract §1, §5).
///
/// The parser is tolerant: the documented field names are read first, then a few aliases
/// (see docs/api/phase-7-contract.md, "Implementation notes"), and unknown fields are ignored.
library;

import 'models.dart';
import 'notify_models.dart';

DateTime? _date(Object? v) => v is String ? DateTime.tryParse(v) : null;

double? _num(Map<String, Object?> json, List<String> keys) {
  for (final k in keys) {
    final v = json[k];
    if (v is num && v.isFinite) return v.toDouble();
  }
  return null;
}

/// Fire danger class of the Canadian FWI system (computed by the server).
enum FireDanger {
  low,
  moderate,
  high,
  veryHigh('very_high'),
  extreme;

  const FireDanger([this._wire]);
  final String? _wire;
  String get wire => _wire ?? name;

  static FireDanger? fromWire(Object? value) {
    final v = value is Map ? (value['class'] ?? value['level']) : value;
    for (final d in values) {
      if (d.wire == v) return d;
    }
    return null;
  }
}

/// Heavy-rain level derived from mm/h and mm/24 h.
enum RainLevel {
  none,
  watch,
  warning;

  static RainLevel? fromWire(Object? value) {
    final v = value is Map ? value['level'] : value;
    return values.asNameMap()[v];
  }
}

/// Values at one hour (or "now").
class WeatherHour {
  const WeatherHour({
    required this.time,
    this.temperatureC,
    this.windKmh,
    this.gustKmh,
    this.windDirectionDeg,
    this.humidityPct,
    this.precipitationMmH,
    this.precipitation24hMm,
    this.fireDanger,
    this.rainLevel,
    this.weatherCode,
  });

  final DateTime time;
  final double? temperatureC;
  final double? windKmh;
  final double? gustKmh;
  final double? windDirectionDeg;
  final double? humidityPct;
  final double? precipitationMmH;
  final double? precipitation24hMm;
  final FireDanger? fireDanger;
  final RainLevel? rainLevel;

  /// WMO weather code (Open-Meteo), when the server forwards it.
  final int? weatherCode;

  static WeatherHour? fromJson(Object? raw, {DateTime? fallbackTime}) {
    if (raw is! Map<String, Object?>) return null;
    final time = _date(raw['time']) ?? fallbackTime;
    if (time == null) return null;
    return WeatherHour(
      time: time,
      temperatureC: _num(raw, const ['temperature_c', 'temperature']),
      windKmh: _num(raw, const ['wind_speed_kmh', 'wind_kmh']),
      gustKmh: _num(raw, const ['wind_gust_kmh', 'wind_gusts_kmh']),
      windDirectionDeg: _num(raw, const ['wind_direction_deg', 'wind_dir_deg']),
      humidityPct: _num(raw, const ['relative_humidity_pct', 'humidity_pct']),
      precipitationMmH: _num(raw, const [
        'precipitation_mm_h',
        'precipitation_mm',
        'rain_1h_mm',
      ]),
      precipitation24hMm: _num(raw, const [
        'precipitation_24h_mm',
        'rain_24h_mm',
      ]),
      fireDanger: FireDanger.fromWire(raw['fire_danger']),
      rainLevel: RainLevel.fromWire(raw['heavy_rain'] ?? raw['rain_level']),
      weatherCode: (raw['weather_code'] as num?)?.toInt(),
    );
  }
}

/// Data attribution shown under the card (Open-Meteo data is CC BY 4.0).
class WeatherAttribution {
  const WeatherAttribution({required this.text, this.url});

  static const openMeteo = WeatherAttribution(
    text: 'Open-Meteo.com (CC BY 4.0)',
    url: 'https://open-meteo.com/',
  );

  final String text;
  final String? url;

  static WeatherAttribution fromJson(Object? raw) {
    if (raw is String && raw.trim().isNotEmpty) {
      return WeatherAttribution(text: raw.trim());
    }
    if (raw is Map) {
      final text = raw['text'];
      if (text is String && text.trim().isNotEmpty) {
        final licence = raw['licence'] ?? raw['license'];
        final url = raw['url'];
        return WeatherAttribution(
          text: licence is String && !text.contains(licence)
              ? '${text.trim()} ($licence)'
              : text.trim(),
          url: url is String && url.startsWith('https://') ? url : null,
        );
      }
    }
    return openMeteo;
  }
}

/// `GET /api/v1/weather` answer.
class WeatherReport {
  const WeatherReport({
    required this.current,
    required this.hourly,
    required this.alerts,
    required this.attribution,
    required this.simulated,
    this.updatedAt,
    this.point,
    this.source = const {},
  });

  final WeatherHour current;
  final List<WeatherHour> hourly;

  /// Active weather alerts covering the point (phase-5 alert items).
  final List<ActiveAlert> alerts;
  final WeatherAttribution attribution;
  final bool simulated;

  /// When the server produced these values.
  final DateTime? updatedAt;

  /// The grid point the values belong to.
  final GeoPoint? point;

  /// The JSON it was read from (kept for the offline copy).
  final Map<String, Object?> source;

  /// Hours from now on (the current hour excluded), at most [count].
  List<WeatherHour> nextHours(DateTime now, {int count = 12}) => [
    for (final h in hourly)
      if (h.time.isAfter(now)) h,
  ].take(count).toList();

  /// Alerts still in force at [now], most severe first.
  List<ActiveAlert> activeAlerts(DateTime now) {
    final list = [
      for (final a in alerts)
        if (a.activeAt(now)) a,
    ];
    list.sort((a, b) => a.severity.index.compareTo(b.severity.index));
    return list;
  }

  /// Highest fire danger now and over the next hours shown.
  FireDanger? maxFireDanger(DateTime now) =>
      _max([current.fireDanger, for (final h in nextHours(now)) h.fireDanger]);

  /// Highest heavy-rain level now and over the next hours shown.
  RainLevel? maxRainLevel(DateTime now) =>
      _max([current.rainLevel, for (final h in nextHours(now)) h.rainLevel]);

  static T? _max<T extends Enum>(List<T?> items) {
    T? best;
    for (final i in items) {
      if (i != null && (best == null || i.index > best.index)) best = i;
    }
    return best;
  }

  static WeatherReport? fromJson(Object? raw) {
    if (raw is! Map<String, Object?>) return null;
    final updatedAt =
        _date(raw['updated_at']) ??
        _date(raw['generated_at']) ??
        _date(raw['observed_at']);
    final current = WeatherHour.fromJson(
      raw['current'],
      fallbackTime: updatedAt,
    );
    if (current == null) return null;
    final hourly = [
      for (final h in (raw['hourly'] is List ? raw['hourly']! as List : []))
        ?WeatherHour.fromJson(h),
    ]..sort((a, b) => a.time.compareTo(b.time));
    final alerts = <ActiveAlert>[];
    for (final a in (raw['alerts'] is List ? raw['alerts']! as List : [])) {
      if (a is! Map<String, Object?> || a['id'] is! String) continue;
      try {
        alerts.add(ActiveAlert.fromJson(a));
      } on TypeError {
        // A malformed alert never hides the weather itself.
      }
    }
    return WeatherReport(
      current: current,
      hourly: hourly,
      alerts: alerts,
      attribution: WeatherAttribution.fromJson(raw['attribution']),
      simulated: raw['simulated'] == true,
      updatedAt: updatedAt,
      point: GeoPoint.fromJson(raw['location']),
      source: raw,
    );
  }
}
