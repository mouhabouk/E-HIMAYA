import 'dart:async';

import 'package:drift/drift.dart' show Value;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/stream_models.dart';
import '../../core/location/location_service.dart';
import '../../core/logging/log.dart';
import '../../core/platform/device_services.dart';
import '../../core/power/battery_saver.dart';
import '../../core/power/high_power.dart';
import '../../core/security/locked_alert.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/sync/report_queue.dart';
import '../../core/sync/sync_engine.dart';
import '../../core/webrtc/whip_client.dart';
import 'live_policies.dart';
import 'live_publisher.dart';

final _log = logger('live');

/// Where the stream goes: a new report created on the spot (home Live button) or a report that
/// was just submitted / is listed in "My reports".
class LiveTarget {
  const LiveTarget.newReport({this.category = ReportCategory.other})
    : clientUuid = null,
      serverId = null,
      trackingCode = null;

  const LiveTarget.existing({
    this.clientUuid,
    this.serverId,
    this.trackingCode,
    this.category = ReportCategory.other,
  }) : assert(clientUuid != null || serverId != null);

  final String? clientUuid;
  final String? serverId;
  final String? trackingCode;
  final ReportCategory category;

  bool get isNew => clientUuid == null && serverId == null;
}

enum LivePhase {
  idle,

  /// Camera opening, report being created, stream being requested.
  preparing,

  /// WHIP offer/answer and ICE in progress.
  connecting,
  live,

  /// The media path dropped; new attempts are being made.
  reconnecting,
  stopping,

  /// Over normally (see [LiveEndReason]).
  ended,

  /// Could not go live, or lost for good (see [LiveFailure]); the clip fallback is offered.
  failed;

  bool get isActive =>
      this == preparing ||
      this == connecting ||
      this == live ||
      this == reconnecting;
}

enum LiveEndReason {
  /// The user tapped stop.
  userStopped,

  /// An operator ended the stream from the dashboard.
  operatorStopped,

  /// `max_duration_s` reached.
  maxDuration,

  /// The server ended it for another reason (token expired, error).
  serverEnded,

  /// The phone went back to the locked alert view.
  locked,
}

enum LiveFailure {
  /// New report without any position: nothing can be created (call 198 instead).
  noLocation,

  /// The report could not reach the server (offline): it stays queued, a clip can be attached.
  reportNotSent,
  permissionDenied,
  cameraUnavailable,

  /// `409 stream_already_active`.
  alreadyActive,

  /// `429` (6 streams an hour).
  rateLimited,

  /// The server refused the stream (report closed, not the owner…).
  refused,

  /// WebRTC could not connect, or the connection was lost and the reconnections failed.
  connectionFailed,

  /// Over the lock screen only the public alert view exists.
  locked,
}

class LiveState {
  const LiveState({
    this.phase = LivePhase.idle,
    this.target,
    this.reportClientUuid,
    this.reportServerId,
    this.trackingCode,
    this.streamId,
    this.simulated = false,
    this.startedAt,
    this.endedAt,
    this.maxDuration = LiveStreamGrant.defaultMaxDuration,
    this.muted = false,
    this.frontCamera = false,
    this.quality = LiveQuality.medium,
    this.weakNetwork = false,
    this.locationShared = true,
    this.reconnectAttempt = 0,
    this.endReason,
    this.failure,
    this.apiError,
  });

  final LivePhase phase;
  final LiveTarget? target;

  /// The report the stream is attached to (local row and server id, when known).
  final String? reportClientUuid;
  final String? reportServerId;
  final String? trackingCode;
  final String? streamId;
  final bool simulated;

  /// First time the media path connected (elapsed time counts from it).
  final DateTime? startedAt;
  final DateTime? endedAt;
  final Duration maxDuration;
  final bool muted;
  final bool frontCamera;
  final LiveQuality quality;

  /// Even the lowest quality does not hold: the clip is suggested (the stream goes on).
  final bool weakNetwork;

  /// False when location is not allowed: the stream goes on without positions.
  final bool locationShared;
  final int reconnectAttempt;
  final LiveEndReason? endReason;
  final LiveFailure? failure;
  final ApiErrorCode? apiError;

  bool get isActive => phase.isActive;

  /// A clip can be attached instead (FR-A-051): the report exists, at least locally.
  bool get canFallback => reportClientUuid != null || reportServerId != null;

  LiveState copyWith({
    LivePhase? phase,
    String? reportClientUuid,
    String? reportServerId,
    String? trackingCode,
    String? streamId,
    bool? simulated,
    DateTime? startedAt,
    DateTime? endedAt,
    Duration? maxDuration,
    bool? muted,
    bool? frontCamera,
    LiveQuality? quality,
    bool? weakNetwork,
    bool? locationShared,
    int? reconnectAttempt,
    LiveEndReason? endReason,
    LiveFailure? failure,
    ApiErrorCode? apiError,
  }) => LiveState(
    phase: phase ?? this.phase,
    target: target,
    reportClientUuid: reportClientUuid ?? this.reportClientUuid,
    reportServerId: reportServerId ?? this.reportServerId,
    trackingCode: trackingCode ?? this.trackingCode,
    streamId: streamId ?? this.streamId,
    simulated: simulated ?? this.simulated,
    startedAt: startedAt ?? this.startedAt,
    endedAt: endedAt ?? this.endedAt,
    maxDuration: maxDuration ?? this.maxDuration,
    muted: muted ?? this.muted,
    frontCamera: frontCamera ?? this.frontCamera,
    quality: quality ?? this.quality,
    weakNetwork: weakNetwork ?? this.weakNetwork,
    locationShared: locationShared ?? this.locationShared,
    reconnectAttempt: reconnectAttempt ?? this.reconnectAttempt,
    endReason: endReason ?? this.endReason,
    failure: failure ?? this.failure,
    apiError: apiError ?? this.apiError,
  );
}

/// Delays of the live session (tests shorten or drive them with fake time).
class LiveTimings {
  const LiveTimings({
    this.reportWait = const Duration(seconds: 20),
    this.reportRetry = const Duration(seconds: 3),
    this.connectTimeout = const Duration(seconds: 20),
    this.disconnectGrace = const Duration(seconds: 6),
    this.statusPoll = const Duration(seconds: 10),
    this.statsEvery = const Duration(seconds: 5),
    this.stopTimeout = const Duration(seconds: 6),
    this.reconnect = const LiveReconnectPolicy(),
  });

  /// How long a new or just-submitted report may take to reach the server.
  final Duration reportWait;
  final Duration reportRetry;

  /// From the WHIP answer to a connected media path.
  final Duration connectTimeout;

  /// A `disconnected` path often recovers by itself; reconnect only after this.
  final Duration disconnectGrace;

  /// `GET /streams/{id}`: learns that an operator ended the stream.
  final Duration statusPoll;
  final Duration statsEvery;

  /// Upper bound of the stop requests (stop API + WHIP DELETE) before the camera is released.
  final Duration stopTimeout;
  final LiveReconnectPolicy reconnect;
}

final liveTimingsProvider = Provider<LiveTimings>((ref) => const LiveTimings());

/// The live session state machine (FR-A-050..052):
///
/// `idle → preparing → connecting → live ⇄ reconnecting → stopping → ended`, or `→ failed`
/// (with the clip fallback) from any active phase.
///
/// * preparing: opens the camera, makes sure the report exists on the server (a new report is
///   queued like an SOS and pushed by the sync engine), then `POST /reports/{id}/streams`;
/// * connecting: WHIP offer → answer, waits for the media path;
/// * while active: the position every `location_interval_s` (`POST /streams/{id}/location`), the
///   stream status every [LiveTimings.statusPoll] (an operator may end it), the sender statistics
///   for the adaptive quality, a local `max_duration_s` deadline, the screen kept on;
/// * a lost media path is retried with a new stream on the same report
///   ([LiveReconnectPolicy]); after the last attempt the session fails and offers the clip;
/// * stop (user, operator, max duration, lock screen): `POST /streams/{id}/stop` and WHIP
///   `DELETE`, then the camera is released and the high-power session ends.
class LiveController extends Notifier<LiveState> {
  static const highPowerSession = 'live-stream';

  LivePublisher? _publisher;
  LiveStreamGrant? _grant;
  WhipSession? _session;
  AdaptiveBitratePolicy? _bitrate;
  LiveLocationThrottle? _throttle;
  Timer? _locationTimer;
  Timer? _statusTimer;
  Timer? _statsTimer;
  Timer? _maxTimer;
  Timer? _graceTimer;
  StreamSubscription<PublisherConnection>? _connectionSub;
  StreamSubscription<String>? _lateSub;

  // Subscriptions are cancelled without awaiting: the events of a stale session are ignored
  // anyway (generation check), and nothing must wait on them while stopping.

  /// Incremented on every start/stop: async continuations of an older session do nothing.
  int _generation = 0;
  bool _connectedThisAttempt = false;
  Completer<bool>? _connected;

  @override
  LiveState build() {
    ref.listen(lockedAlertProvider.select((s) => s.locked), (_, locked) {
      if (locked && state.isActive) {
        unawaited(_finish(LiveEndReason.locked, callStop: true));
      }
    });
    ref.onDispose(() {
      _generation++;
      _cancelTimers();
      final publisher = _publisher;
      _publisher = null;
      if (publisher != null) unawaited(publisher.dispose());
    });
    return const LiveState();
  }

  DateTime _now() => ref.read(clockProvider)();
  LiveTimings get _t => ref.read(liveTimingsProvider);
  EHimayaApi get _api => ref.read(apiProvider);

  /// Clears an ended or failed session (the screen opens on the pre-start panel again).
  void reset() {
    if (state.isActive || state.phase == LivePhase.stopping) return;
    state = const LiveState();
  }

  /// Starts a live session. No-op while one is active.
  Future<void> start(LiveTarget target) async {
    if (state.isActive || state.phase == LivePhase.stopping) return;
    final gen = ++_generation;
    if (ref.read(lockedAlertProvider).locked) {
      state = LiveState(
        phase: LivePhase.failed,
        target: target,
        failure: LiveFailure.locked,
      );
      return;
    }
    final network = await ref.read(connectivityProvider).networkKind();
    final saver = ref.read(batterySaverActiveProvider);
    final quality = LiveQuality.initial(network: network, batterySaver: saver);
    _bitrate = AdaptiveBitratePolicy(
      initial: quality,
      ceiling: saver ? LiveQuality.medium : LiveQuality.high,
    );
    state = LiveState(
      phase: LivePhase.preparing,
      target: target,
      reportClientUuid: target.clientUuid,
      reportServerId: target.serverId,
      trackingCode: target.trackingCode,
      quality: quality,
    );
    ref.read(highPowerSessionsProvider.notifier).begin(highPowerSession);
    unawaited(ref.read(deviceServicesProvider).keepScreenOn(true));

    // 1. Camera and microphone (the system prompts here, after the in-app rationale).
    final publisher = ref.read(livePublisherFactoryProvider)();
    _publisher = publisher;
    try {
      await publisher.openMedia(frontCamera: false);
    } on MediaPermissionDenied {
      return _fail(gen, LiveFailure.permissionDenied);
    } on Object catch (e) {
      _log.info('camera unavailable: ${e.runtimeType}');
      return _fail(gen, LiveFailure.cameraUnavailable);
    }
    if (gen != _generation) return;

    // 2. The report on the server.
    final serverId = await _resolveReport(gen, target);
    if (gen != _generation) return;
    if (serverId == null) return; // _resolveReport already failed the session.

    // 3. Location permission (asked once; the stream goes on without it).
    final availability = await ref
        .read(locationServiceProvider)
        .ensurePermission();
    if (gen != _generation) return;
    state = state.copyWith(
      locationShared: availability == LocationAvailability.granted,
    );

    // 4. The stream.
    final grant = await _requestStream(gen, serverId, first: true);
    if (grant == null || gen != _generation) return;
    _startSessionTimers(gen);
    await _connect(gen);
  }

  Future<String?> _resolveReport(int gen, LiveTarget target) async {
    if (target.serverId != null) return target.serverId;
    var clientUuid = target.clientUuid;
    if (clientUuid == null) {
      final point = await ref
          .read(locationServiceProvider)
          .bestEffort(timeout: const Duration(seconds: 5));
      if (gen != _generation) return null;
      if (point == null) {
        await _fail(gen, LiveFailure.noLocation);
        return null;
      }
      final queued = await ref
          .read(reportQueueProvider)
          .enqueue(
            ReportDraft(
              category: target.category,
              location: point,
              lang: ref.read(localeCodeProvider),
            ),
          );
      if (gen != _generation) return null;
      clientUuid = queued.clientUuid;
      state = state.copyWith(
        reportClientUuid: clientUuid,
        trackingCode: queued.tempCode,
      );
    }
    final db = ref.read(databaseProvider);
    final deadline = _now().add(_t.reportWait);
    // The user is waiting to go live: a report still waiting for its back-off is tried now.
    final pending = await db.reportByUuid(clientUuid);
    if (pending != null &&
        pending.serverId == null &&
        pending.nextAttemptAt != null) {
      await db.updateReport(
        clientUuid,
        const PendingReportsCompanion(nextAttemptAt: Value(null)),
      );
    }
    if (gen != _generation) return null;
    while (true) {
      final row = await db.reportByUuid(clientUuid);
      if (gen != _generation) return null;
      if (row?.serverId != null) {
        state = state.copyWith(
          reportServerId: row!.serverId,
          trackingCode: row.serverTrackingCode,
        );
        return row.serverId;
      }
      if (row == null) break;
      try {
        await ref.read(syncEngineProvider).runOnce();
      } on Object catch (e) {
        _log.info('sync before live failed: ${e.runtimeType}');
      }
      if (gen != _generation) return null;
      final again = await db.reportByUuid(clientUuid);
      if (again?.serverId != null) continue;
      if (!_now().isBefore(deadline)) break;
      await Future<void>.delayed(_t.reportRetry);
      if (gen != _generation) return null;
    }
    await _fail(gen, LiveFailure.reportNotSent);
    return null;
  }

  /// `POST /reports/{id}/streams`. On the first request a refusal fails the session; on a
  /// reconnection it returns null and lets the caller count the attempt.
  Future<LiveStreamGrant?> _requestStream(
    int gen,
    String reportId, {
    required bool first,
  }) async {
    try {
      final grant = await _api.startStream(reportId);
      if (gen != _generation) {
        // Stopped meanwhile: free the stream at once (one active stream per report).
        unawaited(
          _api.stopStream(grant.streamId).then<void>((_) {}, onError: (_) {}),
        );
        return null;
      }
      _grant = grant;
      _throttle = LiveLocationThrottle(grant.locationInterval);
      state = state.copyWith(
        streamId: grant.streamId,
        simulated: grant.simulated,
        maxDuration: grant.maxDuration,
        phase: first ? LivePhase.connecting : state.phase,
      );
      return grant;
    } on ApiException catch (e) {
      _log.info('stream refused: ${e.code.wire}');
      if (!first && e.isTransient) return null;
      final failure = switch (e.code) {
        ApiErrorCode.streamAlreadyActive => LiveFailure.alreadyActive,
        ApiErrorCode.rateLimited => LiveFailure.rateLimited,
        _ when e.isTransient => LiveFailure.connectionFailed,
        _ => LiveFailure.refused,
      };
      await _fail(gen, failure, apiError: e.code, callStop: false);
      return null;
    }
  }

  /// One WHIP publish attempt on the current grant; on failure goes to [_reconnect].
  Future<void> _connect(int gen) async {
    final grant = _grant;
    final publisher = _publisher;
    if (grant == null || publisher == null) return;
    _connectedThisAttempt = false;
    final connected = _connected = Completer<bool>();
    unawaited(_connectionSub?.cancel());
    _connectionSub = publisher.connection.listen((c) => _onConnection(gen, c));
    try {
      final offer = await publisher.createOffer(quality: state.quality);
      if (gen != _generation) return;
      final session = await ref
          .read(whipClientProvider)
          .publish(
            whipUrl: grant.whipUrl,
            token: grant.publishToken,
            offerSdp: offer,
          );
      if (gen != _generation) {
        unawaited(_deleteWhip(session, grant));
        return;
      }
      _session = session;
      await publisher.applyAnswer(session.answerSdp);
      _trickle(gen, offer, session, grant);
    } on WhipException catch (e) {
      _log.info('whip publish failed: $e');
      if (gen == _generation) await _reconnect(gen);
      return;
    } on Object catch (e) {
      _log.info('webrtc setup failed: ${e.runtimeType}');
      if (gen == _generation) await _reconnect(gen);
      return;
    }
    final ok = await connected.future.timeout(
      _t.connectTimeout,
      onTimeout: () => false,
    );
    if (gen != _generation) return;
    if (!ok && !_connectedThisAttempt) await _reconnect(gen);
  }

  void _trickle(
    int gen,
    String offer,
    WhipSession session,
    LiveStreamGrant grant,
  ) {
    final ufrag = RegExp(r'a=ice-ufrag:(\S+)').firstMatch(offer)?.group(1);
    final pwd = RegExp(r'a=ice-pwd:(\S+)').firstMatch(offer)?.group(1);
    final mid = RegExp(r'a=mid:(\S+)').firstMatch(offer)?.group(1) ?? '0';
    if (ufrag == null || pwd == null) return;
    unawaited(_lateSub?.cancel());
    var supported = true;
    _lateSub = _publisher?.lateCandidates.listen((line) async {
      if (!supported || gen != _generation) return;
      try {
        supported = await ref
            .read(whipClientProvider)
            .patchCandidates(
              session: session,
              token: grant.publishToken,
              sdpFragment: trickleFragment(
                iceUfrag: ufrag,
                icePwd: pwd,
                mid: mid,
                candidates: [line],
              ),
            );
      } on WhipException {
        supported = false;
      }
    });
  }

  void _onConnection(int gen, PublisherConnection c) {
    if (gen != _generation) return;
    switch (c) {
      case PublisherConnection.connected:
        _graceTimer?.cancel();
        _graceTimer = null;
        _connectedThisAttempt = true;
        final c0 = _connected;
        if (c0 != null && !c0.isCompleted) c0.complete(true);
        _onLive(gen);
      case PublisherConnection.disconnected:
        if (state.phase != LivePhase.live) return;
        _graceTimer?.cancel();
        _graceTimer = Timer(_t.disconnectGrace, () {
          if (gen == _generation && state.phase == LivePhase.live) {
            unawaited(_reconnect(gen));
          }
        });
      case PublisherConnection.failed:
        final c0 = _connected;
        if (c0 != null && !c0.isCompleted) {
          c0.complete(false); // _connect reconnects.
        } else if (state.phase == LivePhase.live) {
          unawaited(_reconnect(gen));
        }
      case PublisherConnection.connecting || PublisherConnection.closed:
        break;
    }
  }

  void _onLive(int gen) {
    final now = _now();
    final startedAt = state.startedAt ?? now;
    state = state.copyWith(
      phase: LivePhase.live,
      startedAt: startedAt,
      reconnectAttempt: 0,
    );
    // The whole session (reconnections included) stays within max_duration_s.
    _maxTimer ??= Timer(state.maxDuration - now.difference(startedAt), () {
      if (gen == _generation && state.isActive) {
        unawaited(_finish(LiveEndReason.maxDuration, callStop: true));
      }
    });
    _statsTimer ??= Timer.periodic(_t.statsEvery, (_) => _adapt(gen));
    unawaited(_publisher?.setQuality(state.quality));
  }

  Future<void> _adapt(int gen) async {
    final publisher = _publisher;
    final policy = _bitrate;
    if (publisher == null || policy == null || state.phase != LivePhase.live) {
      return;
    }
    final sample = await publisher.sample();
    if (sample == null || gen != _generation) return;
    final decision = policy.next(sample);
    if (decision.quality != state.quality) {
      await publisher.setQuality(decision.quality);
    }
    if (gen != _generation) return;
    if (decision.quality != state.quality ||
        decision.weakNetwork != state.weakNetwork) {
      state = state.copyWith(
        quality: decision.quality,
        weakNetwork: decision.weakNetwork,
      );
    }
  }

  /// The media path is lost (or never came up): new stream on the same report, a few times.
  Future<void> _reconnect(int gen) async {
    if (gen != _generation || !state.isActive) return;
    final attempt = state.reconnectAttempt + 1;
    final delay = _t.reconnect.delayFor(attempt);
    _graceTimer?.cancel();
    _graceTimer = null;
    _statsTimer?.cancel();
    _statsTimer = null;
    if (delay == null) {
      return _fail(gen, LiveFailure.connectionFailed);
    }
    state = state.copyWith(
      phase: LivePhase.reconnecting,
      reconnectAttempt: attempt,
    );
    final old = _grant;
    final oldSession = _session;
    _session = null;
    unawaited(_lateSub?.cancel());
    _lateSub = null;
    await _publisher?.closeConnection();
    if (old != null) {
      // Never reconnect against an operator's decision.
      final info = await _status(old.streamId);
      if (gen != _generation) return;
      if (info?.endReason == LiveEndReasonWire.staffStopped) {
        return _finish(LiveEndReason.operatorStopped, callStop: false);
      }
      if (info?.endReason == LiveEndReasonWire.maxDuration) {
        return _finish(LiveEndReason.maxDuration, callStop: false);
      }
      if (oldSession != null) unawaited(_deleteWhip(oldSession, old));
      try {
        await _api.stopStream(old.streamId);
      } on ApiException {
        // Offline: the server ends it itself when MediaMTX reports the publisher gone.
      }
    }
    await Future<void>.delayed(delay);
    if (gen != _generation || !state.isActive) return;
    final reportId = state.reportServerId;
    if (reportId == null) return _fail(gen, LiveFailure.connectionFailed);
    final grant = await _requestStream(gen, reportId, first: false);
    if (gen != _generation || !state.isActive) return;
    if (grant == null) return _reconnect(gen);
    await _connect(gen);
  }

  Future<LiveStreamInfo?> _status(String streamId) async {
    try {
      return await _api.getStream(streamId);
    } on ApiException {
      return null;
    }
  }

  void _startSessionTimers(int gen) {
    final grant = _grant!;
    _locationTimer?.cancel();
    _locationTimer = Timer.periodic(
      _throttle!.interval,
      (_) => unawaited(_sendLocation(gen)),
    );
    unawaited(_sendLocation(gen));
    _statusTimer?.cancel();
    _statusTimer = Timer.periodic(_t.statusPoll, (_) => unawaited(_poll(gen)));
    // The publish token expires if the stream never starts; the server status says so too.
    _log.fine('session timers started for ${grant.streamId}');
  }

  Future<void> _sendLocation(int gen) async {
    final throttle = _throttle;
    final grant = _grant;
    if (throttle == null || grant == null || !state.locationShared) return;
    if (!state.isActive || state.phase == LivePhase.reconnecting) return;
    final now = _now();
    if (!throttle.shouldSend(now)) return;
    throttle.begin(now);
    try {
      final location = ref.read(locationServiceProvider);
      final timeout = throttle.interval < const Duration(seconds: 5)
          ? throttle.interval
          : const Duration(seconds: 5);
      final point =
          await location.current(timeout: timeout) ??
          await location.lastKnown();
      if (point == null || gen != _generation || !state.isActive) return;
      await _api.postStreamLocation(grant.streamId, point);
    } on ApiException catch (e) {
      if (e.code == ApiErrorCode.streamNotActive && gen == _generation) {
        await _poll(gen);
      }
    } finally {
      throttle.end();
    }
  }

  /// Status poll: an operator ending the stream, the server's max duration, an expired token.
  Future<void> _poll(int gen) async {
    final grant = _grant;
    if (grant == null || !state.isActive) return;
    if (state.phase == LivePhase.reconnecting) return;
    final info = await _status(grant.streamId);
    if (info == null || gen != _generation || !state.isActive) return;
    if (grant.streamId != _grant?.streamId) return;
    final status = info.status;
    if (status == null || status.isActive) return;
    switch (info.endReason) {
      case LiveEndReasonWire.staffStopped:
        await _finish(LiveEndReason.operatorStopped, callStop: false);
      case LiveEndReasonWire.maxDuration:
        await _finish(LiveEndReason.maxDuration, callStop: false);
      case LiveEndReasonWire.publisherStopped || null
          when status == LiveStreamStatus.ended:
        // MediaMTX saw the publisher go away while we think we publish: the path dropped.
        await _reconnect(gen);
      default:
        await _finish(LiveEndReason.serverEnded, callStop: false);
    }
  }

  /// User stop (one tap): ends everything.
  Future<void> stop() async {
    if (!state.isActive) return;
    await _finish(LiveEndReason.userStopped, callStop: true);
  }

  Future<void> toggleMute() async {
    final muted = !state.muted;
    await _publisher?.setMuted(muted);
    state = state.copyWith(muted: muted);
  }

  Future<void> switchCamera() async {
    final publisher = _publisher;
    if (publisher == null) return;
    final front = await publisher.switchCamera();
    state = state.copyWith(frontCamera: front);
  }

  Future<void> _finish(LiveEndReason reason, {required bool callStop}) async {
    final gen = ++_generation;
    state = state.copyWith(phase: LivePhase.stopping);
    await _release(callStop: callStop);
    if (gen != _generation) return;
    state = state.copyWith(
      phase: LivePhase.ended,
      endReason: reason,
      endedAt: _now(),
    );
  }

  Future<void> _fail(
    int gen,
    LiveFailure failure, {
    ApiErrorCode? apiError,
    bool callStop = true,
  }) async {
    if (gen != _generation) return;
    final next = ++_generation;
    state = state.copyWith(phase: LivePhase.stopping);
    await _release(callStop: callStop);
    if (next != _generation) return;
    state = state.copyWith(
      phase: LivePhase.failed,
      failure: failure,
      apiError: apiError,
      endedAt: _now(),
    );
  }

  /// Stop requests (bounded), camera released, screen and high-power session back to normal.
  Future<void> _release({required bool callStop}) async {
    _cancelTimers();
    final grant = _grant;
    final session = _session;
    _grant = null;
    _session = null;
    _throttle = null;
    final c = _connected;
    if (c != null && !c.isCompleted) c.complete(false);
    unawaited(_connectionSub?.cancel());
    _connectionSub = null;
    unawaited(_lateSub?.cancel());
    _lateSub = null;
    final pending = <Future<void>>[
      if (callStop && grant != null)
        _api.stopStream(grant.streamId).then<void>((_) {}, onError: (_) {}),
      if (session != null && grant != null) _deleteWhip(session, grant),
    ];
    if (pending.isNotEmpty) {
      await Future.wait(pending).timeout(_t.stopTimeout, onTimeout: () => []);
    }
    final publisher = _publisher;
    _publisher = null;
    if (publisher != null) {
      try {
        await publisher.dispose();
      } on Object catch (e) {
        _log.info('publisher dispose failed: ${e.runtimeType}');
      }
    }
    if (!ref.mounted) return;
    unawaited(ref.read(deviceServicesProvider).keepScreenOn(false));
    ref.read(highPowerSessionsProvider.notifier).end(highPowerSession);
  }

  Future<void> _deleteWhip(WhipSession session, LiveStreamGrant grant) async {
    try {
      await ref
          .read(whipClientProvider)
          .delete(session: session, token: grant.publishToken);
    } on WhipException catch (e) {
      _log.info('whip delete failed: $e');
    }
  }

  void _cancelTimers() {
    for (final t in [
      _locationTimer,
      _statusTimer,
      _statsTimer,
      _maxTimer,
      _graceTimer,
    ]) {
      t?.cancel();
    }
    _locationTimer = _statusTimer = _statsTimer = _maxTimer = _graceTimer =
        null;
  }

  /// The local camera preview (black until the camera is open).
  LivePublisher? get publisher => _publisher;

  /// FR-A-051: attaches the clip recorded instead of the stream to this session's report (tus
  /// upload by the sync engine, `kind = video`). The clip is marked urgent: the battery saver
  /// does not hold it for Wi-Fi. Returns the local `client_uuid` of the report.
  Future<String> attachClip(String path, {required String mime}) async {
    final s = state;
    final uuid = await ref
        .read(reportQueueProvider)
        .attach(
          AttachTarget(
            clientUuid: s.reportClientUuid,
            serverId: s.reportServerId,
            trackingCode: s.trackingCode,
            category: s.target?.category ?? ReportCategory.other,
          ),
          DraftAttachment(path: path, kind: MediaKind.video, mime: mime),
        );
    ref.read(urgentMediaReportsProvider.notifier).add(uuid);
    return uuid;
  }
}

final liveControllerProvider = NotifierProvider<LiveController, LiveState>(
  LiveController.new,
);
