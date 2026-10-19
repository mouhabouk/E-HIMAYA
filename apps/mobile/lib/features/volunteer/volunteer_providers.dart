import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
import '../../core/power/battery_saver.dart';
import '../../core/power/scheduling.dart';

final _log = logger('volunteer');

/// Readiness needs a position: the phone could not give one.
class LocationUnavailable implements Exception {
  const LocationUnavailable(this.availability);
  final LocationAvailability availability;
}

/// The account's volunteer application (FR-A-020…022). Null when it never applied; always null
/// for anonymous users (volunteering needs a registered account).
class VolunteerController extends AsyncNotifier<Volunteer?> {
  @override
  Future<Volunteer?> build() async {
    final registered = ref.watch(
      identityProvider.select((s) => s.isRegistered ? s.fingerprint : null),
    );
    if (registered == null) return null;
    return ref.read(apiProvider).myVolunteer();
  }

  Future<void> reload() async {
    final v = await ref.read(apiProvider).myVolunteer();
    if (ref.mounted) state = AsyncData(v);
  }

  Future<Volunteer> submit(VolunteerInput input) async {
    final v = await ref.read(apiProvider).putVolunteer(input);
    if (ref.mounted) state = AsyncData(v);
    return v;
  }

  Future<void> withdraw() async {
    await ref.read(apiProvider).withdrawVolunteer();
    await reload();
  }

  /// Readiness on for [hours]: the current position is required (it lives on the server only
  /// while ready, never archived).
  Future<void> setReady(int hours) async {
    final location = ref.read(locationServiceProvider);
    final permission = await location.ensurePermission();
    if (permission != LocationAvailability.granted) {
      throw LocationUnavailable(permission);
    }
    final position = await location.bestEffort();
    if (position == null || !position.isInTunisiaBox) {
      throw const LocationUnavailable(LocationAvailability.granted);
    }
    final v = await ref
        .read(apiProvider)
        .setReadiness(ready: true, position: position, hours: hours);
    if (ref.mounted) state = AsyncData(v);
  }

  Future<void> setNotReady() async {
    final v = await ref.read(apiProvider).setReadiness(ready: false);
    if (ref.mounted) state = AsyncData(v);
  }
}

final volunteerProvider =
    AsyncNotifierProvider<VolunteerController, Volunteer?>(
      VolunteerController.new,
      retry: (_, _) => null,
    );

/// Call-outs addressed to the volunteer (UC-05): open ones and those still in progress.
final myCalloutsProvider = FutureProvider.autoDispose<List<MyCallout>>((
  ref,
) async {
  final registered = ref.watch(identityProvider.select((s) => s.isRegistered));
  if (!registered) return const [];
  return ref.watch(apiProvider).myCallouts();
}, retry: (_, _) => null);

/// What [ReadinessTracker.tick] did.
enum ReadinessTick {
  idle,
  sent,
  ended,
  skipped,

  /// Ready, but the volunteer has not moved enough since the last send (nothing sent).
  unchanged,
}

/// Shares the live position while the volunteer is ready (FR-A-022), and stops at the end of
/// readiness. Runs while the app is in the foreground only; the server keeps the last position
/// until `ready_until` and deletes it then.
///
/// Battery: position updates come from a balanced-accuracy stream with a distance filter (no
/// GPS fix while the phone does not move); a send happens only after a real move (100 m, 250 m
/// in battery saver), as a rare heartbeat, and never faster than the server accepts. The check
/// timer starts at [interval] and stretches up to [maxInterval] while nothing changes. Sharing
/// stops at once when readiness ends or the app leaves the foreground.
class ReadinessTracker with WidgetsBindingObserver {
  ReadinessTracker(
    this._ref, {
    this.interval = const Duration(seconds: 60),
    this.maxInterval = const Duration(minutes: 8),
    LocationCoalescer? coalescer,
  }) : _coalescer = coalescer ?? LocationCoalescer(),
       _cadence = AdaptiveInterval(min: interval, max: maxInterval);

  final Duration interval;
  final Duration maxInterval;
  final Ref _ref;
  final LocationCoalescer _coalescer;
  final AdaptiveInterval _cadence;
  Timer? _timer;
  StreamSubscription<GeoPoint>? _watch;
  bool _watchLowPower = false;
  GeoPoint? _latest;
  DateTime? _latestAt;
  Future<ReadinessTick>? _inFlight;
  bool _started = false;
  bool _foreground = true;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _ref
      ..listen(volunteerProvider, (_, _) => _sync(), fireImmediately: true)
      ..listen(batterySaverActiveProvider, (_, _) {
        // New radio settings for the stream.
        _stopWatch();
        _sync();
      });
  }

  Volunteer? get _volunteer => _ref.read(volunteerProvider).value;
  DateTime get _now => _ref.read(clockProvider)();
  bool get _saver => _ref.read(batterySaverActiveProvider);

  bool get isSharing => _timer != null || _watch != null;

  /// Delay before the next check (for tests and diagnostics).
  Duration get currentInterval => _cadence.current;

  void _sync() {
    final ready = _volunteer?.isReadyAt(_now) ?? false;
    if (ready && _foreground) {
      _timer ??= Timer(_cadence.current, _onTimer);
      if (_watch == null && _started) {
        _watchLowPower = _saver;
        _watch = _ref
            .read(locationServiceProvider)
            .watch(lowPower: _watchLowPower)
            .listen(_onFix, onError: (Object _) => _stopWatch());
      }
    } else {
      _timer?.cancel();
      _timer = null;
      _stopWatch();
      _cadence.activity();
      if (!ready) _coalescer.reset();
    }
  }

  void _stopWatch() {
    unawaited(_watch?.cancel());
    _watch = null;
    _latest = null;
    _latestAt = null;
  }

  void _onFix(GeoPoint fix) {
    _latest = fix;
    _latestAt = _now;
    if (_coalescer.shouldSend(fix, _now, batterySaver: _saver)) {
      unawaited(tick());
    }
  }

  Future<void> _onTimer() async {
    _timer = null;
    final result = await tick();
    if (result == ReadinessTick.sent) {
      _cadence.activity();
    } else {
      _cadence.idle();
    }
    _sync();
  }

  /// A stream fix younger than the check interval, else a cheap last-known/coarse position.
  Future<GeoPoint?> _position() async {
    final latest = _latest;
    final at = _latestAt;
    if (latest != null && at != null && _now.difference(at) <= maxInterval) {
      return latest;
    }
    return _ref.read(locationServiceProvider).withoutPrompt();
  }

  /// One update: sends the position while ready (when it changed enough), and ends sharing when
  /// readiness is over. Concurrent calls share the update in progress.
  Future<ReadinessTick> tick() =>
      _inFlight ??= _tick().whenComplete(() => _inFlight = null);

  Future<ReadinessTick> _tick() async {
    final v = _volunteer;
    if (v == null || !v.ready) {
      _sync();
      return ReadinessTick.idle;
    }
    if (!v.isReadyAt(_now)) {
      // Readiness ran out: the server already ended it; show the new state.
      await _reload();
      return ReadinessTick.ended;
    }
    final position = await _position();
    if (position == null || !position.isInTunisiaBox) {
      return ReadinessTick.skipped;
    }
    final now = _now;
    if (!_coalescer.shouldSend(position, now, batterySaver: _saver)) {
      return ReadinessTick.unchanged;
    }
    try {
      await _ref.read(apiProvider).putVolunteerLocation(position);
      _coalescer.markSent(position, now);
      return ReadinessTick.sent;
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.notReady ||
          e.code == ApiErrorCode.notVolunteer) {
        await _reload();
        return ReadinessTick.ended;
      }
      _log.info('position not sent: ${e.code.wire}');
      return ReadinessTick.skipped;
    }
  }

  Future<void> _reload() async {
    try {
      await _ref.read(volunteerProvider.notifier).reload();
    } on ApiException catch (e) {
      _log.info('volunteer not reloaded: ${e.code.wire}');
    }
    _sync();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final foreground = state == AppLifecycleState.resumed;
    if (state == AppLifecycleState.inactive) return; // transient
    if (foreground == _foreground) return;
    _foreground = foreground;
    _sync();
    if (_foreground) unawaited(tick());
  }

  void dispose() {
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _stopWatch();
  }
}

final readinessTrackerProvider = Provider<ReadinessTracker>((ref) {
  final tracker = ReadinessTracker(ref);
  ref.onDispose(tracker.dispose);
  return tracker;
});
