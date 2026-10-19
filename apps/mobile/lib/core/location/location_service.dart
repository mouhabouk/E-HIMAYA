import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../http/models.dart';
import '../logging/log.dart';

final _log = logger('location');

enum LocationAvailability { granted, denied, deniedForever, serviceDisabled }

abstract class LocationService {
  Future<LocationAvailability> ensurePermission();

  /// Fresh fix, or null after [timeout].
  Future<GeoPoint?> current({Duration timeout = const Duration(seconds: 8)});

  Future<GeoPoint?> lastKnown();

  /// Fresh fix when it arrives within [timeout], otherwise the last known position (SOS must
  /// not wait for a slow GPS).
  Future<GeoPoint?> bestEffort({
    Duration timeout = const Duration(seconds: 5),
  }) async {
    if (await ensurePermission() != LocationAvailability.granted) return null;
    final last = lastKnown();
    final fresh = await current(timeout: timeout);
    return fresh ?? await last;
  }
}

class GeolocatorLocationService extends LocationService {
  @override
  Future<LocationAvailability> ensurePermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return LocationAvailability.serviceDisabled;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    return switch (permission) {
      LocationPermission.always ||
      LocationPermission.whileInUse => LocationAvailability.granted,
      LocationPermission.deniedForever => LocationAvailability.deniedForever,
      _ => LocationAvailability.denied,
    };
  }

  @override
  Future<GeoPoint?> current({
    Duration timeout = const Duration(seconds: 8),
  }) async {
    try {
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: timeout,
        ),
      );
      return _toPoint(pos);
    } on TimeoutException {
      return null;
    } on Exception catch (e) {
      _log.info('no fresh fix: ${e.runtimeType}');
      return null;
    }
  }

  @override
  Future<GeoPoint?> lastKnown() async {
    try {
      final pos = await Geolocator.getLastKnownPosition();
      return pos == null ? null : _toPoint(pos);
    } on Exception {
      return null;
    }
  }

  static GeoPoint _toPoint(Position p) =>
      GeoPoint(lat: p.latitude, lon: p.longitude, accuracyM: p.accuracy);
}

final locationServiceProvider = Provider<LocationService>(
  (ref) => GeolocatorLocationService(),
);
