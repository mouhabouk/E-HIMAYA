import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/http/models.dart';
import '../core/location/location_service.dart';
import '../core/logging/log.dart';
import '../core/storage/secure_store.dart';
import 'staff_api.dart';
import 'staff_auth.dart';
import 'staff_config.dart';
import 'staff_models.dart';

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
    bool clearError = false,
    bool clearCode = false,
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
  );
}

/// The whole staff app: sign-in with the device grant, the PIN lock, the shift and its missions.
class StaffController extends Notifier<StaffState> {
  Timer? _poll;
  Timer? _signIn;
  int _signInRun = 0;

  StaffApi get _api => ref.read(staffApiProvider);
  StaffVault get _vault => ref.read(staffVaultProvider);

  @override
  StaffState build() {
    ref.onDispose(() {
      _poll?.cancel();
      _signIn?.cancel();
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
        state.phase == StaffPhase.onShift) {
      _poll?.cancel();
      state = state.copyWith(phase: StaffPhase.locked, pinError: false);
    }
  }

  Future<void> signOut() async {
    _stop();
    await _vault.wipe();
    state = const StaffState(phase: StaffPhase.signedOut);
  }

  void _stop() {
    _poll?.cancel();
    _signIn?.cancel();
    _signInRun++;
  }

  // ------------------------------------------------------------------ shift and missions

  /// Runs a call; a revoked phone or a refused sign-in erases everything, a network error keeps
  /// the last copy and shows the offline strip. Returns null on failure.
  Future<T?> _guard<T>(Future<T> Function() call) async {
    try {
      final out = await call();
      if (state.offline) state = state.copyWith(offline: false);
      return out;
    } on DeviceRevoked {
      _stop();
      await _vault.wipe();
      state = const StaffState(
        phase: StaffPhase.signedOut,
        reason: SignOutReason.wiped,
      );
    } on StaffSignedOut {
      _stop();
      await _vault.wipe();
      state = const StaffState(
        phase: StaffPhase.signedOut,
        reason: SignOutReason.refused,
      );
    } on CrewError catch (e) {
      state = state.copyWith(error: e.code, busy: false);
    } on Object catch (e) {
      _log.info('staff call failed: $e');
      state = state.copyWith(offline: true, busy: false);
    }
    return null;
  }

  Future<void> refresh() async {
    final me = await _guard(_api.me);
    if (me == null) {
      if (state.phase == StaffPhase.setPin ||
          state.phase == StaffPhase.locked) {
        // Unlocked without network: the shift screen shows the offline strip.
        state = state.copyWith(
          phase: state.me?.shift == null
              ? StaffPhase.noShift
              : StaffPhase.onShift,
        );
      }
      return;
    }
    if (me.shift == null) {
      _poll?.cancel();
      state = state.copyWith(
        phase: StaffPhase.noShift,
        me: me,
        missions: const [],
      );
      return;
    }
    state = state.copyWith(phase: StaffPhase.onShift, me: me);
    await poll();
    _poll?.cancel();
    _poll = Timer.periodic(StaffConfig.pollEvery, (_) => unawaited(poll()));
  }

  /// Fetches the missions (also on a push "mission").
  Future<void> poll() async {
    if (state.phase != StaffPhase.onShift) return;
    final missions = await _guard(_api.missions);
    if (missions != null && state.phase == StaffPhase.onShift) {
      state = state.copyWith(missions: missions);
    }
  }

  Future<List<CrewVehicle>> vehicles() async =>
      await _guard(_api.vehicles) ?? const [];

  Future<bool> startShift(CrewVehicle v, int crewSize, String? names) async {
    state = state.copyWith(busy: true, clearError: true);
    final shift = await _guard(() => _api.startShift(v.id, crewSize, names));
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

  Future<bool> _write(Future<Mission> Function() call) async {
    state = state.copyWith(busy: true, clearError: true);
    final m = await _guard(call);
    if (m == null) {
      state = state.copyWith(busy: false);
      return false;
    }
    state = state.copyWith(
      busy: false,
      missions: [
        for (final x in state.missions) x.id == m.id ? m : x,
        if (state.mission(m.id) == null) m,
      ],
    );
    return true;
  }

  Future<bool> acknowledge(String id) => _write(() => _api.acknowledge(id));

  /// Next step of the mission, with the phone's position when one comes quickly.
  Future<bool> step(String id, String status, {GeoPoint? at}) =>
      _write(() => _api.step(id, status, lat: at?.lat, lon: at?.lon));

  Future<bool> firstReport(
    String id, {
    required ReportCategory category,
    required int severity,
    bool backupNeeded = false,
    String? backupNote,
    bool crewDanger = false,
  }) => _write(
    () => _api.firstReport(
      id,
      category: category.wire,
      severity: severity,
      backupNeeded: backupNeeded,
      backupNote: backupNote,
      crewDanger: crewDanger,
    ),
  );

  Future<bool> count(String id, CasualtyCounter c, int delta) =>
      _write(() => _api.casualties(id, {c: delta}));

  Future<bool> transport(
    String id, {
    required Triage triage,
    required AgeBand ageBand,
    required Sex sex,
    required String hospital,
  }) => _write(
    () => _api.transport(
      id,
      triage: triage,
      ageBand: ageBand,
      sex: sex,
      hospital: hospital,
    ),
  );

  void clearError() => state = state.copyWith(clearError: true);
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
