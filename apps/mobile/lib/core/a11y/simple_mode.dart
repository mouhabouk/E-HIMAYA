import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/app_prefs.dart';

/// Phase P5b (F-APP-142): the simplified home, five large buttons in plain words within reach
/// of the thumb. Off by default; only the home changes, nothing is removed from the app.
class SimpleModeController extends Notifier<bool> {
  @override
  bool build() => ref.watch(appPrefsProvider).a11ySimpleMode;

  Future<void> set(bool on) async {
    await ref.read(appPrefsProvider).setA11ySimpleMode(on);
    state = on;
  }
}

final simpleModeProvider = NotifierProvider<SimpleModeController, bool>(
  SimpleModeController.new,
);
