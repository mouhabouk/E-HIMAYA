import 'dart:io' show Platform;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart';
import '../config/app_config.dart';
import '../config/providers.dart';
import '../http/api_error.dart';
import '../http/ehimaya_api.dart';
import '../logging/log.dart';
import '../settings/settings_controller.dart';
import '../storage/app_prefs.dart';

final _log = logger('consent');

/// What the sync engine needs from the consent flow.
abstract class ConsentSender {
  /// Sends the accepted charter version to the server when the current identity has not sent it
  /// yet ([force] re-sends anyway, used after `428 consent_required`). Returns true on success
  /// or when nothing had to be sent.
  Future<bool> sendIfNeeded({bool force = false});
}

/// FR-A-001: the charter is accepted locally first (works offline, before any identity exists),
/// then `POST /api/v1/consents` is sent once per identity, retried later if offline.
class ConsentService implements ConsentSender {
  ConsentService({
    required this.prefs,
    required this.api,
    required this.identity,
    required this.locale,
    required this.clock,
    this.platform = _platformName,
  });

  final AppPrefs prefs;
  final EHimayaApi api;
  final IdentityState Function() identity;
  final String Function() locale;
  final DateTime Function() clock;
  final String Function() platform;

  Future<void>? _inFlight;

  bool get acceptedLocally =>
      prefs.charterAcceptedVersion == AppConfig.charterVersion;

  Future<void> acceptLocally() async {
    await prefs.setCharterAccepted(AppConfig.charterVersion, clock());
  }

  bool get needsServerSend {
    final id = identity();
    return acceptedLocally &&
        id.hasIdentity &&
        prefs.consentSentFor != id.fingerprint;
  }

  @override
  Future<bool> sendIfNeeded({bool force = false}) async {
    final id = identity();
    if (!acceptedLocally || !id.hasIdentity) return !force;
    if (!force && prefs.consentSentFor == id.fingerprint) return true;
    try {
      await (_inFlight ??= _send(id).whenComplete(() => _inFlight = null));
      return true;
    } on ApiException catch (e) {
      _log.info('consent not sent yet: ${e.code.wire}');
      return false;
    }
  }

  Future<void> _send(IdentityState id) async {
    await api.postConsent(
      charterVersion: AppConfig.charterVersion,
      locale: locale(),
      platform: platform(),
    );
    await prefs.setConsentSentFor(id.fingerprint);
  }
}

String _platformName() => Platform.isIOS ? 'ios' : 'android';

final consentServiceProvider = Provider<ConsentService>(
  (ref) => ConsentService(
    prefs: ref.watch(appPrefsProvider),
    api: ref.watch(apiProvider),
    identity: () => ref.read(identityProvider),
    locale: () => ref.read(localeCodeProvider),
    clock: ref.watch(clockProvider),
  ),
);
