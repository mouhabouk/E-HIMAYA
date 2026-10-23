import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/auth/oidc_client.dart';
import '../../core/routing/app_router.dart';
import '../../l10n/app_localizations.dart';

/// A citizen signs in (phase A: phone number and SMS code). True once signed in. [register] is
/// kept for the callers: with a phone number, signing in and creating the account are one step.
Future<bool> runLogin(
  BuildContext context,
  WidgetRef ref, {
  bool register = false,
}) async {
  final ok = await GoRouter.of(context).push<bool>(Routes.signIn);
  return ok ?? false;
}

/// Runs the Keycloak login in the browser (institutions, and e-mail accounts created before
/// phase A) and reports failures in a snack bar.
Future<bool> runBrowserLogin(
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
