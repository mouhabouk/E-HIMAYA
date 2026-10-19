import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart';
import '../connectivity/connectivity.dart';
import '../logging/log.dart';
import 'sync_engine.dart';

final _log = logger('sync.scheduler');

/// Triggers the sync engine: on app start, when connectivity comes back, when the identity
/// changes (login, anonymous choice), on demand, and periodically while the app is in the
/// foreground.
class SyncScheduler with WidgetsBindingObserver {
  SyncScheduler(this._ref, {this.period = const Duration(seconds: 45)});

  final Ref _ref;
  final Duration period;
  Timer? _timer;
  StreamSubscription<bool>? _connectivity;
  bool _started = false;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _connectivity = _ref.read(connectivityProvider).onlineChanges.listen((
      online,
    ) {
      if (online) trigger('connectivity');
    });
    _startTimer();
    trigger('start');
  }

  Future<void> trigger(String reason) async {
    try {
      await _ref.read(syncEngineProvider).runOnce();
    } on Object catch (e, st) {
      _log.warning('sync pass failed ($reason)', e, st);
    }
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(period, (_) => trigger('periodic'));
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _startTimer();
      trigger('resumed');
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _timer?.cancel();
      _timer = null;
    }
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
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
