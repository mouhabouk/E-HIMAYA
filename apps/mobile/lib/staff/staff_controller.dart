import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/connectivity/connectivity.dart';
import '../core/http/models.dart';
import '../core/location/location_service.dart';
import '../core/logging/log.dart';
import '../core/storage/secure_store.dart';
import '../features/report/sms_fallback.dart' show normalizeSmsNumber, smsUri;
import 'mission_box.dart';
import 'staff_api.dart';
import 'staff_auth.dart';
import 'staff_config.dart';
import 'staff_models.dart';
import 'staff_push.dart';
import 'staff_sms.dart';

final _log = logger('staff');

final staffConfigProvider = Provider<StaffConfig>(
  (ref) => StaffConfig.fromEnvironment(),
);

final staffDioProvider = Provider<Dio>(
  (ref) => Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
    ),
  ),
);

final staffAuthProvider = Provider<StaffAuth>(
  (ref) =>
      StaffAuth(ref.watch(staffConfigProvider), ref.watch(staffDioProvider)),
);

final staffVaultProvider = Provider<StaffVault>(
  (ref) => StaffVault(ref.watch(secureStoreProvider)),
);

final staffApiProvider = Provider<StaffApi>(
  (ref) => StaffApi(
    ref.watch(staffDioProvider),
    ref.watch(staffAuthProvider),
    ref.watch(staffVaultProvider),
  ),
);

/// `android` or `ios`, sent when the phone is registered.
final staffPlatformProvider = Provider<String>(
  (ref) => defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android',
);

enum StaffPhase {
  loading,
  signedOut,
  signingIn,
  setPin,
  locked,
  noShift,
  onShift,

  /// An inspector without the team leader role: the prevention visits (phase P4c).
  prevention,

  /// Phase F: an agent activated with a code reads and accepts the charter first.
  charter,
}

/// Phase F: a step recorded by the long press, kept on the phone for the undo window before it
/// is written with the time of the press.
@immutable
class StagedStep {
  const StagedStep({
    required this.missionId,
    required this.step,
    required this.at,
    required this.deadline,
    this.position,
  });

  final String missionId;

  /// `en_route`, `on_scene`, `left_scene`, `at_hospital`, `available` or `back_at_unit`.
  final String step;
  final DateTime at;
  final DateTime deadline;
  final GeoPoint? position;
}

/// Why the phone came back to the sign-in screen.
enum SignOutReason { none, wiped, pinFailures, refused, expired }

@immutable
class StaffState {
  const StaffState({
    this.phase = StaffPhase.loading,
    this.code,
    this.me,
    this.missions = const [],
    this.reason = SignOutReason.none,
    this.pinError = false,
    this.pinTriesLeft = StaffConfig.maxPinFailures,
    this.offline = false,
    this.busy = false,
    this.error,
    this.lastSync,
    this.outbox = const [],
    this.syncing = false,
    this.smsCapable = false,
    this.staged,
    this.activation,
  });

  final StaffPhase phase;
  final DeviceCode? code;
  final CrewMe? me;
  final List<Mission> missions;
  final SignOutReason reason;
  final bool pinError;
  final int pinTriesLeft;

  /// The last call failed for lack of network: what is shown is the last copy.
  final bool offline;
  final bool busy;

  /// Error code of the last write the server refused (`not_on_scene`, ...).
  final String? error;

  /// When the server last answered (the connection strip's "updated N s ago").
  final DateTime? lastSync;

  /// The writes kept on the phone until the server has them, in order (phase P4d, design §9.1).
  final List<MissionWrite> outbox;
  final bool syncing;

  /// A gateway number and the phone's key: the steps and alerts that wait can go by SMS.
  final bool smsCapable;

  /// Phase F: the step waiting for its undo window to pass.
  final StagedStep? staged;

  /// Phase F: why the last activation was refused (`activation_refused`, `activation_expired`,
  /// `network`, `rate_limited`).
  final String? activation;

  int get pending => outbox.length;

  /// The writes that can still go by text message («أرسل برسالة قصيرة», design §9.3).
  List<MissionWrite> get smsWaiting => [
    for (final w in outbox)
      if (w.smsEvent != null && w.smsAt == null) w,
  ];

  /// Whether [missionId] has writes waiting (the mission card shows «في الانتظار»).
  bool waiting(String missionId) => outbox.any((w) => w.missionId == missionId);

  Mission? mission(String id) {
    for (final m in missions) {
      if (m.id == id) return m;
    }
    return null;
  }

  /// The oldest mission still waiting for its acknowledgement (full-screen alert).
  Mission? get ringing {
    Mission? first;
    for (final m in missions) {
      if (m.unacknowledged &&
          (first == null || m.createdAt.isBefore(first.createdAt))) {
        first = m;
      }
    }
    return first;
  }

  StaffState copyWith({
    StaffPhase? phase,
    DeviceCode? code,
    CrewMe? me,
    List<Mission>? missions,
    SignOutReason? reason,
    bool? pinError,
    int? pinTriesLeft,
    bool? offline,
    bool? busy,
    String? error,
    DateTime? lastSync,
    List<MissionWrite>? outbox,
    bool? syncing,
    bool? smsCapable,
    StagedStep? staged,
    String? activation,
    bool clearError = false,
    bool clearCode = false,
    bool clearStaged = false,
    bool clearActivation = false,
  }) => StaffState(
    phase: phase ?? this.phase,
    code: clearCode ? null : code ?? this.code,
    me: me ?? this.me,
    missions: missions ?? this.missions,
    reason: reason ?? this.reason,
    pinError: pinError ?? this.pinError,
    pinTriesLeft: pinTriesLeft ?? this.pinTriesLeft,
    offline: offline ?? this.offline,
    busy: busy ?? this.busy,
    error: clearError ? null : error ?? this.error,
    lastSync: lastSync ?? this.lastSync,
    outbox: outbox ?? this.outbox,
    syncing: syncing ?? this.syncing,
    smsCapable: smsCapable ?? this.smsCapable,
    staged: clearStaged ? null : staged ?? this.staged,
    activation: clearActivation ? null : activation ?? this.activation,
  );
}

/// The whole staff app: sign-in with the device grant, the PIN lock, the shift and its missions.
class StaffController extends Notifier<StaffState> {
  Timer? _poll;
  Timer? _signIn;
  Timer? _retry;
  Timer? _undo;
  int _signInRun = 0;
  StreamSubscription<bool>? _online;
  StreamSubscription<GeoPoint>? _tracking;
  final _pushSubs = <StreamSubscription<Object?>>[];
  bool _pushStarted = false;

  /// The server's last copy of each mission; what is shown is this with the waiting writes on it.
  List<Map<String, dynamic>> _server = const [];
  bool _restored = false;
  Future<void>? _syncing;
  Future<void> _saved = Future.value();

  /// Writes the server refused during the last send, by id, with its error code.
  final _refused = <String, String>{};

  /// The last position kept for each mission (one every 30 s on the way, 2 min on scene).
  final _lastKept = <String, DateTime>{};

  /// The texts of the tracking notification and of the mission channel, in the leader's
  /// language; set by the missions screen.
  ({String title, String text, String channel}) labels = (
    title: 'e-Himaya',
    text: '',
    channel: 'e-Himaya',
  );

  StaffApi get _api => ref.read(staffApiProvider);
  StaffVault get _vault => ref.read(staffVaultProvider);
  MissionBox get _box => ref.read(missionBoxProvider);

  @override
  StaffState build() {
    _online = ref
        .read(connectivityProvider)
        .onlineChanges
        .listen((up) => up ? unawaited(sync()) : null);
    _retry = Timer.periodic(StaffConfig.retryEvery, (_) {
      if (state.pending > 0) unawaited(sync());
    });
    ref.onDispose(() {
      _poll?.cancel();
      _signIn?.cancel();
      _retry?.cancel();
      _undo?.cancel();
      unawaited(_online?.cancel());
      unawaited(_tracking?.cancel());
      for (final sub in _pushSubs) {
        unawaited(sub.cancel());
      }
    });
    unawaited(_init());
    return const StaffState();
  }

  Future<void> _init() async {
    if (await _vault.tokens() == null || await _vault.deviceId() == null) {
      state = const StaffState(phase: StaffPhase.signedOut);
    } else if (!await _vault.hasPin()) {
      state = const StaffState(phase: StaffPhase.setPin);
    } else {
      state = const StaffState(phase: StaffPhase.locked);
    }
  }

  // ------------------------------------------------------------------ sign-in

  Future<void> signIn() async {
    final run = ++_signInRun;
    state = state.copyWith(
      busy: true,
      clearError: true,
      reason: SignOutReason.none,
    );
    try {
      final code = await ref.read(staffAuthProvider).start();
      if (run != _signInRun) return;
      state = StaffState(phase: StaffPhase.signingIn, code: code);
      _schedulePoll(run, code, code.interval);
    } on Object catch (e, st) {
      _log.warning('device authorization failed', e, st);
      state = state.copyWith(busy: false, offline: true);
    }
  }

  /// Phase F: the agent's professional number and the one-time code the room chief gave.
  Future<void> activate(String matricule, String code) async {
    state = state.copyWith(busy: true, clearActivation: true, clearError: true);
    try {
      final a = await ref
          .read(staffAuthProvider)
          .activate(
            matricule: matricule,
            code: code,
            platform: ref.read(staffPlatformProvider),
            pushToken: await _pushToken(),
          );
      await _vault.saveTokens(a.tokens);
      await _vault.saveDeviceId(a.deviceId);
      state = const StaffState(phase: StaffPhase.setPin);
    } on ActivationRefused catch (e) {
      state = state.copyWith(
        busy: false,
        activation: e.code,
        offline: e.code == 'network',
      );
    }
  }

  /// Phase F: the charter read and accepted, with the consent to text messages and location.
  Future<bool> acceptCharter({
    required String version,
    required bool sms,
    required bool location,
  }) async {
    state = state.copyWith(busy: true, clearError: true);
    final ok = await _guard(() async {
      await _api.acceptCharter(version: version, sms: sms, location: location);
      return true;
    });
    state = state.copyWith(busy: false);
    if (ok == true) await refresh();
    return ok == true;
  }

  void cancelSignIn() {
    _signInRun++;
    _signIn?.cancel();
    state = const StaffState(phase: StaffPhase.signedOut);
  }

  void _schedulePoll(int run, DeviceCode code, Duration wait) {
    _signIn?.cancel();
    _signIn = Timer(wait, () => unawaited(_pollOnce(run, code, wait)));
  }

  Future<void> _pollOnce(int run, DeviceCode code, Duration wait) async {
    if (run != _signInRun) return;
    PollResult result;
    try {
      result = await ref.read(staffAuthProvider).poll(code);
    } on Object catch (e) {
      _log.info('sign-in poll failed: $e');
      result = const PollResult(PollOutcome.pending);
    }
    if (run != _signInRun) return;
    switch (result.outcome) {
      case PollOutcome.pending:
        if (DateTime.now().isAfter(code.expiresAt)) {
          state = const StaffState(
            phase: StaffPhase.signedOut,
            reason: SignOutReason.expired,
          );
        } else {
          _schedulePoll(run, code, wait);
        }
      case PollOutcome.slowDown:
        _schedulePoll(run, code, wait + const Duration(seconds: 5));
      case PollOutcome.denied:
        state = const StaffState(
          phase: StaffPhase.signedOut,
          reason: SignOutReason.refused,
        );
      case PollOutcome.expired:
        state = const StaffState(
          phase: StaffPhase.signedOut,
          reason: SignOutReason.expired,
        );
      case PollOutcome.granted:
        await _vault.saveTokens(result.tokens!);
        try {
          final id = await _api.registerDevice(
            platform: ref.read(staffPlatformProvider),
            pushToken: await _pushToken(),
          );
          await _vault.saveDeviceId(id);
          state = const StaffState(phase: StaffPhase.setPin);
        } on Object catch (e, st) {
          _log.warning('device registration failed', e, st);
          await _vault.wipe();
          state = StaffState(
            phase: StaffPhase.signedOut,
            reason: e is StaffSignedOut || e is CrewError
                ? SignOutReason.refused
                : SignOutReason.none,
            offline: e is DioException,
          );
        }
    }
  }

  // ------------------------------------------------------------------ PIN

  Future<void> setPin(String pin) async {
    final rnd = Random.secure();
    final salt = [
      for (var i = 0; i < 16; i++)
        rnd.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ].join();
    await _vault.setPin(pin, salt);
    await refresh();
  }

  Future<void> unlock(String pin) async {
    if (await _vault.checkPin(pin)) {
      state = state.copyWith(
        pinError: false,
        pinTriesLeft: StaffConfig.maxPinFailures,
      );
      await refresh();
      return;
    }
    if (!await _vault.hasPin()) {
      _stop();
      await _erase();
      state = const StaffState(
        phase: StaffPhase.signedOut,
        reason: SignOutReason.pinFailures,
      );
      return;
    }
    state = state.copyWith(
      pinError: true,
      pinTriesLeft: StaffConfig.maxPinFailures - await _vault.failures(),
    );
  }

  /// Called after [StaffConfig.lockAfter] in the background: the PIN is asked again.
  void lock() {
    if (state.phase == StaffPhase.noShift ||
        state.phase == StaffPhase.onShift ||
        state.phase == StaffPhase.prevention ||
        state.phase == StaffPhase.charter) {
      _poll?.cancel();
      state = state.copyWith(phase: StaffPhase.locked, pinError: false);
    }
  }

  Future<void> signOut() async {
    _stop();
    await _vault.wipe();
    await _erase();
    state = const StaffState(phase: StaffPhase.signedOut);
  }

  void _stop() {
    _poll?.cancel();
    _signIn?.cancel();
    _signInRun++;
    _stopTracking();
  }

  /// The missions, the writes that wait and the positions: nothing stays on the phone.
  Future<void> _erase() async {
    _server = const [];
    _restored = false;
    _refused.clear();
    _lastKept.clear();
    await (_saved = _saved.then((_) => _box.wipe()));
  }

  // ------------------------------------------------------------------ shift and missions

  /// Runs a call; a revoked phone or a refused sign-in erases everything, a network error keeps
  /// the last copy and shows the offline strip. Returns null on failure.
  Future<T?> _guard<T>(Future<T> Function() call) async {
    try {
      final out = await call();
      state = state.copyWith(offline: false, lastSync: DateTime.now());
      return out;
    } on DeviceRevoked catch (e) {
      await forceSignOut(e);
    } on StaffSignedOut catch (e) {
      await forceSignOut(e);
    } on CrewError catch (e) {
      state = state.copyWith(error: e.code, busy: false);
    } on Object catch (e) {
      _log.info('staff call failed: $e');
      state = state.copyWith(offline: true, busy: false);
    }
    return null;
  }

  /// A revoked phone ([DeviceRevoked]) or a refused sign-in: everything on the phone is erased.
  Future<void> forceSignOut(Object why) async {
    _stop();
    await _vault.wipe();
    await _erase();
    state = StaffState(
      phase: StaffPhase.signedOut,
      reason: why is DeviceRevoked
          ? SignOutReason.wiped
          : SignOutReason.refused,
    );
  }

  /// Another part of the app reached the server, or did not (the connection strip).
  void network({required bool ok}) => state = ok
      ? state.copyWith(offline: false, lastSync: DateTime.now())
      : state.copyWith(offline: true);

  static bool _inspectorOnly(List<String> roles) =>
      roles.contains('org_auditor') && !roles.contains('team_leader');

  /// The missions and the writes kept on the phone, once after unlocking: the shift goes on
  /// without network with the last copy (design §9.1).
  Future<CrewMe?> _restore() async {
    if (_restored) return null;
    _restored = true;
    final cache = await _box.cache();
    final outbox = await _box.outbox();
    _server = cache?.missions ?? const [];
    final me = cache?.me == null ? null : CrewMe.fromJson(cache!.me!);
    state = state.copyWith(
      outbox: outbox,
      missions: _shown(outbox),
      smsCapable:
          normalizeSmsNumber(ref.read(staffConfigProvider).smsNumber) != null &&
          await _vault.smsKey() != null,
    );
    return me;
  }

  /// The server's missions with the waiting writes applied, newest data first.
  List<Mission> _shown([List<MissionWrite>? outbox]) {
    final waiting = outbox ?? state.outbox;
    return [
      for (final m in _server)
        Mission.fromJson(
          waiting.where((w) => w.missionId == m['id']).fold(m, applyLocally),
        ),
    ];
  }

  void _keep() {
    final cache = MissionCache(me: state.me?.json, missions: _server);
    final outbox = state.outbox;
    _saved = _saved
        .then((_) async {
          await _box.saveCache(cache);
          await _box.saveOutbox(outbox);
        })
        .catchError((Object e) => _log.warning('missions not kept: $e'));
  }

  Future<void> refresh() async {
    final kept = await _restore();
    final me = await _guard(_api.me);
    if (me == null) {
      if (state.phase == StaffPhase.setPin ||
          state.phase == StaffPhase.locked) {
        // Unlocked without network: the shift screen (or the visits kept on the phone) with
        // the offline strip.
        final known = state.me ?? kept;
        final roles = known?.roles ?? await _vault.roles();
        state = state.copyWith(
          me: known,
          phase: _inspectorOnly(roles)
              ? StaffPhase.prevention
              : known?.shift == null
              ? StaffPhase.noShift
              : StaffPhase.onShift,
        );
        _track();
      }
      return;
    }
    await _vault.saveRoles(me.roles);
    if (me.activatedAgent && !me.charterAccepted) {
      _poll?.cancel();
      state = state.copyWith(phase: StaffPhase.charter, me: me);
      return;
    }
    if (_inspectorOnly(me.roles)) {
      _poll?.cancel();
      state = state.copyWith(phase: StaffPhase.prevention, me: me);
      return;
    }
    unawaited(_startPush());
    unawaited(_fetchSmsKey());
    if (me.shift == null) {
      _poll?.cancel();
      _server = const [];
      state = state.copyWith(
        phase: StaffPhase.noShift,
        me: me,
        missions: const [],
      );
      _keep();
      _track();
      unawaited(sync());
      return;
    }
    state = state.copyWith(phase: StaffPhase.onShift, me: me);
    await poll();
    _poll?.cancel();
    _poll = Timer.periodic(StaffConfig.pollEvery, (_) => unawaited(poll()));
  }

  /// Fetches the missions (also on a push "mission"); what waits is sent first.
  Future<void> poll() async {
    if (state.phase != StaffPhase.onShift) return;
    await sync();
    final missions = await _guard(_api.missions);
    if (missions != null && state.phase == StaffPhase.onShift) {
      _server = [for (final m in missions) m.json];
      state = state.copyWith(missions: _shown());
      _keep();
    }
    _track();
  }

  Future<List<CrewVehicle>> vehicles() async =>
      await _guard(_api.vehicles) ?? const [];

  Future<bool> startShift(
    CrewVehicle v,
    int crewSize,
    String? names, {
    List<String> crewAgentIds = const [],
  }) async {
    state = state.copyWith(busy: true, clearError: true);
    final shift = await _guard(
      () => _api.startShift(v.id, crewSize, names, crewAgentIds: crewAgentIds),
    );
    state = state.copyWith(busy: false);
    if (shift == null) return false;
    await refresh();
    return true;
  }

  Future<bool> endShift() async {
    state = state.copyWith(busy: true, clearError: true);
    final ok = await _guard(() async {
      await _api.endShift();
      return true;
    });
    state = state.copyWith(busy: false);
    if (ok == true) await refresh();
    return ok == true;
  }

  // ------------------------------------------------------------------ writes kept on the phone

  /// A write of a mission: shown at once, kept sealed in order, then sent. False only when the
  /// server refused it (its reason in [StaffState.error]); without network it waits and is true.
  Future<bool> _write(
    String missionId,
    String action,
    Map<String, dynamic> body, {
    CapturedMedia? media,
    Map<String, dynamic> shown = const {},
    DateTime? at,
  }) async {
    final w = _api.write(
      missionId,
      action,
      body,
      mediaType: media?.contentType,
      shown: shown,
      at: at,
    );
    if (media != null) await _box.saveMedia(w.id, media.bytes);
    final outbox = [...state.outbox, w];
    state = state.copyWith(
      outbox: outbox,
      missions: _shown(outbox),
      clearError: true,
    );
    _keep();
    _track();
    await sync();
    // Added while another send was finishing: one more pass.
    if (state.outbox.contains(w) && !state.offline) await sync();
    return _refused.remove(w.id) == null;
  }

  /// Sends what waits, oldest first; stops at the first network error (tried again every 30 s
  /// and when the network comes back). A write the server refuses is dropped and its reason
  /// shown; the mission shows the server's copy again.
  Future<void> sync() =>
      _syncing ??= _sync().whenComplete(() => _syncing = null);

  Future<void> _sync() async {
    if (state.outbox.isEmpty && !await _hasPositions()) return;
    state = state.copyWith(syncing: true);
    try {
      while (state.outbox.isNotEmpty) {
        final w = state.outbox.first;
        final media = w.mediaType == null ? null : await _box.media(w.id);
        Mission? m;
        if (w.mediaType == null || media != null) {
          try {
            m = await _api.send(w, media: media);
            network(ok: true);
          } on DeviceRevoked catch (e) {
            await forceSignOut(e);
            return;
          } on StaffSignedOut catch (e) {
            await forceSignOut(e);
            return;
          } on CrewError catch (e) {
            if (e.status >= 500 || e.status == 429) {
              network(ok: false);
              return;
            }
            _log.info('write refused: ${w.action} ${e.code}');
            _refused[w.id] = e.code;
            state = state.copyWith(error: e.code);
          } on Object catch (e) {
            _log.info('write not sent: $e');
            network(ok: false);
            return;
          }
        }
        if (m != null) {
          final json = m.json;
          final known = _server.any((x) => x['id'] == m!.id);
          _server = [
            for (final x in _server) x['id'] == m.id ? json : x,
            if (!known) json,
          ];
        }
        final outbox = [
          for (final x in state.outbox)
            if (x.id != w.id) x,
        ];
        state = state.copyWith(outbox: outbox, missions: _shown(outbox));
        _keep();
        if (w.mediaType != null) await _box.deleteMedia(w.id);
      }
      await _sendPositions();
    } finally {
      state = state.copyWith(syncing: false);
      _track();
    }
  }

  Future<bool> acknowledge(String id) => _write(id, 'ack', const {});

  /// Next step of the mission, with the phone's position when one comes quickly.
  Future<bool> step(String id, String status, {GeoPoint? at}) => _write(
    id,
    'status',
    {'status': status, 'lat': ?at?.lat, 'lon': ?at?.lon},
  );

  /// Left the scene, at the hospital, back at the unit (phase S2): the phone's time, kept in order
  /// by the server; back at the unit ends the mission.
  Future<bool> milestone(String id, String step) =>
      _write(id, 'milestone', {'step': step});

  /// The crew and what the mission used (phase S2).
  Future<bool> teamRecord(
    String id, {
    required int crewCount,
    required Map<String, int> consumables,
  }) => _write(id, 'record', {
    'crew_count': crewCount,
    'consumables': {
      for (final e in consumables.entries)
        if (e.value > 0) e.key: e.value,
    },
  });

  /// Situation report (design §5.5); backup chips mean "backup needed".
  Future<bool> situation(
    String id, {
    required ReportCategory category,
    required int severity,
    List<String> backupKinds = const [],
  }) => _write(id, 'situation', {
    'category': category.wire,
    'severity': severity,
    'backup_needed': backupKinds.isNotEmpty,
    'backup_kinds': backupKinds,
    'crew_danger': false,
  });

  Future<bool> count(String id, CasualtyCounter c, int delta) =>
      _write(id, 'casualties', {c.wire: delta});

  /// One person taken to hospital: a hospital of the map ([hospitalRef], shown by [hospital]
  /// while it waits) or a typed name.
  Future<bool> transport(
    String id, {
    required Triage triage,
    required AgeBand ageBand,
    required Sex sex,
    String? hospitalRef,
    String? hospital,
  }) => _write(
    id,
    'transports',
    {
      'triage': triage.name,
      'age_band': ageBand.wire,
      'sex': sex.name,
      'hospital_ref': ?hospitalRef,
      if (hospitalRef == null) 'hospital': hospital?.trim(),
    },
    shown: {'hospital': ?hospital?.trim()},
  );

  /// "Backup" or "danger to the crew", with the chips chosen (design §5.4).
  Future<bool> alert(String id, String kind, List<String> items) =>
      _write(id, 'alerts', {'kind': kind, 'items': items});

  Future<bool> note(String id, String body) =>
      _write(id, 'notes', {'body': body.trim()});

  /// A photo or a voice note, sealed on the phone until it is sent.
  Future<bool> upload(String id, String kind, CapturedMedia media) => _write(
    id,
    'attachments',
    {'kind': kind, 'duration_s': ?media.durationS},
    media: media,
  );

  Future<bool> detailedReport(
    String id,
    String templateId,
    Map<String, Object> answers,
    String? note,
  ) => _write(id, 'detailed-report', {
    'template_id': templateId,
    'answers': answers,
    if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
  });

  // ------------------------------------------------------------------ the mission flow (phase F)

  /// The step given by the long press on the round button: shown at once with an undo bar, and
  /// written after the room's undo window with the time of the press.
  void stage(String missionId, String step, {GeoPoint? at}) {
    final now = DateTime.now();
    final seconds = state.me?.undoSeconds ?? 10;
    _undo?.cancel();
    final previous = state.staged;
    if (previous != null) unawaited(_commit(previous));
    final staged = StagedStep(
      missionId: missionId,
      step: step,
      at: now,
      deadline: now.add(Duration(seconds: seconds)),
      position: at,
    );
    if (seconds <= 0) {
      unawaited(_commit(staged));
      return;
    }
    state = state.copyWith(staged: staged);
    _undo = Timer(Duration(seconds: seconds), () {
      final s = state.staged;
      if (s != null && identical(s, staged)) unawaited(_commit(s));
    });
  }

  /// «تراجع»: the step is forgotten, nothing was sent.
  void undo() {
    _undo?.cancel();
    state = state.copyWith(clearStaged: true);
  }

  Future<bool> _commit(StagedStep s) async {
    if (identical(state.staged, s)) state = state.copyWith(clearStaged: true);
    return s.step == 'en_route' || s.step == 'on_scene'
        ? _write(s.missionId, 'status', {
            'status': s.step,
            'lat': ?s.position?.lat,
            'lon': ?s.position?.lon,
          }, at: s.at)
        : _write(s.missionId, 'milestone', {'step': s.step}, at: s.at);
  }

  /// The nature the leader confirmed or corrected (the room's category is chosen first).
  Future<bool> nature(String id, String nature) =>
      _write(id, 'nature', {'nature': nature});

  /// «تجاوز المرحلة»: the hospital or the stop on the way back is not needed, with why.
  Future<bool> skip(String id, String step, String reason) =>
      _write(id, 'skip', {'step': step, 'reason': reason});

  /// «بدون تدخل», after the double confirmation.
  Future<bool> endWithout(String id, String reason) =>
      _write(id, 'no-intervention', {'reason': reason});

  /// The toll at the end: the material damage and the description, typed or spoken and corrected
  /// ([voiceId] names the transcript it was corrected from).
  Future<bool> toll(
    String id, {
    required String damage,
    String? description,
    String? voiceId,
  }) {
    final text = description?.trim() ?? '';
    return _write(id, 'toll', {
      'damage': damage,
      if (text.isNotEmpty) ...{'description': text, 'voice_id': ?voiceId},
    });
  }

  /// The intervention report (محضر التدخل), from the mission's page.
  Future<bool> interventionReport(String id, String text, {String? voiceId}) =>
      _write(id, 'report', {'text': text.trim(), 'voice_id': ?voiceId});

  /// A spoken toll or report sent to be transcribed (needs network; the audio is not kept).
  Future<SpokenText?> transcribe(String id, CapturedMedia media, String lang) =>
      _guard(() => _api.transcribe(id, media, lang: lang));

  /// A mission the team opens from the field (needs network: the room must know at once).
  Future<Mission?> openMission({
    required String nature,
    required GeoPoint at,
    String? note,
  }) async {
    state = state.copyWith(busy: true, clearError: true);
    final m = await _guard(
      () => _api.openMission(
        nature: nature,
        lat: at.lat,
        lon: at.lon,
        note: note,
      ),
    );
    state = state.copyWith(busy: false);
    if (m != null) {
      _server = [m.json, ..._server.where((x) => x['id'] != m.id)];
      state = state.copyWith(missions: _shown());
      _keep();
    }
    return m;
  }

  /// The activated agents the leader can put on the shift (empty offline).
  Future<List<CrewAgent>> crewAgents() async =>
      await _guard(_api.crewAgents) ?? const [];

  /// The nearest hospitals of the map, for the transport chips (empty offline).
  Future<List<Hospital>> hospitals(String id) async =>
      await _guard(() => _api.hospitals(id)) ?? const [];

  void clearError() => state = state.copyWith(clearError: true);

  // ------------------------------------------------------------------ text messages (design §9.3)

  /// The phone's key for its text messages, fetched once while there is network.
  Future<void> _fetchSmsKey() async {
    if (normalizeSmsNumber(ref.read(staffConfigProvider).smsNumber) == null) {
      return;
    }
    if (await _vault.smsKey() == null) {
      try {
        await _vault.saveSmsKey(await _api.smsKey());
      } on Object catch (e) {
        _log.info('no sms key yet: $e');
        return;
      }
    }
    state = state.copyWith(smsCapable: true);
  }

  /// Opens the SMS app with the oldest step or alert that waits, signed with the phone's key;
  /// the leader presses Send. The write stays queued: sent again over the internet, it is
  /// applied once.
  Future<bool> sendBySms(Future<bool> Function(Uri) open) async {
    final number = normalizeSmsNumber(ref.read(staffConfigProvider).smsNumber);
    final key = await _vault.smsKey();
    final device = await _vault.deviceId();
    final waiting = state.smsWaiting;
    if (number == null || key == null || device == null || waiting.isEmpty) {
      return false;
    }
    final w = waiting.first;
    final body = crewSmsBody(key: key, deviceId: device, write: w);
    if (body == null || !await open(smsUri(number, body))) return false;
    final outbox = [
      for (final x in state.outbox)
        x.id == w.id ? x.sentBySms(DateTime.now()) : x,
    ];
    state = state.copyWith(outbox: outbox);
    _keep();
    return true;
  }

  // ------------------------------------------------------------------ tracking (design §9.2)

  void _stopTracking() {
    unawaited(_tracking?.cancel());
    _tracking = null;
  }

  /// The vehicle's position is followed while a mission is on the way or on scene (a foreground
  /// service with its notification on Android), and stops after.
  void _track() {
    final moving =
        state.phase == StaffPhase.onShift &&
        state.missions.any(
          (m) =>
              m.status == MissionStatus.enRoute ||
              m.status == MissionStatus.onScene,
        );
    if (!moving) {
      _stopTracking();
      return;
    }
    _tracking ??= ref
        .read(locationServiceProvider)
        .follow(title: labels.title, text: labels.text)
        .listen((p) => unawaited(_position(p)));
  }

  Future<void> _position(GeoPoint p) async {
    final now = DateTime.now();
    final points = <QueuedPosition>[];
    for (final m in state.missions) {
      final every = switch (m.status) {
        MissionStatus.enRoute => StaffConfig.trackEnRoute,
        MissionStatus.onScene => StaffConfig.trackOnScene,
        _ => null,
      };
      final last = _lastKept[m.id];
      if (every == null || (last != null && now.difference(last) < every)) {
        continue;
      }
      _lastKept[m.id] = now;
      points.add(QueuedPosition(m.id, p.lat, p.lon, now, p.accuracyM));
    }
    if (points.isEmpty) return;
    await (_saved = _saved.then((_) async {
      await _box.savePositions([...await _box.positions(), ...points]);
    }));
    unawaited(sync());
  }

  Future<bool> _hasPositions() async {
    await _saved;
    return (await _box.positions()).isNotEmpty;
  }

  /// The positions kept, mission by mission, 50 at a time.
  Future<void> _sendPositions() async {
    await _saved;
    var left = await _box.positions();
    while (left.isNotEmpty) {
      final id = left.first.missionId;
      final batch = left.where((p) => p.missionId == id).take(50).toList();
      try {
        await _api.positions(id, batch);
      } on CrewError catch (e) {
        // A mission that ended or is not this leader's: its positions are dropped.
        if (e.status >= 500) return;
      } on DeviceRevoked catch (e) {
        await forceSignOut(e);
        return;
      } on StaffSignedOut catch (e) {
        await forceSignOut(e);
        return;
      } on Object {
        return;
      }
      final sent = {for (final p in batch) p.key};
      await (_saved = _saved.then((_) async {
        left = [
          for (final p in await _box.positions())
            if (!sent.contains(p.key)) p,
        ];
        await _box.savePositions(left);
      }));
    }
  }

  // ------------------------------------------------------------------ push (design §9.4)

  Future<String?> _pushToken() async {
    try {
      return await ref.read(staffPushProvider).start(labels.channel);
    } on Object {
      return null;
    }
  }

  /// The phone's push token reaches the server once per launch and when it changes; a mission
  /// push in the foreground fetches the missions at once.
  Future<void> _startPush() async {
    if (_pushStarted) return;
    _pushStarted = true;
    final push = ref.read(staffPushProvider);
    final token = await _pushToken();
    if (token != null) {
      await _guard(() => _api.updatePushToken(token));
    }
    _pushSubs
      ..add(
        push.onTokenRefresh.listen(
          (t) => unawaited(_guard(() => _api.updatePushToken(t))),
        ),
      )
      ..add(push.onMission.listen((_) => unawaited(poll())));
  }
}

final staffControllerProvider = NotifierProvider<StaffController, StaffState>(
  StaffController.new,
);

/// Distance in metres between two points (haversine).
double distanceM(GeoPoint a, GeoPoint b) {
  const r = 6371000.0;
  double rad(double d) => d * pi / 180;
  final dLat = rad(b.lat - a.lat);
  final dLon = rad(b.lon - a.lon);
  final h =
      pow(sin(dLat / 2), 2) +
      cos(rad(a.lat)) * cos(rad(b.lat)) * pow(sin(dLon / 2), 2);
  return 2 * r * asin(sqrt(h));
}

/// The phone's position now, for the on-scene suggestion (null without permission or fix).
final staffPositionProvider = FutureProvider.autoDispose<GeoPoint?>(
  (ref) => ref.read(locationServiceProvider).bestEffort(),
);
