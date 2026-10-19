import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../platform/device_services.dart';
import '../push/push_payload.dart';

/// The app is displayed over a locked phone because a most severe official alert opened it full
/// screen (Android). While [locked] is true the router shows only the public alert view; leaving
/// it needs the phone to be unlocked first ([LockedAlertController.unlock]).
class LockedAlertState {
  const LockedAlertState({required this.locked, this.alert});

  final bool locked;

  /// The public alert that opened the app (its own text is public content).
  final PushPayload? alert;

  String? get alertId => alert?.id;
}

/// Read by `main()` before the first frame, so a locked phone never renders the app shell.
final initialLockedAlertProvider = Provider<bool>((ref) => false);

class LockedAlertController extends Notifier<LockedAlertState> {
  AppLifecycleListener? _lifecycle;

  @override
  LockedAlertState build() {
    ref.onDispose(() => _lifecycle?.dispose());
    return LockedAlertState(locked: ref.watch(initialLockedAlertProvider));
  }

  /// Follows the lock state on every resume (the activity may have been reopened by a new
  /// full-screen alert, or unlocked by the system). Started from `main()`.
  void start() {
    _lifecycle ??= AppLifecycleListener(onResume: () => unawaited(refresh()));
  }

  Future<void> refresh() async {
    final locked = await ref.read(deviceServicesProvider).lockedAlertMode();
    if (!ref.mounted) return;
    if (locked != state.locked) {
      state = LockedAlertState(
        locked: locked,
        alert: locked ? state.alert : null,
      );
    }
  }

  /// Remembers the public alert shown over the lock screen.
  void showAlert(PushPayload alert) {
    state = LockedAlertState(locked: state.locked, alert: alert);
  }

  /// Asks for the unlock; true when the app may leave the alert view. Fails closed.
  Future<bool> unlock() async {
    if (!state.locked) return true;
    final ok = await ref.read(deviceServicesProvider).requestUnlock();
    if (!ref.mounted) return false;
    if (ok) state = const LockedAlertState(locked: false);
    return ok;
  }
}

final lockedAlertProvider =
    NotifierProvider<LockedAlertController, LockedAlertState>(
      LockedAlertController.new,
    );

/// A push that may be shown over the lock screen: a public official alert of the highest
/// severity (never a personal or redacted push).
bool showableWhileLocked(PushPayload p) =>
    p.severe && !p.redacted && (p.id ?? '').isNotEmpty;
