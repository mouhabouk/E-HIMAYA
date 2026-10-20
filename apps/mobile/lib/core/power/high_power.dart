import 'package:flutter_riverpod/flutter_riverpod.dart';

/// High-power sessions: the few moments where the app deliberately spends battery (live
/// streaming, phase 6: camera, encoder, radio at full power, a high-accuracy fix every few
/// seconds, the screen kept on). Each one is an explicit exception to the battery rules of
/// [scheduling.dart]: it is opened by the feature, closed with it, and never outlives it.
class HighPowerController extends Notifier<Set<String>> {
  @override
  Set<String> build() => const {};

  void begin(String session) {
    if (state.contains(session)) return;
    state = {...state, session};
  }

  void end(String session) {
    if (!state.contains(session)) return;
    state = {...state}..remove(session);
  }
}

final highPowerSessionsProvider =
    NotifierProvider<HighPowerController, Set<String>>(HighPowerController.new);

/// Whether any high-power session is open.
final highPowerActiveProvider = Provider<bool>(
  (ref) => ref.watch(highPowerSessionsProvider).isNotEmpty,
);
