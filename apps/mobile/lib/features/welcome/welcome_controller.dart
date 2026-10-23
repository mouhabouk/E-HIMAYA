import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/app_prefs.dart';

/// First-launch steps done on this phone (phase A, addition 7): language, introduction cards,
/// permissions. The terms (charter) and the identity have their own controllers.
class WelcomeSteps {
  const WelcomeSteps({
    required this.languageChosen,
    required this.introSeen,
    required this.permissionsSeen,
  });

  final bool languageChosen;
  final bool introSeen;
  final bool permissionsSeen;

  static const done = WelcomeSteps(
    languageChosen: true,
    introSeen: true,
    permissionsSeen: true,
  );
}

class WelcomeController extends Notifier<WelcomeSteps> {
  AppPrefs get _prefs => ref.read(appPrefsProvider);

  @override
  WelcomeSteps build() {
    final prefs = ref.watch(appPrefsProvider);
    return WelcomeSteps(
      languageChosen: prefs.languageChosen,
      introSeen: prefs.introSeen,
      permissionsSeen: prefs.permissionsSeen,
    );
  }

  Future<void> languageChosen() async {
    await _prefs.setLanguageChosen();
    state = WelcomeSteps(
      languageChosen: true,
      introSeen: state.introSeen,
      permissionsSeen: state.permissionsSeen,
    );
  }

  Future<void> introSeen() async {
    await _prefs.setIntroSeen();
    state = WelcomeSteps(
      languageChosen: state.languageChosen,
      introSeen: true,
      permissionsSeen: state.permissionsSeen,
    );
  }

  Future<void> permissionsSeen() async {
    await _prefs.setPermissionsSeen();
    state = WelcomeSteps(
      languageChosen: state.languageChosen,
      introSeen: state.introSeen,
      permissionsSeen: true,
    );
  }
}

final welcomeProvider = NotifierProvider<WelcomeController, WelcomeSteps>(
  WelcomeController.new,
);
