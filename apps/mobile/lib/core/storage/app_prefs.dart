import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Non-sensitive local settings (charter acceptance, chosen role, UI language and theme).
///
/// Secrets never go here: see [SecureStore].
class AppPrefs {
  AppPrefs(this._prefs);

  final SharedPreferences _prefs;

  static const _charterVersion = 'charter.accepted_version';
  static const _charterAcceptedAt = 'charter.accepted_at';
  static const _consentSentFor = 'charter.consent_sent_for';
  static const _role = 'onboarding.role';
  static const _identityMode = 'onboarding.identity_mode';
  static const _locale = 'settings.locale';
  static const _theme = 'settings.theme';
  static const _profilePrompted = 'profile.prompted';

  String? get charterAcceptedVersion => _prefs.getString(_charterVersion);
  DateTime? get charterAcceptedAt {
    final raw = _prefs.getString(_charterAcceptedAt);
    return raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> setCharterAccepted(String version, DateTime at) async {
    await _prefs.setString(_charterVersion, version);
    await _prefs.setString(_charterAcceptedAt, at.toUtc().toIso8601String());
  }

  /// Identity fingerprint (`anon` or the OIDC subject) the current charter version was sent for.
  String? get consentSentFor => _prefs.getString(_consentSentFor);
  Future<void> setConsentSentFor(String? value) async {
    if (value == null) {
      await _prefs.remove(_consentSentFor);
    } else {
      await _prefs.setString(_consentSentFor, value);
    }
  }

  String? get role => _prefs.getString(_role);
  Future<void> setRole(String? value) =>
      value == null ? _prefs.remove(_role) : _prefs.setString(_role, value);

  String? get identityMode => _prefs.getString(_identityMode);
  Future<void> setIdentityMode(String? value) => value == null
      ? _prefs.remove(_identityMode)
      : _prefs.setString(_identityMode, value);

  String? get localeCode => _prefs.getString(_locale);
  Future<void> setLocaleCode(String value) => _prefs.setString(_locale, value);

  String? get themeMode => _prefs.getString(_theme);
  Future<void> setThemeMode(String value) => _prefs.setString(_theme, value);

  bool get profilePrompted => _prefs.getBool(_profilePrompted) ?? false;
  Future<void> setProfilePrompted(bool value) =>
      _prefs.setBool(_profilePrompted, value);
}

/// Overridden in `main()` (and in tests) with an initialised [SharedPreferences].
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPreferencesProvider not overridden'),
);

final appPrefsProvider = Provider<AppPrefs>(
  (ref) => AppPrefs(ref.watch(sharedPreferencesProvider)),
);
