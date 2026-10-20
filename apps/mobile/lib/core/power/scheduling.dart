import 'dart:math' as math;

import '../http/models.dart';

/// Pure scheduling rules behind every periodic or background cost of the app (battery
/// hardening, phase 5.5). Kept free of Flutter and plugins so each rule is unit tested.
///
/// Budget, measured on the rules below for one hour in the foreground (no movement):
/// - alert polling: 4 requests with push (was 4), 12 without push (was 12), 2/6 in battery saver;
///   failures back off instead of retrying at the same pace;
/// - sync: 0 wake-ups with an empty queue (was 80 at 45 s), back-off to 10 min when nothing
///   progresses;
/// - volunteer readiness: about 4 position sends while stationary (was 60), the GPS radio in
///   balanced (cell/Wi-Fi) mode with a 100 m filter instead of a high-accuracy fix every minute;
/// - simulated push (dev only): 5 s while messages arrive, up to 60 s when idle (was 720 polls).
///
/// The one deliberate exception is live streaming (phase 6, FR-A-052): while a stream is open the
/// position is sent at the server's cadence with a high-accuracy fix and the screen stays on,
/// battery saver or not. It is registered as a high-power session (`high_power.dart`) that ends
/// with the stream; battery saver only caps the stream's starting video quality.

/// One battery reading from the platform.
class BatteryReading {
  const BatteryReading({
    required this.level,
    required this.charging,
    this.systemPowerSave = false,
  });

  /// 0–100, null when the platform does not tell.
  final int? level;
  final bool charging;

  /// The phone's own battery saver / Low Power Mode.
  final bool systemPowerSave;
}

/// What the user chose for the in-app battery saver.
enum BatterySaverMode {
  /// On when the battery is low (or the phone's own saver is on), off while charging.
  auto,
  on,
  off;

  static BatterySaverMode fromName(String? name) =>
      values.asNameMap()[name] ?? auto;
}

/// Decides whether the in-app battery saver is active, with hysteresis so it does not flap
/// around the threshold.
class BatterySaverPolicy {
  const BatterySaverPolicy({this.enterAtPercent = 20, this.exitAtPercent = 30})
    : assert(exitAtPercent > enterAtPercent);

  final int enterAtPercent;
  final int exitAtPercent;

  bool isActive({
    required BatterySaverMode mode,
    required BatteryReading? reading,
    required bool wasActive,
  }) {
    switch (mode) {
      case BatterySaverMode.on:
        return true;
      case BatterySaverMode.off:
        return false;
      case BatterySaverMode.auto:
        if (reading == null) return false;
        if (reading.charging) return false;
        if (reading.systemPowerSave) return true;
        final level = reading.level;
        if (level == null) return false;
        if (level <= enterAtPercent) return true;
        return wasActive && level < exitAtPercent;
    }
  }
}

/// A polling period with exponential back-off on consecutive failures.
class PollSchedule {
  const PollSchedule({
    required this.normal,
    required this.saver,
    required this.maxBackoff,
  });

  final Duration normal;

  /// Period while the battery saver is active (never shorter than [normal]).
  final Duration saver;

  /// Longest delay after repeated failures.
  final Duration maxBackoff;

  Duration next({required int failures, required bool batterySaver}) {
    final base = batterySaver ? saver : normal;
    if (failures <= 0) return base;
    final factor = 1 << math.min(failures, 16);
    final ms = math.min(
      base.inMilliseconds * factor,
      math.max(maxBackoff.inMilliseconds, base.inMilliseconds),
    );
    return Duration(milliseconds: ms);
  }
}

/// Active-alert polling: push is the primary channel; polling only covers phones where push is
/// missing and the time between two pushes.
abstract final class AlertPolling {
  static const withPush = PollSchedule(
    normal: Duration(minutes: 15),
    saver: Duration(minutes: 30),
    maxBackoff: Duration(minutes: 30),
  );

  /// Without push polling is the only way to learn about alerts: kept frequent even in saver.
  static const withoutPush = PollSchedule(
    normal: Duration(minutes: 5),
    saver: Duration(minutes: 10),
    maxBackoff: Duration(minutes: 15),
  );

  static PollSchedule of({required bool pushAvailable}) =>
      pushAvailable ? withPush : withoutPush;
}

/// A delay that grows while nothing happens and snaps back on activity (stationary volunteer,
/// idle simulator, sync queue that cannot progress).
class AdaptiveInterval {
  AdaptiveInterval({required this.min, required this.max, this.factor = 2})
    : assert(max >= min),
      assert(factor >= 1),
      _current = min;

  final Duration min;
  final Duration max;
  final int factor;
  Duration _current;

  Duration get current => _current;

  /// Something happened: back to [min].
  Duration activity() => _current = min;

  /// Nothing happened: the next delay is longer, up to [max].
  Duration idle() {
    final ms = math.min(_current.inMilliseconds * factor, max.inMilliseconds);
    return _current = Duration(milliseconds: ms);
  }
}

/// Great-circle distance in metres.
double distanceMeters(GeoPoint a, GeoPoint b) {
  const r = 6371000.0;
  double rad(double d) => d * math.pi / 180;
  final dLat = rad(b.lat - a.lat);
  final dLon = rad(b.lon - a.lon);
  final h =
      math.pow(math.sin(dLat / 2), 2) +
      math.cos(rad(a.lat)) *
          math.cos(rad(b.lat)) *
          math.pow(math.sin(dLon / 2), 2);
  return 2 * r * math.asin(math.min(1, math.sqrt(h)));
}

/// Coalesces the volunteer's position updates: a fix is sent only when the volunteer moved
/// enough, or as a rare heartbeat, and never faster than the server accepts (one per 20 s).
class LocationCoalescer {
  LocationCoalescer({
    this.minSpacing = const Duration(seconds: 30),
    this.moveThresholdM = 100,
    this.saverMoveThresholdM = 250,
    this.heartbeat = const Duration(minutes: 15),
    this.saverHeartbeat = const Duration(minutes: 30),
  });

  final Duration minSpacing;
  final double moveThresholdM;
  final double saverMoveThresholdM;
  final Duration heartbeat;
  final Duration saverHeartbeat;

  GeoPoint? _lastSent;
  DateTime? _lastSentAt;

  GeoPoint? get lastSent => _lastSent;

  bool shouldSend(GeoPoint fix, DateTime now, {bool batterySaver = false}) {
    final last = _lastSent;
    final at = _lastSentAt;
    if (last == null || at == null) return true;
    final elapsed = now.difference(at);
    if (elapsed < minSpacing) return false;
    if (elapsed >= (batterySaver ? saverHeartbeat : heartbeat)) return true;
    final threshold = batterySaver ? saverMoveThresholdM : moveThresholdM;
    return distanceMeters(last, fix) >= threshold;
  }

  void markSent(GeoPoint fix, DateTime now) {
    _lastSent = fix;
    _lastSentAt = now;
  }

  void reset() {
    _lastSent = null;
    _lastSentAt = null;
  }
}

/// Network the phone is on, as far as the platform tells.
enum NetworkKind {
  /// No interface up (a hint only; the request itself decides).
  none,

  /// Wi-Fi or Ethernet: unmetered, cheap radio.
  unmetered,

  /// Mobile data (or unknown, treated the same way).
  metered,
}

/// Whether a queued media file may be uploaded now. The report itself (text, position) is never
/// delayed; an SOS and its media are never delayed. Only in battery saver, a large file on mobile
/// data waits for Wi-Fi, at most [maxWait] after it was queued, so evidence still reaches the
/// operators.
class MediaUploadPolicy {
  const MediaUploadPolicy({
    this.largeBytes = 8 * 1024 * 1024,
    this.maxWait = const Duration(minutes: 30),
  });

  final int largeBytes;
  final Duration maxWait;

  bool mayUpload({
    required bool sos,
    required int sizeBytes,
    required NetworkKind network,
    required bool batterySaver,
    required DateTime queuedAt,
    required DateTime now,
  }) {
    // `none` is only a hint (it can be wrong behind some VPNs): treated as unknown, metered.
    if (sos || !batterySaver) return true;
    if (network == NetworkKind.unmetered) return true;
    if (sizeBytes < largeBytes) return true;
    return !now.difference(queuedAt).isNegative &&
        now.difference(queuedAt) >= maxWait;
  }
}
