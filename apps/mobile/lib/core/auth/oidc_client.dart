import 'package:flutter/services.dart';
import 'package:flutter_appauth/flutter_appauth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../config/providers.dart';
import '../logging/log.dart';
import 'auth_session.dart';

final _log = logger('auth');

/// Raised when the user closed the login page.
class OidcCancelled implements Exception {
  const OidcCancelled();
}

/// Raised when the refresh token is no longer valid (session ended on the server).
class OidcSessionExpired implements Exception {
  const OidcSessionExpired();
}

/// Generic login/refresh failure (network, misconfiguration).
class OidcFailure implements Exception {
  const OidcFailure(this.code);
  final String code;
  @override
  String toString() => 'OidcFailure($code)';
}

abstract class OidcClient {
  /// Authorization Code + PKCE (S256) in the system browser. [register] opens the Keycloak
  /// registration page (`prompt=create`).
  Future<AuthSession> login({bool register = false});

  Future<AuthSession> refresh(AuthSession session);

  /// RP-initiated logout at Keycloak (ends the SSO session in the browser too).
  Future<void> endSession(AuthSession session);
}

class AppAuthOidcClient implements OidcClient {
  AppAuthOidcClient(this._config, [FlutterAppAuth? appAuth])
    : _appAuth = appAuth ?? const FlutterAppAuth();

  final AppConfig _config;
  final FlutterAppAuth _appAuth;

  static const _scopes = ['openid', 'profile', 'email', 'offline_access'];

  @override
  Future<AuthSession> login({bool register = false}) async {
    try {
      final result = await _appAuth.authorizeAndExchangeCode(
        AuthorizationTokenRequest(
          _config.oidcClientId,
          _config.oidcRedirectUrl,
          issuer: _config.oidcIssuer,
          scopes: _scopes,
          promptValues: register ? const ['create'] : null,
          allowInsecureConnections: _config.allowInsecureOidc,
          externalUserAgent: ExternalUserAgent.asWebAuthenticationSession,
        ),
      );
      return _toSession(result, previous: null);
    } on FlutterAppAuthUserCancelledException {
      throw const OidcCancelled();
    } on PlatformException catch (e) {
      _log.warning('login failed: ${e.code}');
      throw OidcFailure(e.code);
    }
  }

  @override
  Future<AuthSession> refresh(AuthSession session) async {
    final refreshToken = session.refreshToken;
    if (refreshToken == null) throw const OidcSessionExpired();
    try {
      final result = await _appAuth.token(
        TokenRequest(
          _config.oidcClientId,
          _config.oidcRedirectUrl,
          issuer: _config.oidcIssuer,
          refreshToken: refreshToken,
          scopes: _scopes,
          allowInsecureConnections: _config.allowInsecureOidc,
        ),
      );
      return _toSession(result, previous: session);
    } on PlatformException catch (e) {
      final details = e is FlutterAppAuthPlatformException
          ? e.platformErrorDetails.error
          : null;
      if (details == 'invalid_grant') throw const OidcSessionExpired();
      _log.warning('refresh failed: ${e.code}');
      throw OidcFailure(e.code);
    }
  }

  @override
  Future<void> endSession(AuthSession session) async {
    try {
      await _appAuth.endSession(
        EndSessionRequest(
          idTokenHint: session.idToken,
          postLogoutRedirectUrl: _config.oidcRedirectUrl,
          issuer: _config.oidcIssuer,
          allowInsecureConnections: _config.allowInsecureOidc,
        ),
      );
    } on PlatformException catch (e) {
      // Local logout proceeds anyway; the refresh token is discarded.
      _log.warning('end session failed: ${e.code}');
    }
  }

  AuthSession _toSession(TokenResponse r, {required AuthSession? previous}) {
    final access = r.accessToken;
    if (access == null) throw const OidcFailure('no_access_token');
    return AuthSession(
      accessToken: access,
      expiresAt:
          r.accessTokenExpirationDateTime ??
          DateTime.now().add(const Duration(minutes: 5)),
      refreshToken: r.refreshToken ?? previous?.refreshToken,
      idToken: r.idToken ?? previous?.idToken,
    );
  }
}

final oidcClientProvider = Provider<OidcClient>(
  (ref) => AppAuthOidcClient(ref.watch(appConfigProvider)),
);
