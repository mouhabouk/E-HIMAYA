import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart';
import '../connectivity/connectivity.dart';
import '../db/open_database.dart';
import '../logging/log.dart';
import '../power/battery_saver.dart';
import '../power/scheduling.dart';
import 'sync_engine.dart';

final _log = logger('sync.scheduler');

/// Triggers the sync engine: on app start, when connectivity comes back, when the identity
/// changes (login, anonymous choice), on demand (after a submit, an SOS), and on a timer while
/// the app is in the foreground and the queue still holds work.
///
/// Battery: no timer at all while the queue is empty, offline or in the background (the
/// triggers above restart it); the timer starts at [period] and backs off up to [maxIdle] (twice
/// that in battery saver) while passes make no progress. Explicit triggers always run a pass at
/// once: an SOS is never delayed by the scheduler.
class SyncScheduler with WidgetsBindingObserver {
  SyncScheduler(
    this._ref, {
    this.period = const Duration(seconds: 45),
    this.maxIdle = const Duration(minutes: 10),
  }) : _cadence = AdaptiveInterval(min: period, max: maxIdle);

  final Ref _ref;
  final Duration period;
  final Duration maxIdle;
  final AdaptiveInterval _cadence;
  Timer? _timer;
  StreamSubscription<bool>? _connectivity;
  bool _started = false;
  bool _foreground = true;
  bool _online = true;

  /// Whether a timed pass is scheduled.
  bool get isScheduled => _timer != null;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _connectivity = _ref.read(connectivityProvider).onlineChanges.listen((
      online,
    ) {
      _online = online;
      if (online) {
        _cadence.activity();
        trigger('connectivity');
      } else {
        _cancelTimer();
      }
    });
    trigger('start');
  }

  Future<void> trigger(String reason) async {
    SyncSummary? summary;
    try {
      summary = await _ref.read(syncEngineProvider).runOnce();
    } on Object catch (e, st) {
      _log.warning('sync pass failed ($reason)', e, st);
    }
    final progressed =
        summary != null &&
        summary.reportsSent + summary.mediaUploaded + summary.mediaStored > 0;
    await _scheduleNext(progressed: progressed);
  }

  Future<void> _scheduleNext({required bool progressed}) async {
    _cancelTimer();
    if (!_started || !_foreground || !_online) return;
    final List<Object> pending;
    try {
      pending = await _ref.read(databaseProvider).reportsNeedingSync();
    } on Object {
      return;
    }
    if (pending.isEmpty) {
      _cadence.activity();
      return;
    }
    var delay = progressed ? _cadence.activity() : _cadence.idle();
    if (_ref.read(batterySaverActiveProvider)) delay *= 2;
    if (!_foreground || !_online) return;
    _cancelTimer();
    _timer = Timer(delay, () => trigger('periodic'));
  }

  void _cancelTimer() {
    _timer?.cancel();
    _timer = null;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _foreground = true;
      _cadence.activity();
      trigger('resumed');
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _foreground = false;
      _cancelTimer();
    }
  }

  void dispose() {
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _cancelTimer();
    _connectivity?.cancel();
  }
}

/// Started once from `main()`; widget tests never start it.
final syncSchedulerProvider = Provider<SyncScheduler>((ref) {
  final scheduler = SyncScheduler(ref);
  ref.listen(identityProvider.select((s) => s.fingerprint), (_, next) {
    if (next != null && scheduler._started) scheduler.trigger('identity');
  });
  ref.onDispose(scheduler.dispose);
  return scheduler;
});

/// Asks for a sync pass now (after a submit, pull-to-refresh). Fire and forget.
final requestSyncProvider = Provider<Future<void> Function()>(
  (ref) =>
      () => ref.read(syncSchedulerProvider).trigger('manual'),
);
