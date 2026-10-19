import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/providers.dart';
import '../identity/device_key.dart';
import '../logging/log.dart';
import '../storage/app_prefs.dart';
import '../storage/secure_store.dart';
import 'auth_session.dart';
import 'oidc_client.dart';

final _log = logger('identity');

/// FR-A-002/003: who is using the app.
enum UserRole { citizen, institution }

enum IdentityMode {
  /// Role not chosen yet, or logged out: only public endpoints may be called.
  none,

  /// Citizen without account: requests carry `X-Device-Key`.
  anonymous,

  /// Citizen or institution account: requests carry `Authorization: Bearer`.
  registered,
}

class IdentityState {
  const IdentityState({required this.mode, this.role, this.session});

  final UserRole? role;
  final IdentityMode mode;
  final AuthSession? session;

  bool get isRegistered => mode == IdentityMode.registered && session != null;
  bool get isAnonymous => mode == IdentityMode.anonymous;
  bool get hasIdentity => isRegistered || isAnonymous;

  /// Local key used to remember for which identity the charter consent was sent.
  String? get fingerprint => switch (mode) {
    IdentityMode.anonymous => 'anon',
    IdentityMode.registered => 'sub:${session?.subject ?? 'unknown'}',
    IdentityMode.none => null,
  };

  IdentityState copyWith({
    UserRole? role,
    IdentityMode? mode,
    AuthSession? session,
    bool clearSession = false,
  }) => IdentityState(
    role: role ?? this.role,
    mode: mode ?? this.mode,
    session: clearSession ? null : (session ?? this.session),
  );
}

/// Session restored from secure storage before `runApp` (overridden in `main()`).
final initialAuthSessionProvider = Provider<AuthSession?>((ref) => null);

class IdentityController extends Notifier<IdentityState> {
  Future<AuthSession?>? _refreshing;

  AppPrefs get _prefs => ref.read(appPrefsProvider);
  SecureStore get _secure => ref.read(secureStoreProvider);
  OidcClient get _oidc => ref.read(oidcClientProvider);

  @override
  IdentityState build() {
    final prefs = ref.watch(appPrefsProvider);
    final role = UserRole.values.asNameMap()[prefs.role];
    var mode =
        IdentityMode.values.asNameMap()[prefs.identityMode] ??
        IdentityMode.none;
    final session = ref.watch(initialAuthSessionProvider);
    if (mode == IdentityMode.registered && session == null) {
      mode = IdentityMode.none;
    }
    if (role == UserRole.institution && mode == IdentityMode.anonymous) {
      mode = IdentityMode.none;
    }
    return IdentityState(role: role, mode: mode, session: session);
  }

  Future<void> chooseRole(UserRole? role) async {
    await _prefs.setRole(role?.name);
    if (role == null) await _prefs.setIdentityMode(null);
    state = IdentityState(
      role: role,
      mode: role == null ? IdentityMode.none : state.mode,
      session: state.session,
    );
  }

  /// Citizen continues without an account (FR-A-003).
  Future<void> useAnonymous() async {
    await ref.read(deviceKeyStoreProvider).get();
    await _prefs.setIdentityMode(IdentityMode.anonymous.name);
    state = state.copyWith(
      role: UserRole.citizen,
      mode: IdentityMode.anonymous,
      clearSession: true,
    );
  }

  /// Opens the Keycloak login (or registration) page. Throws [OidcCancelled] / [OidcFailure].
  Future<void> login({bool register = false}) async {
    final session = await _oidc.login(register: register);
    await _saveSession(session);
    await _prefs.setIdentityMode(IdentityMode.registered.name);
    state = state.copyWith(mode: IdentityMode.registered, session: session);
  }

  Future<void> logout() async {
    final session = state.session;
    await _secure.delete(SecureStoreKeys.authSession);
    await _prefs.setIdentityMode(null);
    state = state.copyWith(mode: IdentityMode.none, clearSession: true);
    if (session != null) await _oidc.endSession(session);
  }

  /// A valid access token, refreshed when it expires within 30 s. Concurrent callers share one
  /// refresh. Returns null when the session is gone (the user must log in again).
  Future<String?> validAccessToken({bool forceRefresh = false}) async {
    final session = state.session;
    if (session == null || state.mode != IdentityMode.registered) return null;
    final now = ref.read(clockProvider)();
    if (!forceRefresh &&
        !session.expiresWithin(const Duration(seconds: 30), now)) {
      return session.accessToken;
    }
    final refreshed = await (_refreshing ??= _refresh(session)
        .whenComplete(() => _refreshing = null));
    return refreshed?.accessToken;
  }

  Future<AuthSession?> _refresh(AuthSession session) async {
    try {
      final next = await _oidc.refresh(session);
      await _saveSession(next);
      state = state.copyWith(session: next);
      return next;
    } on OidcSessionExpired {
      _log.info('session expired, signing out locally');
      await _secure.delete(SecureStoreKeys.authSession);
      await _prefs.setIdentityMode(null);
      state = state.copyWith(mode: IdentityMode.none, clearSession: true);
      return null;
    } on OidcFailure {
      // Offline or Keycloak unreachable: keep the session, let the caller retry later.
      return null;
    }
  }

  Future<void> _saveSession(AuthSession session) =>
      _secure.write(SecureStoreKeys.authSession, jsonEncode(session.toJson()));
}

final identityProvider = NotifierProvider<IdentityController, IdentityState>(
  IdentityController.new,
);

/// Set when the server answered `403 anon_blocked`: the UI then offers registration.
final anonBlockedProvider = NotifierProvider<FlagNotifier, bool>(
  FlagNotifier.new,
);

class FlagNotifier extends Notifier<bool> {
  @override
  bool build() => false;
  void set(bool value) => state = value;
}

/// Reads the session persisted by a previous run (called before `runApp`).
Future<AuthSession?> loadStoredSession(SecureStore store) async =>
    AuthSession.tryParse(await store.read(SecureStoreKeys.authSession));
