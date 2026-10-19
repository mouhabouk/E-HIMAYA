import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/auth/oidc_client.dart';
import '../../l10n/app_localizations.dart';

/// Runs the Keycloak login (or registration) and reports failures in a snack bar.
Future<bool> runLogin(
  BuildContext context,
  WidgetRef ref, {
  bool register = false,
}) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  try {
    await ref.read(identityProvider.notifier).login(register: register);
    ref.read(anonBlockedProvider.notifier).set(false);
    return true;
  } on OidcCancelled {
    messenger.showSnackBar(SnackBar(content: Text(l10n.loginCancelled)));
  } on Exception {
    messenger.showSnackBar(SnackBar(content: Text(l10n.loginFailed)));
  }
  return false;
}
