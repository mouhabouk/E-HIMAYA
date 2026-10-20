import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/notify_models.dart';
import '../../core/http/weather_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
import '../../core/power/battery_saver.dart';
import '../../core/power/scheduling.dart';
import '../../core/storage/app_prefs.dart';

final _log = logger('weather');

/// Why the card cannot show fresh values.
enum WeatherIssue {
  /// No position without a prompt (location not granted, or no fix).
  noLocation,

  /// The position is outside Tunisia: the grid does not cover it.
  outsideCoverage,

  /// No network interface: nothing was asked.
  offline,

  /// The server did not answer (or answered with an error).
  unavailable,
}

/// What the weather card shows.
class WeatherCardState {
  const WeatherCardState({
    this.report,
    this.fetchedAt,
    this.fromCache = false,
    this.loading = false,
    this.issue,
  });

  /// The last values, fresh or from the offline copy.
  final WeatherReport? report;

  /// When [report] was received from the server.
  final DateTime? fetchedAt;

  /// [report] is the offline copy, not an answer of this refresh.
  final bool fromCache;
  final bool loading;
  final WeatherIssue? issue;

  WeatherCardState copyWith({
    bool? fromCache,
    bool? loading,
    WeatherIssue? issue,
    bool clearIssue = false,
  }) => WeatherCardState(
    report: report,
    fetchedAt: fetchedAt,
    fromCache: fromCache ?? this.fromCache,
    loading: loading ?? this.loading,
    issue: clearIssue ? null : (issue ?? this.issue),
  );
}

/// Rounds a position to 2 decimals (≈ 1 km): enough for a 0.25° weather grid, and the server
/// never learns the precise position from a weather request.
GeoPoint coarseWeatherPoint(GeoPoint p) => GeoPoint(
  lat: (p.lat * 100).roundToDouble() / 100,
  lon: (p.lon * 100).roundToDouble() / 100,
);

/// FR-A-034: weather at the user's coarse position, cached for offline display. Refreshes run
/// only when [WeatherPolling.isDue] allows them (≤ every 30 min, 60 min in battery saver,
/// back-off after failures), never offline. [WeatherScheduler] drives them in the foreground.
class WeatherController extends Notifier<WeatherCardState> {
  DateTime? _lastAttempt;
  int _failures = 0;
  Future<void>? _inFlight;

  /// Consecutive failed requests (drives the back-off).
  int get failures => _failures;
  DateTime? get lastAttempt => _lastAttempt;

  @override
  WeatherCardState build() {
    final cached = _readCache();
    if (cached == null) {
      // First display: ask now (the card is on screen, so the app is in the foreground).
      unawaited(Future.microtask(refreshIfDue));
      return const WeatherCardState(loading: true);
    }
    // The copy counts as the last attempt: a restart within 30 min asks nothing.
    _lastAttempt = cached.fetchedAt;
    unawaited(Future.microtask(refreshIfDue));
    return cached;
  }

  WeatherCardState? _readCache() {
    final raw = ref.read(appPrefsProvider).lastWeatherJson;
    if (raw == null) return null;
    try {
      final json = jsonDecode(raw);
      if (json is! Map<String, Object?>) return null;
      final at = DateTime.tryParse(json['fetched_at'] as String? ?? '');
      final report = WeatherReport.fromJson(json['report']);
      if (at == null || report == null) return null;
      final now = ref.read(clockProvider)();
      if (now.difference(at) > WeatherPolling.cacheMaxAge) return null;
      return WeatherCardState(report: report, fetchedAt: at, fromCache: true);
    } on Object {
      return null;
    }
  }

  bool _due({bool manual = false}) => WeatherPolling.isDue(
    lastAttempt: _lastAttempt,
    now: ref.read(clockProvider)(),
    failures: _failures,
    batterySaver: ref.read(batterySaverActiveProvider),
    manual: manual,
  );

  /// Refreshes when the rules allow it (concurrent calls share one request).
  Future<void> refreshIfDue() => _due() ? _start() : Future.value();

  /// The user asked (retry, "use my location"): honoured unless they asked a minute ago.
  Future<void> refreshManually() =>
      _due(manual: true) ? _start() : Future.value();

  Future<void> _start() => _inFlight ??= _refresh().whenComplete(() {
    _inFlight = null;
    // Lets the foreground timer count from this attempt (no-op until started from main()).
    if (ref.mounted) ref.read(weatherSchedulerProvider).reschedule();
  });

  Future<void> _refresh() async {
    if (!ref.mounted) return;
    // Only a request to the server counts as an attempt. Offline, without a position or
    // outside Tunisia nothing is asked, so the refresh runs as soon as that changes (network
    // back, location granted) — still never more than once per scheduler period.
    if (!await ref.read(connectivityProvider).isOnline()) {
      _set(state.copyWith(loading: false, issue: WeatherIssue.offline));
      return;
    }
    _set(state.copyWith(loading: true));
    final position = await ref.read(locationServiceProvider).withoutPrompt();
    if (!ref.mounted) return;
    if (position == null) {
      _set(state.copyWith(loading: false, issue: WeatherIssue.noLocation));
      return;
    }
    if (!position.isInTunisiaBox) {
      _set(state.copyWith(loading: false, issue: WeatherIssue.outsideCoverage));
      return;
    }
    _lastAttempt = ref.read(clockProvider)();
    try {
      final report = await ref
          .read(apiProvider)
          .weather(coarseWeatherPoint(position));
      final at = ref.read(clockProvider)().toUtc();
      _failures = 0;
      await ref
          .read(appPrefsProvider)
          .setLastWeatherJson(
            jsonEncode({
              'fetched_at': at.toIso8601String(),
              'report': report.source,
            }),
          );
      _set(WeatherCardState(report: report, fetchedAt: at));
    } on ApiException catch (e) {
      _failures++;
      _log.info('weather not refreshed: ${e.code.wire}');
      _set(state.copyWith(loading: false, issue: WeatherIssue.unavailable));
    }
  }

  void _set(WeatherCardState value) {
    if (ref.mounted) state = value;
  }
}

final weatherProvider = NotifierProvider<WeatherController, WeatherCardState>(
  WeatherController.new,
);

/// Weather alerts listed by the last weather answer, still in force.
final weatherAlertsProvider = Provider<List<ActiveAlert>>((ref) {
  final report = ref.watch(weatherProvider.select((s) => s.report));
  if (report == null) return const [];
  return report.activeAlerts(ref.watch(clockProvider)());
});

/// Keeps the weather card current in the foreground only: on resume and when the network comes
/// back (each time only if [WeatherPolling.isDue]), and on a timer of [WeatherPolling]'s
/// period, once the card has been shown. Nothing runs in the background or offline. Started
/// from `main()`.
class WeatherScheduler with WidgetsBindingObserver {
  WeatherScheduler(this._ref);

  final Ref _ref;
  Timer? _timer;
  StreamSubscription<bool>? _connectivity;
  bool _started = false;
  bool _foreground = true;
  bool _online = true;

  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _ref.listen(batterySaverActiveProvider, (_, _) => _schedule());
    _connectivity = _ref.read(connectivityProvider).onlineChanges.listen((
      online,
    ) {
      final back = online && !_online;
      _online = online;
      if (back && _foreground) {
        unawaited(_run());
      } else {
        _schedule();
      }
    });
    _schedule();
  }

  /// Whether a refresh is scheduled (false in the background and offline).
  bool get isScheduled => _timer != null;

  /// Delay until the next scheduled refresh.
  Duration get period {
    final c = _ref.read(weatherProvider.notifier);
    return WeatherPolling.schedule.next(
      failures: c.failures,
      batterySaver: _ref.read(batterySaverActiveProvider),
    );
  }

  /// Recomputes the timer after an attempt made elsewhere (the card's first display, a retry).
  void reschedule() => _schedule();

  void _schedule() {
    _timer?.cancel();
    _timer = null;
    if (!_started || !_foreground || !_online) return;
    // Until the card was shown once nothing is asked (e.g. the app opened over a locked phone
    // for an alert): the card's first display starts the cycle.
    if (!_ref.exists(weatherProvider)) return;
    final last = _ref.read(weatherProvider.notifier).lastAttempt;
    var wait = period;
    if (last != null) {
      final elapsed = _ref.read(clockProvider)().difference(last);
      if (!elapsed.isNegative && elapsed < wait) wait -= elapsed;
    }
    _timer = Timer(wait, () => unawaited(_run()));
  }

  Future<void> _run() async {
    _timer?.cancel();
    _timer = null;
    if (_ref.exists(weatherProvider)) {
      await _ref.read(weatherProvider.notifier).refreshIfDue();
    }
    _schedule();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_foreground) return;
      _foreground = true;
      unawaited(_run());
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

final weatherSchedulerProvider = Provider<WeatherScheduler>((ref) {
  final scheduler = WeatherScheduler(ref);
  ref.onDispose(scheduler.dispose);
  return scheduler;
});
