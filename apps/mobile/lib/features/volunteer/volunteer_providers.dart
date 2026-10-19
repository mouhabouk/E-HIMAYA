import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';

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
enum ReadinessTick { idle, sent, ended, skipped }

/// Shares the live position while the volunteer is ready (FR-A-022), and stops at the end of
/// readiness. Runs while the app is in the foreground; the server keeps the last position until
/// `ready_until` and deletes it then.
class ReadinessTracker with WidgetsBindingObserver {
  ReadinessTracker(this._ref, {this.interval = const Duration(seconds: 60)});

  /// The server accepts one update every 20 s; once a minute is enough to dispatch.
  final Duration interval;
  final Ref _ref;
  Timer? _timer;
  bool _started = false;
  bool _foreground = true;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _ref.listen(volunteerProvider, (_, _) => _sync(), fireImmediately: true);
  }

  Volunteer? get _volunteer => _ref.read(volunteerProvider).value;
  DateTime get _now => _ref.read(clockProvider)();

  bool get isSharing => _timer != null;

  void _sync() {
    final ready = _volunteer?.isReadyAt(_now) ?? false;
    if (ready && _foreground) {
      _timer ??= Timer.periodic(interval, (_) => unawaited(tick()));
    } else {
      _timer?.cancel();
      _timer = null;
    }
  }

  /// One update: sends the position while ready, and ends sharing when readiness is over.
  Future<ReadinessTick> tick() async {
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
    final position = await _ref.read(locationServiceProvider).withoutPrompt();
    if (position == null || !position.isInTunisiaBox) {
      return ReadinessTick.skipped;
    }
    try {
      await _ref.read(apiProvider).putVolunteerLocation(position);
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
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) unawaited(tick());
    _sync();
  }

  void dispose() {
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
  }
}

final readinessTrackerProvider = Provider<ReadinessTracker>((ref) {
  final tracker = ReadinessTracker(ref);
  ref.onDispose(tracker.dispose);
  return tracker;
});
