import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../platform/device_services.dart';
import '../storage/app_prefs.dart';
import 'scheduling.dart';

/// State of the in-app battery saver.
class BatterySaverState {
  const BatterySaverState({
    required this.mode,
    required this.active,
    this.reading,
  });

  final BatterySaverMode mode;
  final bool active;
  final BatteryReading? reading;
}

/// In-app battery saver: on low battery (or when the phone's own saver is on) the app polls
/// less, shares the volunteer position less often with a coarser radio, and keeps large media
/// for Wi-Fi. Alerts, SOS and reports are never slowed down beyond what [AlertPolling] allows.
///
/// The battery is read on start, on resume and every [readEvery] in the foreground only (a
/// cheap binder call; no listener stays registered in the background).
class BatterySaverController extends Notifier<BatterySaverState>
    with WidgetsBindingObserver {
  static const readEvery = Duration(minutes: 5);
  static const policy = BatterySaverPolicy();

  Timer? _timer;
  bool _started = false;

  @override
  BatterySaverState build() {
    ref.onDispose(_stop);
    final mode = BatterySaverMode.fromName(
      ref.read(appPrefsProvider).batterySaverMode,
    );
    return BatterySaverState(
      mode: mode,
      active: policy.isActive(mode: mode, reading: null, wasActive: false),
    );
  }

  /// Started once from `main()`; widget tests never start it.
  void start() {
    if (_started) return;
    _started = true;
    WidgetsBinding.instance.addObserver(this);
    _resume();
  }

  Future<void> setMode(BatterySaverMode mode) async {
    await ref.read(appPrefsProvider).setBatterySaverMode(mode.name);
    _apply(mode: mode, reading: state.reading);
  }

  /// Reads the battery now (also used by tests through a fake [DeviceServices]).
  Future<void> refresh() async {
    final reading = await ref.read(deviceServicesProvider).battery();
    if (!ref.mounted) return;
    _apply(mode: state.mode, reading: reading ?? state.reading);
  }

  void _apply({required BatterySaverMode mode, BatteryReading? reading}) {
    final active = policy.isActive(
      mode: mode,
      reading: reading,
      wasActive: state.active,
    );
    if (active == state.active &&
        mode == state.mode &&
        identical(reading, state.reading)) {
      return;
    }
    state = BatterySaverState(mode: mode, active: active, reading: reading);
  }

  void _resume() {
    unawaited(refresh());
    _timer?.cancel();
    _timer = Timer.periodic(readEvery, (_) => unawaited(refresh()));
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _resume();
    } else if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _timer?.cancel();
      _timer = null;
    }
  }

  void _stop() {
    _timer?.cancel();
    _timer = null;
    if (_started) WidgetsBinding.instance.removeObserver(this);
  }
}

final batterySaverProvider =
    NotifierProvider<BatterySaverController, BatterySaverState>(
      BatterySaverController.new,
    );

/// Whether the battery saver is active now (read by the schedulers).
final batterySaverActiveProvider = Provider<bool>(
  (ref) => ref.watch(batterySaverProvider.select((s) => s.active)),
);
