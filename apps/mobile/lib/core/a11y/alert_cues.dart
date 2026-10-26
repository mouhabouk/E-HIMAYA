import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../push/push_payload.dart';
import '../settings/settings_controller.dart';
import '../storage/app_prefs.dart';
import '../ui/theme.dart';
import 'speech.dart';
import 'torch.dart';

/// The user's choices for deaf, hard-of-hearing and blind users (phase P5a). All off by default:
/// the notification already rings, vibrates (long-short-long) and lights the LED.
class A11yCues {
  const A11yCues({
    required this.screenFlash,
    required this.torchFlash,
    required this.readAlerts,
  });

  final bool screenFlash;
  final bool torchFlash;
  final bool readAlerts;

  bool get any => screenFlash || torchFlash || readAlerts;
}

class A11yCuesController extends Notifier<A11yCues> {
  AppPrefs get _prefs => ref.read(appPrefsProvider);

  @override
  A11yCues build() {
    final p = ref.watch(appPrefsProvider);
    return A11yCues(
      screenFlash: p.a11yScreenFlash,
      torchFlash: p.a11yTorchFlash,
      readAlerts: p.a11yReadAlerts,
    );
  }

  A11yCues _with({bool? screenFlash, bool? torchFlash, bool? readAlerts}) =>
      A11yCues(
        screenFlash: screenFlash ?? state.screenFlash,
        torchFlash: torchFlash ?? state.torchFlash,
        readAlerts: readAlerts ?? state.readAlerts,
      );

  Future<void> setScreenFlash(bool on) async {
    await _prefs.setA11yScreenFlash(on);
    state = _with(screenFlash: on);
  }

  Future<void> setTorchFlash(bool on) async {
    await _prefs.setA11yTorchFlash(on);
    state = _with(torchFlash: on);
  }

  Future<void> setReadAlerts(bool on) async {
    await _prefs.setA11yReadAlerts(on);
    state = _with(readAlerts: on);
  }
}

final a11yCuesProvider = NotifierProvider<A11yCuesController, A11yCues>(
  A11yCuesController.new,
);

/// Each increment asks [ScreenFlash] for one series of flashes.
class ScreenFlashRequests extends Notifier<int> {
  @override
  int build() => 0;

  void request() => state++;
}

final screenFlashProvider = NotifierProvider<ScreenFlashRequests, int>(
  ScreenFlashRequests.new,
);

/// Runs the cues the user chose when an urgent push arrives while the app is open.
class AlertCuesRunner {
  AlertCuesRunner(this._ref);

  final Ref _ref;

  /// [p] is shown by the notification as usual; this adds the flashes and the voice.
  Future<void> onUrgent(PushPayload p) async {
    if (!p.kind.urgent) return;
    final text = [
      if (p.title != null) p.title!,
      if (p.body != null) p.body!,
    ].join('. ');
    await run(text);
  }

  /// Also used by the «try» button of the accessibility settings.
  Future<void> run(String text) async {
    final cues = _ref.read(a11yCuesProvider);
    if (cues.screenFlash) _ref.read(screenFlashProvider.notifier).request();
    if (cues.torchFlash) unawaited(_ref.read(torchProvider).flash());
    if (cues.readAlerts && text.isNotEmpty) {
      await _ref
          .read(speakingProvider.notifier)
          .toggle('alert-cue', text, _ref.read(localeCodeProvider));
    }
  }
}

final alertCuesProvider = Provider<AlertCuesRunner>(AlertCuesRunner.new);

/// A red veil over the whole app, three pulses at one per second (WCAG 2.3.1 allows up to three
/// per second), that never takes a tap and is invisible to screen readers.
class ScreenFlash extends ConsumerStatefulWidget {
  const ScreenFlash({super.key, required this.child});

  final Widget child;

  static const pulses = 3;

  @override
  ConsumerState<ScreenFlash> createState() => _ScreenFlashState();
}

class _ScreenFlashState extends ConsumerState<ScreenFlash>
    with SingleTickerProviderStateMixin {
  late final _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: ScreenFlash.pulses),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  /// 0 → 1 → 0 once per second.
  double _opacity(double t) {
    final phase = (t * ScreenFlash.pulses) % 1;
    return phase < 0.5 ? phase * 2 : (1 - phase) * 2;
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(screenFlashProvider, (_, _) => _controller.forward(from: 0));
    return Stack(
      textDirection: TextDirection.ltr,
      children: [
        widget.child,
        Positioned.fill(
          child: IgnorePointer(
            child: ExcludeSemantics(
              child: AnimatedBuilder(
                animation: _controller,
                builder: (context, _) => _controller.isAnimating
                    ? ColoredBox(
                        key: const Key('screen-flash'),
                        color: sosRed.withValues(
                          alpha: 0.7 * _opacity(_controller.value),
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
