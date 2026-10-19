import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/notify_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
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

  /// Re-fetches and keeps the shown list when the server cannot be reached.
  Future<void> refresh() async {
    try {
      final alerts = await _fetch();
      if (ref.mounted) state = AsyncData(alerts);
    } on ApiException catch (e) {
      _log.info('alerts not refreshed: ${e.code.wire}');
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

/// Keeps the active alerts current: on resume and periodically while the app is in the
/// foreground, more often when push is not available on this phone. Started from `main()`.
class AlertsScheduler with WidgetsBindingObserver {
  AlertsScheduler(this._ref);

  static const withPush = Duration(minutes: 15);
  static const withoutPush = Duration(minutes: 5);

  final Ref _ref;
  Timer? _timer;
  bool _started = false;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _ref.listen(pushAvailableProvider, (_, _) => _startTimer());
    _startTimer();
  }

  Duration get period =>
      _ref.read(pushAvailableProvider) ? withPush : withoutPush;

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(period, (_) => _refresh());
  }

  void _refresh() =>
      unawaited(_ref.read(activeAlertsProvider.notifier).refresh());

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refresh();
      _startTimer();
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _timer?.cancel();
      _timer = null;
    }
  }

  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
  }
}

final alertsSchedulerProvider = Provider<AlertsScheduler>((ref) {
  final scheduler = AlertsScheduler(ref);
  ref.onDispose(scheduler.dispose);
  return scheduler;
});
