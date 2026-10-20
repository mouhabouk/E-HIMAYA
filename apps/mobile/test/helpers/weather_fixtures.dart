import 'phase5_fixtures.dart';

/// A `GET /api/v1/weather` answer (contract §1, shape in the phase-7 implementation notes).
/// Hours start at [from] (UTC), one per hour.
Map<String, Object?> weatherJson({
  DateTime? from,
  bool simulated = false,
  String fireDanger = 'high',
  String heavyRain = 'none',
  String laterRain = 'watch',
  List<Map<String, Object?>> alerts = const [],
  Object? attribution = const {
    'text': 'Weather data by Open-Meteo.com',
    'url': 'https://open-meteo.com/',
    'licence': 'CC BY 4.0',
  },
  int hours = 12,
}) {
  final start = from ?? DateTime.utc(2026, 10, 20, 10);
  return {
    'location': {'lat': 36.75, 'lon': 10.25},
    'updated_at': start.toIso8601String(),
    'current': {
      'time': start.toIso8601String(),
      'temperature_c': 24.4,
      'wind_speed_kmh': 18.2,
      'wind_gust_kmh': 35,
      'wind_direction_deg': 270,
      'relative_humidity_pct': 55,
      'precipitation_mm_h': 0,
      'precipitation_24h_mm': 2.1,
      'fire_danger': {'class': fireDanger, 'fwi': 23.5},
      'heavy_rain': heavyRain,
      'weather_code': 1,
    },
    'hourly': [
      for (var i = 1; i <= hours; i++)
        {
          'time': start.add(Duration(hours: i)).toIso8601String(),
          'temperature_c': 24 - i * 0.5,
          'wind_speed_kmh': 20,
          'precipitation_mm_h': i == 3 ? 4.5 : 0,
          'fire_danger': fireDanger,
          'heavy_rain': i == 3 ? laterRain : 'none',
          'weather_code': i == 3 ? 63 : 0,
        },
    ],
    'alerts': alerts,
    'attribution': attribution,
    'simulated': simulated,
  };
}

/// A weather alert as listed by the weather endpoint (same item as the active alerts).
Map<String, Object?> weatherAlertJson({
  String id = 'a1e70000-0000-4000-8000-0000000000aa',
  String severity = 'medium',
}) => alertJson(id: id, severity: severity);
