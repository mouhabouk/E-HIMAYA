import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/consent/consent_service.dart';
import '../../core/storage/app_prefs.dart';

/// Whether the current charter version was accepted on this device (FR-A-001).
class CharterController extends Notifier<bool> {
  @override
  bool build() => ref.watch(consentServiceProvider).acceptedLocally;

  Future<void> accept() async {
    final consent = ref.read(consentServiceProvider);
    await consent.acceptLocally();
    state = true;
    // Sent now if an identity already exists, otherwise by the sync engine later.
    unawaited(consent.sendIfNeeded());
  }
}

final charterAcceptedProvider = NotifierProvider<CharterController, bool>(
  CharterController.new,
);

/// Whether the "complete your profile" form was already offered after the first login.
class ProfilePromptController extends Notifier<bool> {
  @override
  bool build() => ref.watch(appPrefsProvider).profilePrompted;

  Future<void> markPrompted() async {
    await ref.read(appPrefsProvider).setProfilePrompted(true);
    state = true;
  }

  Future<void> reset() async {
    await ref.read(appPrefsProvider).setProfilePrompted(false);
    state = false;
  }
}

final profilePromptedProvider = NotifierProvider<ProfilePromptController, bool>(
  ProfilePromptController.new,
);
