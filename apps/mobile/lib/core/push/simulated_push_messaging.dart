// ┏━━ SIMULATION ━━ Push delivery without Firebase: polls the notify-sim inbox (dev/test only).
// ┃ PRODUCTION: build WITHOUT --dart-define=PUSH_SIMULATOR_URL (this file then stays unused) and
// ┃   pass --dart-define FIREBASE_API_KEY / FIREBASE_APP_ID / FIREBASE_MESSAGING_SENDER_ID /
// ┃   FIREBASE_PROJECT_ID, copied from Firebase console > Project settings > General > Your apps
// ┃   (Android app). iOS: add ios/Runner/GoogleService-Info.plist (or the same four defines),
// ┃   enable the Push Notifications capability and upload the APNs key in Firebase console >
// ┃   Project settings > Cloud Messaging. API: set FCM_SERVICE_ACCOUNT (base64 of the key from
// ┃   Project settings > Service accounts) and remove FCM_API_URL / FCM_SERVICE_ACCOUNT_FILE.
// ┃   See apps/mobile/README.md, "Switching to production".
// ┗━━━━━━━━━━━━━━━━
import 'dart:async';
import 'dart:io' show Platform;
import 'dart:math' as math;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:uuid/uuid.dart';

import '../logging/log.dart';
import '../storage/app_prefs.dart';
import 'push_messaging.dart';
import 'push_notifications.dart';
import 'push_payload.dart';

final _log = logger('push');

// ┏━━ SIMULATION ━━ Switch that turns simulated push on (debug builds against notify-sim).
// ┃ PRODUCTION: do not pass --dart-define=PUSH_SIMULATOR_URL; pass the four FIREBASE_* defines
// ┃   instead (Firebase console > Project settings > Your apps). See the banner at the top.
// ┗━━━━━━━━━━━━━━━━
/// Base URL of the channels simulator (`notify-sim`), injected with
/// `--dart-define=PUSH_SIMULATOR_URL=…`. Empty on every real build.
const pushSimulatorUrl = String.fromEnvironment('PUSH_SIMULATOR_URL');

/// Dio for the simulator's inspection API: its own base URL and no identity headers (the
/// simulator has no authentication and must never see the user's credentials).
Dio buildSimulatorDio(String baseUrl, {HttpClientAdapter? adapter}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
      responseType: ResponseType.json,
      headers: {'Accept': 'application/json'},
    ),
  );
  if (adapter != null) dio.httpClientAdapter = adapter;
  return dio;
}

/// Title prefix of every notification shown by the simulator, so it is never mistaken for a
/// real push.
const simulatedTitlePrefix = '[SIM] ';

/// Push for development builds without a Firebase project: the server sends to the simulator
/// as if it were FCM, and the app polls the simulator for the pushes addressed to its token.
///
/// The token (`sim-<uuid v4>`) is registered with the API like a real FCM token. Polling runs
/// only while the app is in the foreground; each push is shown as a local notification on the
/// channel the server chose and emitted on [onForeground], and tapping it emits [onOpened].
class SimulatedPushMessaging
    with WidgetsBindingObserver
    implements PushMessaging {
  SimulatedPushMessaging({
    required this._dio,
    required this._prefs,
    PushNotifications? notifications,
    this.interval = const Duration(seconds: 5),
    this.maxBackoff = const Duration(minutes: 1),
    Uuid? uuid,
  }) : _notifications = notifications ?? LocalPushNotifications(),
       _uuid = uuid ?? const Uuid();

  /// Delay between two polls while the simulator answers.
  final Duration interval;

  /// Longest delay between two polls while the simulator is unreachable.
  final Duration maxBackoff;

  static const _pageSize = 50;

  final Dio _dio;
  final AppPrefs _prefs;
  final PushNotifications _notifications;
  final Uuid _uuid;
  final _foreground = StreamController<PushPayload>.broadcast();
  final _opened = StreamController<PushPayload>.broadcast();

  bool _started = false;
  bool _disposed = false;
  bool _inForeground = false;
  int _failures = 0;
  Timer? _timer;
  Future<bool>? _inFlight;
  PushPayload? _launch;

  @override
  String get platform => !kIsWeb && Platform.isIOS ? 'ios' : 'android';

  /// Whether a poll is scheduled (false while the app is in the background).
  @visibleForTesting
  bool get isPolling => _timer != null;

  @override
  Future<bool> start(PushChannelNames names) async {
    if (_started) return true;
    _started = true;
    try {
      _launch = await _notifications.init(names, onTap: _opened.add);
      await _notifications.requestPermission();
    } on Object catch (e, st) {
      // Pushes are still emitted on onForeground, only the system notification is missing.
      _log.warning('local notifications unavailable', e, st);
    }
    await token();
    if (_disposed) return false;
    _log.info('simulated push from ${_dio.options.baseUrl}');
    final binding = WidgetsBinding.instance;
    binding.addObserver(this);
    final state = binding.lifecycleState;
    if (state == null || state == AppLifecycleState.resumed) _resume();
    return true;
  }

  @override
  Future<String?> token() async {
    final existing = _prefs.simPushToken;
    if (existing != null) return existing;
    final created = 'sim-${_uuid.v4()}';
    await _prefs.setSimPushToken(created);
    return created;
  }

  /// The token never changes.
  @override
  Stream<String> get onTokenRefresh => const Stream.empty();

  @override
  Stream<PushPayload> get onForeground => _foreground.stream;

  @override
  Stream<PushPayload> get onOpened => _opened.stream;

  @override
  Future<PushPayload?> launchPayload() async {
    final p = _launch;
    _launch = null;
    return p;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _resume();
      case AppLifecycleState.paused ||
          AppLifecycleState.hidden ||
          AppLifecycleState.detached:
        _inForeground = false;
        _timer?.cancel();
        _timer = null;
      case AppLifecycleState.inactive:
        // Transient (dialogs, app switcher): keep the current schedule.
        break;
    }
  }

  void _resume() {
    if (_disposed || _inForeground) return;
    _inForeground = true;
    _failures = 0;
    _schedule(Duration.zero);
  }

  void _schedule(Duration delay) {
    _timer?.cancel();
    _timer = Timer(delay, _tick);
  }

  Future<void> _tick() async {
    _timer = null;
    final ok = await pollOnce();
    _failures = ok ? 0 : _failures + 1;
    if (_disposed || !_inForeground || _timer != null) return;
    _schedule(_nextDelay());
  }

  /// [interval], doubled after each consecutive failure up to [maxBackoff].
  Duration _nextDelay() {
    if (_failures == 0) return interval;
    final factor = 1 << math.min(_failures, 10);
    final ms = math.min(
      interval.inMilliseconds * factor,
      maxBackoff.inMilliseconds,
    );
    return Duration(milliseconds: ms);
  }

  /// Fetches the pushes received since the last one seen. False when the simulator could not
  /// be reached or answered something unexpected (never throws).
  @visibleForTesting
  Future<bool> pollOnce() => _inFlight ??= _poll().whenComplete(() {
    _inFlight = null;
  });

  Future<bool> _poll() async {
    try {
      final token = await this.token();
      final after = _prefs.simPushLastSeq;
      final response = await _dio.get<Object?>(
        '/api/messages',
        queryParameters: {
          'channel': 'push',
          'token': token,
          'after': after,
          'limit': _pageSize,
        },
      );
      final body = response.data;
      if (body is! Map || body['items'] is! List) {
        _log.fine('unexpected simulator response');
        return false;
      }
      var last = after;
      for (final item in body['items'] as List) {
        if (item is! Map) continue;
        final seq = item['seq'];
        if (seq is! int || seq <= after) continue;
        last = math.max(last, seq);
        await _deliver(seq, item);
      }
      final serverLast = body['last_seq'];
      if (serverLast is int && serverLast < after) {
        // The simulator restarted (its sequence starts again): read it from the beginning.
        last = 0;
      }
      if (last != after) await _prefs.setSimPushLastSeq(last);
      return true;
    } on Object catch (e) {
      // Simulator stopped or unreachable: retried later with back-off, never surfaced.
      if (_failures == 0) _log.info('simulator unreachable: ${e.runtimeType}');
      return false;
    }
  }

  Future<void> _deliver(int seq, Map<Object?, Object?> item) async {
    final payload = parseSimulatorItem(item);
    if (payload == null || _disposed) return;
    _foreground.add(payload);
    if (payload.title == null) return;
    final channel = item['android_channel'];
    try {
      await _notifications.show(
        seq & 0x7fffffff,
        PushPayload(
          kind: payload.kind,
          data: payload.data,
          title: '$simulatedTitlePrefix${payload.title}',
          body: payload.body,
        ),
        channelId: channel is String ? channel : null,
      );
    } on Object catch (e) {
      _log.info('notification not shown: ${e.runtimeType}');
    }
  }

  void dispose() {
    _disposed = true;
    _timer?.cancel();
    _timer = null;
    if (_started) WidgetsBinding.instance.removeObserver(this);
    _foreground.close();
    _opened.close();
  }
}

/// Maps one item of the simulator's inspection API to the payload a real FCM push carries
/// (same `data` keys). Null when the item is malformed or of an unknown kind.
PushPayload? parseSimulatorItem(Map<Object?, Object?> item) {
  final data = item['data'];
  if (data is! Map) return null;
  final title = item['title'];
  final body = item['body'];
  return PushPayload.parse(
    {
      for (final e in data.entries)
        if (e.key is String) e.key as String: e.value,
    },
    title: title is String ? title : null,
    body: body is String ? body : null,
  );
}
