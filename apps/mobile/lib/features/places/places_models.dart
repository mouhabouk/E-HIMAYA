import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../core/http/models.dart';

/// A public map layer (`GET /api/v1/layers`): hospitals, pharmacies… or the Civil Protection
/// centres (`origin: units`).
class PlaceLayer {
  const PlaceLayer({
    required this.key,
    required this.names,
    required this.icon,
    required this.colour,
    this.source = '',
    this.licence = '',
    this.toVerify = false,
    this.count = 0,
    this.dataVersion = 0,
  });

  final String key;
  final Map<String, String> names;
  final String icon;
  final String colour;
  final String source;
  final String licence;

  /// First load from OpenStreetMap not yet checked by the Office: shown with "to be verified".
  final bool toVerify;
  final int count;
  final int dataVersion;

  String nameFor(String lang) {
    final n = names[lang];
    if (n != null && n.trim().isNotEmpty) return n;
    return names['ar'] ?? names.values.firstOrNull ?? key;
  }

  factory PlaceLayer.fromJson(Map<String, Object?> json) {
    final names = json['names'];
    return PlaceLayer(
      key: '${json['key']}',
      names: {
        if (names is Map)
          for (final e in names.entries)
            if (e.value is String) '${e.key}': e.value as String,
        if (names is! Map && json['name'] is String)
          'ar': json['name']! as String,
      },
      icon: (json['icon'] as String?) ?? 'pin',
      colour: (json['colour'] as String?) ?? '#37474F',
      source: (json['source'] as String?) ?? '',
      licence: (json['licence'] as String?) ?? '',
      toVerify: json['to_verify'] == true,
      count: (json['count'] as num?)?.toInt() ?? 0,
      dataVersion: (json['data_version'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, Object?> toJson() => {
    'key': key,
    'names': names,
    'icon': icon,
    'colour': colour,
    'source': source,
    'licence': licence,
    'to_verify': toVerify,
    'count': count,
    'data_version': dataVersion,
  };
}

/// A place of a layer, as the app keeps it offline. Staff-only columns never reach the app.
class Place {
  const Place({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    this.kind,
    this.phone,
    this.props = const {},
  });

  final String id;
  final String name;
  final double lat;
  final double lon;
  final String? kind;
  final String? phone;
  final Map<String, Object?> props;

  String? prop(String key) {
    final v = props[key];
    return v is String && v.trim().isNotEmpty ? v : null;
  }

  factory Place.fromJson(Map<String, Object?> json) {
    final props = json['props'];
    return Place(
      id: '${json['id']}',
      name: (json['name'] as String?) ?? '',
      lat: (json['lat']! as num).toDouble(),
      lon: (json['lon']! as num).toDouble(),
      kind: json['kind'] as String?,
      phone: json['phone'] as String?,
      props: {
        if (props is Map)
          for (final e in props.entries) '${e.key}': e.value,
      },
    );
  }

  Map<String, Object?> toJson() => {
    'id': id,
    'name': name,
    'lat': lat,
    'lon': lon,
    'kind': kind,
    'phone': phone,
    'props': props,
  };
}

/// Offline copy of one layer (`GET /api/v1/layers/{key}/package`).
class PlacePackage {
  const PlacePackage({
    required this.layer,
    required this.places,
    this.etag,
    this.lang,
    this.truncated = false,
  });

  final String layer;
  final List<Place> places;
  final String? etag;
  final String? lang;
  final bool truncated;

  factory PlacePackage.fromJson(Map<String, Object?> json, {String? etag}) {
    final items = json['items'];
    return PlacePackage(
      layer: '${json['layer']}',
      places: [
        if (items is List)
          for (final i in items)
            if (i is Map<String, Object?> && i['lat'] is num && i['lon'] is num)
              Place.fromJson(i),
      ],
      etag: etag ?? json['etag'] as String?,
      lang: json['lang'] as String?,
      truncated: json['truncated'] == true,
    );
  }

  Map<String, Object?> toJson() => {
    'layer': layer,
    'etag': etag,
    'lang': lang,
    'truncated': truncated,
    'items': [for (final p in places) p.toJson()],
  };
}

/// A place with its distance from the user.
class NearPlace {
  const NearPlace(this.place, this.distanceM);
  final Place place;
  final double distanceM;
}

/// Great-circle distance in metres (haversine; enough for "nearest" within Tunisia).
double distanceM(double lat1, double lon1, double lat2, double lon2) {
  const r = 6371000.0;
  double rad(double d) => d * math.pi / 180;
  final dLat = rad(lat2 - lat1);
  final dLon = rad(lon2 - lon1);
  final a =
      math.pow(math.sin(dLat / 2), 2) +
      math.cos(rad(lat1)) *
          math.cos(rad(lat2)) *
          math.pow(math.sin(dLon / 2), 2);
  return 2 * r * math.asin(math.min(1, math.sqrt(a)));
}

/// The [limit] places nearest to [from], computed on the phone (works offline).
List<NearPlace> nearest(List<Place> places, GeoPoint from, {int limit = 3}) {
  final all = [
    for (final p in places)
      NearPlace(p, distanceM(from.lat, from.lon, p.lat, p.lon)),
  ]..sort((a, b) => a.distanceM.compareTo(b.distanceM));
  return all.take(limit).toList();
}

/// "850 m" under one kilometre, then "12.4 km".
String formatDistance(double metres) => metres < 1000
    ? '${(metres / 10).round() * 10} m'
    : '${(metres / 1000).toStringAsFixed(metres < 10000 ? 1 : 0)} km';

/// Icons of the layers, matching the names the dashboard offers (`ICONS` of the API).
IconData layerIcon(String name) => switch (name) {
  'hospital' => Icons.local_hospital,
  'clinic' => Icons.medical_services,
  'pharmacy' => Icons.local_pharmacy,
  'police' => Icons.local_police,
  'guard' => Icons.shield,
  'civil_protection' => Icons.local_fire_department,
  'shelter' => Icons.night_shelter,
  'school' => Icons.school,
  'factory' => Icons.factory,
  'water' => Icons.water_drop,
  'fuel' => Icons.local_gas_station,
  _ => Icons.place,
};
