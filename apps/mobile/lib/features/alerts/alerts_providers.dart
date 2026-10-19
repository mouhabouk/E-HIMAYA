import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/notify_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
import '../../core/power/battery_saver.dart';
import '../../core/power/scheduling.dart';
import '../../core/push/push_messaging.dart';
import '../../core/storage/app_prefs.dart';

final _log = logger('alerts');

/// Active alerts for where the user is (FR-A-061): the phone's coarse position when location
/// alerts are allowed and location was already granted, otherwise the profile gouvernorat, and
/// otherwise every active alert. The last list is kept for offline use until each alert expires.
class ActiveAlertsController extends AsyncNotifier<List<ActiveAlert>> {
  @override
  Future<List<ActiveAlert>> build() async {
    ref.watch(identityProvider.select((s) => s.fingerprint));
    try {
      return await _fetch();
    } on ApiException catch (e) {
      if (!e.isTransient) rethrow;
      return _cached();
    }
  }

  Future<List<ActiveAlert>> _fetch() async {
    final api = ref.read(apiProvider);
    final prefs = ref.read(appPrefsProvider);
    GeoPoint? position;
    if (prefs.locationAlerts) {
      position = await ref.read(locationServiceProvider).withoutPrompt();
      if (position != null && !position.isInTunisiaBox) position = null;
    }
    int? gouvernorat;
    if (position == null && ref.read(identityProvider).isRegistered) {
      try {
        gouvernorat = (await api.getProfile()).gouvernoratCode;
      } on ApiException {
        gouvernorat = null;
      }
    }
    final alerts = await api.activeAlerts(
      position: position,
      gouvernoratCode: gouvernorat,
    );
    await prefs.setLastAlertsJson(
      jsonEncode([for (final a in alerts) a.source]),
    );
    return alerts;
  }

  List<ActiveAlert> _cached() {
    final raw = ref.read(appPrefsProvider).lastAlertsJson;
    if (raw == null) return const [];
    final now = ref.read(clockProvider)();
    try {
      final json = jsonDecode(raw);
      return [
        for (final a in (json is List ? json : const []))
          if (a is Map<String, Object?>) ActiveAlert.fromJson(a),
      ].where((a) => a.activeAt(now)).toList();
    } on Object {
      return const [];
    }
  }

  /// Re-fetches and keeps the shown list when the server cannot be reached. Returns whether
  /// the server answered.
  Future<bool> refresh() async {
    try {
      final alerts = await _fetch();
      if (ref.mounted) state = AsyncData(alerts);
      return true;
    } on ApiException catch (e) {
      _log.info('alerts not refreshed: ${e.code.wire}');
      return false;
    }
  }
}

final activeAlertsProvider =
    AsyncNotifierProvider<ActiveAlertsController, List<ActiveAlert>>(
      ActiveAlertsController.new,
      retry: (_, _) => null,
    );

/// Alerts still in force, most severe first (the server already orders them so).
final currentAlertsProvider = Provider<List<ActiveAlert>>((ref) {
  final now = ref.watch(clockProvider)();
  return [
    for (final a
        in ref.watch(activeAlertsProvider).value ?? const <ActiveAlert>[])
      if (a.activeAt(now)) a,
  ];
});

/// Shown as a banner on the home screen.
final highAlertsProvider = Provider<List<ActiveAlert>>(
  (ref) => [
    for (final a in ref.watch(currentAlertsProvider))
      if (a.severity == AlertSeverity.high) a,
  ],
);

/// The caller's notifications (FR-A-060), newest first, loaded page by page.
class InboxState {
  const InboxState(this.items, this.nextCursor, {this.loadingMore = false});

  final List<InboxItem> items;
  final String? nextCursor;
  final bool loadingMore;

  bool get hasMore => nextCursor != null;
}

class InboxController extends AsyncNotifier<InboxState> {
  @override
  Future<InboxState> build() async {
    final identity = ref.watch(identityProvider);
    if (!identity.hasIdentity) return const InboxState([], null);
    final page = await ref.read(apiProvider).inbox();
    return InboxState(page.items, page.nextCursor);
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || !current.hasMore || current.loadingMore) return;
    state = AsyncData(
      InboxState(current.items, current.nextCursor, loadingMore: true),
    );
    try {
      final page = await ref
          .read(apiProvider)
          .inbox(cursor: current.nextCursor);
      if (!ref.mounted) return;
      final seen = {for (final i in current.items) i.id};
      state = AsyncData(
        InboxState([
          ...current.items,
          ...page.items.where((i) => !seen.contains(i.id)),
        ], page.nextCursor),
      );
    } on ApiException {
      if (ref.mounted) state = AsyncData(current);
      rethrow;
    }
  }
}

final inboxProvider = AsyncNotifierProvider<InboxController, InboxState>(
  InboxController.new,
  retry: (_, _) => null,
);

/// Keeps the active alerts current: on resume, when the network comes back, and periodically
/// while the app is in the foreground ([AlertPolling]: every 15 min with push, 5 min without;
/// doubled in battery saver; exponential back-off after failures). Nothing runs in the
/// background or while the phone is offline. Started from `main()`.
class AlertsScheduler with WidgetsBindingObserver {
  AlertsScheduler(this._ref);

  final Ref _ref;
  Timer? _timer;
  StreamSubscription<bool>? _connectivity;
  bool _started = false;
  bool _foreground = true;
  bool _online = true;
  int _failures = 0;
  Future<void>? _inFlight;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _ref
      ..listen(pushAvailableProvider, (_, _) => _schedule())
      ..listen(batterySaverActiveProvider, (_, _) => _schedule());
    _connectivity = _ref.read(connectivityProvider).onlineChanges.listen((
      online,
    ) {
      final back = online && !_online;
      _online = online;
      if (back && _foreground) {
        _failures = 0;
        unawaited(refreshNow());
      } else {
        _schedule();
      }
    });
    _schedule();
  }

  /// Whether a refresh is scheduled (false in the background and offline).
  bool get isScheduled => _timer != null;

  Duration get period =>
      AlertPolling.of(pushAvailable: _ref.read(pushAvailableProvider)).next(
        failures: _failures,
        batterySaver: _ref.read(batterySaverActiveProvider),
      );

  void _schedule() {
    _timer?.cancel();
    _timer = null;
    if (!_started || !_foreground || !_online) return;
    _timer = Timer(period, () => unawaited(refreshNow()));
  }

  /// Refreshes now and schedules the next refresh (concurrent calls share one request).
  Future<void> refreshNow() => _inFlight ??= _refresh().whenComplete(() {
    _inFlight = null;
  });

  Future<void> _refresh() async {
    _timer?.cancel();
    _timer = null;
    final ok = await _ref.read(activeAlertsProvider.notifier).refresh();
    _failures = ok ? 0 : _failures + 1;
    _schedule();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_foreground) return;
      _foreground = true;
      unawaited(refreshNow());
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _foreground = false;
      _schedule();
    }
  }

  void dispose() {
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    unawaited(_connectivity?.cancel());
  }
}

final alertsSchedulerProvider = Provider<AlertsScheduler>((ref) {
  final scheduler = AlertsScheduler(ref);
  ref.onDispose(scheduler.dispose);
  return scheduler;
});
