import 'dart:math' as math;

import '../../core/http/stream_models.dart';
import '../../core/power/scheduling.dart';

/// Pure rules of the live stream (FR-A-050..052), free of Flutter and WebRTC so each one is unit
/// tested: video quality tiers and their adaptation to the network, the location cadence, the
/// reconnection schedule.

/// Video encoding caps for one network quality. Capture is 1280×720 at most; lower tiers scale
/// the encoder down rather than reopening the camera. WebRTC's own congestion control still
/// adapts below each cap.
enum LiveQuality {
  /// 4G / Wi-Fi: 720p, 30 fps, up to 1.5 Mbit/s.
  high(maxBitrate: 1500000, scaleDown: 1, maxFramerate: 30),

  /// Fair 4G / good 3G: 480p, 24 fps, 800 kbit/s.
  medium(maxBitrate: 800000, scaleDown: 1.5, maxFramerate: 24),

  /// 3G: 360p, 15 fps, 400 kbit/s.
  low(maxBitrate: 400000, scaleDown: 2, maxFramerate: 15),

  /// Poor 3G / EDGE: 240p, 10 fps, 180 kbit/s. Still bad here → offer the clip fallback.
  minimal(maxBitrate: 180000, scaleDown: 3, maxFramerate: 10);

  const LiveQuality({
    required this.maxBitrate,
    required this.scaleDown,
    required this.maxFramerate,
  });

  /// Bits per second.
  final int maxBitrate;

  /// `scaleResolutionDownBy` from the 1280×720 capture.
  final double scaleDown;
  final int maxFramerate;

  /// Capture size (landscape terms; the camera rotates it).
  static const captureWidth = 1280;
  static const captureHeight = 720;
  static const captureFramerate = 30;

  /// Opus voice: speech is enough, keeps the uplink for video.
  static const audioMaxBitrate = 32000;

  LiveQuality? get lower =>
      index + 1 < values.length ? values[index + 1] : null;
  LiveQuality? get higher => index > 0 ? values[index - 1] : null;

  /// Where a stream starts: the top tier on Wi-Fi, one below on mobile data (most 3G links
  /// cannot hold 1.5 Mbit/s up), and never above [medium] in battery saver (fewer pixels to
  /// encode and send).
  static LiveQuality initial({
    required NetworkKind network,
    required bool batterySaver,
  }) {
    final start = network == NetworkKind.unmetered ? high : medium;
    if (batterySaver && start.index < medium.index) return medium;
    return start;
  }
}

/// One sample of the sender statistics (every few seconds while live).
class LiveNetworkSample {
  const LiveNetworkSample({
    this.availableOutgoingBitrate,
    this.fractionLost,
    this.roundTripTime,
  });

  /// Bandwidth estimate of the selected candidate pair, bits per second.
  final double? availableOutgoingBitrate;

  /// 0..1, from the receiver report of the media server.
  final double? fractionLost;
  final Duration? roundTripTime;
}

/// The decision taken after a sample.
class BitrateDecision {
  const BitrateDecision(this.quality, {required this.weakNetwork});
  final LiveQuality quality;

  /// Even the lowest tier does not hold: the UI offers to record a clip instead (FR-A-051).
  final bool weakNetwork;
}

/// Steps the quality down quickly when the link degrades and back up slowly when it recovers
/// (hysteresis, so it does not oscillate).
class AdaptiveBitratePolicy {
  AdaptiveBitratePolicy({
    required LiveQuality initial,
    this.badSamplesToDowngrade = 2,
    this.goodSamplesToUpgrade = 4,
    this.badSamplesForWeakNetwork = 4,
    this.maxLoss = 0.08,
    this.goodLoss = 0.02,
    this.maxRtt = const Duration(milliseconds: 800),
    this.ceiling = LiveQuality.high,
  }) : _quality = initial;

  final int badSamplesToDowngrade;
  final int goodSamplesToUpgrade;

  /// Consecutive bad samples at [LiveQuality.minimal] before [BitrateDecision.weakNetwork].
  final int badSamplesForWeakNetwork;
  final double maxLoss;
  final double goodLoss;
  final Duration maxRtt;

  /// Highest tier allowed (lowered in battery saver).
  LiveQuality ceiling;

  LiveQuality _quality;
  int _bad = 0;
  int _good = 0;

  LiveQuality get quality => _quality;

  bool _isBad(LiveNetworkSample s) {
    final loss = s.fractionLost;
    final rtt = s.roundTripTime;
    final bw = s.availableOutgoingBitrate;
    return (loss != null && loss > maxLoss) ||
        (rtt != null && rtt > maxRtt) ||
        (bw != null && bw < _quality.maxBitrate * 0.7);
  }

  bool _isGood(LiveNetworkSample s) {
    final up = _quality.higher;
    if (up == null || up.index < ceiling.index) return false;
    final loss = s.fractionLost ?? 0;
    final bw = s.availableOutgoingBitrate;
    final rtt = s.roundTripTime;
    return loss <= goodLoss &&
        (rtt == null || rtt < maxRtt ~/ 2) &&
        bw != null &&
        bw >= up.maxBitrate * 1.3;
  }

  BitrateDecision next(LiveNetworkSample sample) {
    if (_quality.index < ceiling.index) {
      _quality = ceiling;
      _bad = _good = 0;
    }
    if (_isBad(sample)) {
      _good = 0;
      _bad++;
      final down = _quality.lower;
      if (down != null && _bad >= badSamplesToDowngrade) {
        _quality = down;
        _bad = 0;
        return BitrateDecision(_quality, weakNetwork: false);
      }
      return BitrateDecision(
        _quality,
        weakNetwork: down == null && _bad >= badSamplesForWeakNetwork,
      );
    }
    _bad = 0;
    if (_isGood(sample)) {
      _good++;
      if (_good >= goodSamplesToUpgrade) {
        _quality = _quality.higher!;
        _good = 0;
      }
    } else {
      _good = 0;
    }
    return BitrateDecision(_quality, weakNetwork: false);
  }
}

/// Position cadence while live: one send every `location_interval_s` (never closer than the 3 s
/// the server accepts), one request in flight at a time.
///
/// Battery: live streaming is the one high-power exception of the app (FR-A-052 wants the
/// position all along). The cadence ignores the in-app battery saver, uses a high-accuracy fix,
/// and stops with the stream; nothing of it survives the stream (see [LiveController]).
class LiveLocationThrottle {
  LiveLocationThrottle(Duration interval)
    : interval = interval < LiveStreamGrant.minLocationInterval
          ? LiveStreamGrant.minLocationInterval
          : interval;

  final Duration interval;
  DateTime? _lastSentAt;
  bool _inFlight = false;

  bool shouldSend(DateTime now) {
    if (_inFlight) return false;
    final last = _lastSentAt;
    return last == null || now.difference(last) >= interval;
  }

  /// A request is going out.
  void begin(DateTime now) {
    _inFlight = true;
    _lastSentAt = now;
  }

  void end() => _inFlight = false;

  void reset() {
    _lastSentAt = null;
    _inFlight = false;
  }
}

/// Reconnection after the media path drops: a few attempts with growing delays, then the clip
/// fallback is offered.
class LiveReconnectPolicy {
  const LiveReconnectPolicy({
    this.maxAttempts = 3,
    this.baseDelay = const Duration(seconds: 2),
    this.maxDelay = const Duration(seconds: 10),
  });

  final int maxAttempts;
  final Duration baseDelay;
  final Duration maxDelay;

  /// Delay before attempt [attempt] (1-based), or null when attempts are exhausted.
  Duration? delayFor(int attempt) {
    if (attempt < 1 || attempt > maxAttempts) return null;
    final ms = baseDelay.inMilliseconds * math.pow(2, attempt - 1);
    return Duration(
      milliseconds: math.min(ms.toInt(), maxDelay.inMilliseconds),
    );
  }
}
