import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
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

  /// A position without ever showing the permission prompt (background uses such as alert
  /// targeting): null unless location was already granted.
  Future<GeoPoint?> withoutPrompt() => lastKnown();

  /// Whether location works now, without any prompt (status strip of the home screen,
  /// addition 4).
  Future<LocationAvailability> status() async => LocationAvailability.granted;

  /// Opens the system page that turns location on (service off) or the app's settings
  /// (permission refused for good).
  Future<bool> openSettings() async => false;

  /// Position updates for the volunteer's readiness, in the foreground only and without a
  /// permission prompt. Battery: balanced (cell/Wi-Fi) accuracy and a 100 m distance filter
  /// ([lowPower]: low-power accuracy, 250 m), so a stationary phone produces no updates and the
  /// GPS chip stays off. Empty when location is not granted. Cancel the subscription to stop.
  Stream<GeoPoint> watch({bool lowPower = false}) => const Stream.empty();

  /// Phase B2: precise updates while a live location share or a safety check runs, kept going in
  /// a pocket by a foreground service with its visible notification ([title], [text]; Android).
  /// Started from the app only; no background location permission. Cancel to stop.
  Stream<GeoPoint> follow({required String title, required String text}) =>
      watch();
}

class GeolocatorLocationService extends LocationService {
  @override
  Future<LocationAvailability> status() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        return LocationAvailability.serviceDisabled;
      }
      return switch (await Geolocator.checkPermission()) {
        LocationPermission.always ||
        LocationPermission.whileInUse => LocationAvailability.granted,
        LocationPermission.deniedForever => LocationAvailability.deniedForever,
        _ => LocationAvailability.denied,
      };
    } on Exception {
      return LocationAvailability.denied;
    }
  }

  @override
  Future<bool> openSettings() async {
    try {
      final available = await status();
      return switch (available) {
        LocationAvailability.serviceDisabled =>
          await Geolocator.openLocationSettings(),
        LocationAvailability.deniedForever =>
          await Geolocator.openAppSettings(),
        LocationAvailability.denied =>
          await ensurePermission() == LocationAvailability.granted,
        LocationAvailability.granted => true,
      };
    } on Exception {
      return false;
    }
  }

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

  /// A last known position younger than this is good enough for coarse uses (alert targeting
  /// is rounded to about 1 km by the server) and costs no radio time.
  static const coarseMaxAge = Duration(minutes: 10);

  Future<bool> _grantedWithoutPrompt() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return false;
      final permission = await Geolocator.checkPermission();
      return permission == LocationPermission.always ||
          permission == LocationPermission.whileInUse;
    } on Exception {
      return false;
    }
  }

  @override
  Future<GeoPoint?> withoutPrompt() async {
    if (!await _grantedWithoutPrompt()) return null;
    try {
      final last = await Geolocator.getLastKnownPosition();
      if (last != null &&
          DateTime.now().difference(last.timestamp) < coarseMaxAge) {
        return _toPoint(last);
      }
      // Coarse fix from cell/Wi-Fi: no GPS warm-up for a 1 km-rounded position.
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low,
          timeLimit: Duration(seconds: 5),
        ),
      );
      return _toPoint(pos);
    } on TimeoutException {
      return lastKnown();
    } on Exception catch (e) {
      _log.info('no coarse fix: ${e.runtimeType}');
      return lastKnown();
    }
  }

  static LocationSettings _watchSettings({required bool lowPower}) {
    final accuracy = lowPower ? LocationAccuracy.low : LocationAccuracy.medium;
    final distance = lowPower ? 250 : 100;
    if (!kIsWeb && Platform.isAndroid) {
      return AndroidSettings(
        accuracy: accuracy,
        distanceFilter: distance,
        intervalDuration: Duration(seconds: lowPower ? 120 : 60),
      );
    }
    if (!kIsWeb && Platform.isIOS) {
      return AppleSettings(
        accuracy: accuracy,
        distanceFilter: distance,
        pauseLocationUpdatesAutomatically: true,
        allowBackgroundLocationUpdates: false,
      );
    }
    return LocationSettings(accuracy: accuracy, distanceFilter: distance);
  }

  @override
  Stream<GeoPoint> watch({bool lowPower = false}) async* {
    if (!await _grantedWithoutPrompt()) return;
    yield* Geolocator.getPositionStream(
      locationSettings: _watchSettings(lowPower: lowPower),
    ).map(_toPoint).handleError((Object e) {
      _log.info('position updates stopped: ${e.runtimeType}');
    });
  }

  @override
  Stream<GeoPoint> follow({
    required String title,
    required String text,
  }) async* {
    if (!await _grantedWithoutPrompt()) return;
    final LocationSettings settings;
    if (!kIsWeb && Platform.isAndroid) {
      settings = AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 20,
        intervalDuration: const Duration(seconds: 30),
        foregroundNotificationConfig: ForegroundNotificationConfig(
          notificationTitle: title,
          notificationText: text,
          setOngoing: true,
          enableWakeLock: false,
        ),
      );
    } else if (!kIsWeb && Platform.isIOS) {
      settings = AppleSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 20,
        pauseLocationUpdatesAutomatically: false,
        showBackgroundLocationIndicator: true,
        allowBackgroundLocationUpdates: false,
      );
    } else {
      settings = const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 20,
      );
    }
    yield* Geolocator.getPositionStream(locationSettings: settings)
        .map(_toPoint)
        .handleError((Object e) {
          _log.info('shared position updates stopped: ${e.runtimeType}');
        });
  }

  static GeoPoint _toPoint(Position p) =>
      GeoPoint(lat: p.latitude, lon: p.longitude, accuracyM: p.accuracy);
}

final locationServiceProvider = Provider<LocationService>(
  (ref) => GeolocatorLocationService(),
);
