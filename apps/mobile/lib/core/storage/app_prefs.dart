import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Non-sensitive local settings (charter acceptance, chosen role, UI language and theme,
/// "report as" choices).
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
  static const _reportAs = 'orgs.report_as';
  static const _sosReportAs = 'orgs.sos_report_as';
  static const _locationAlerts = 'alerts.location';
  static const _pushToken = 'push.registered_token';
  static const _simPushToken = 'push.sim_token';
  static const _simPushSeq = 'push.sim_last_seq';
  static const _tipsEtag = 'tips.etag';
  static const _tipsJson = 'tips.json';
  static const _alertsJson = 'alerts.last';
  static const _weatherJson = 'weather.last';
  static const _batterySaver = 'power.battery_saver';
  static const _criticalAlerts = criticalAlertsKey;

  /// Read directly by the push background isolate.
  static const criticalAlertsKey = 'alerts.critical_opt_in';
  static const _batteryOptAskedAt = 'power.battery_opt_asked_at';
  static const _anonQuotaLimit = 'quota.anon_limit';
  static const _anonQuotaRemaining = 'quota.anon_remaining';

  /// Kept when the account is deleted: interface choices, not personal data.
  static const _keptOnWipe = {_locale, _theme, _batterySaver};

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

  /// Institution id last chosen in "Report as" on the report form (null: myself).
  String? get reportAsOrgId => _prefs.getString(_reportAs);
  Future<void> setReportAsOrgId(String? value) => value == null
      ? _prefs.remove(_reportAs)
      : _prefs.setString(_reportAs, value);

  /// Institution id the SOS is sent for by default (null: myself), chosen in settings.
  String? get sosReportAsOrgId => _prefs.getString(_sosReportAs);
  Future<void> setSosReportAsOrgId(String? value) => value == null
      ? _prefs.remove(_sosReportAs)
      : _prefs.setString(_sosReportAs, value);

  /// FR-A-061: receive alerts for the phone's current (coarse) position, not only for the
  /// profile gouvernorat. On by default; the user can turn it off in settings.
  bool get locationAlerts => _prefs.getBool(_locationAlerts) ?? true;
  Future<void> setLocationAlerts(bool value) =>
      _prefs.setBool(_locationAlerts, value);

  /// Push token last registered with the server (to unregister it at sign-out).
  String? get pushToken => _prefs.getString(_pushToken);
  Future<void> setPushToken(String? value) => value == null
      ? _prefs.remove(_pushToken)
      : _prefs.setString(_pushToken, value);

  /// Token of the simulated push (development builds with PUSH_SIMULATOR_URL only).
  String? get simPushToken => _prefs.getString(_simPushToken);
  Future<void> setSimPushToken(String value) =>
      _prefs.setString(_simPushToken, value);

  /// Last simulator message seen, so a restart does not show old pushes again.
  int get simPushLastSeq => _prefs.getInt(_simPushSeq) ?? 0;
  Future<void> setSimPushLastSeq(int value) =>
      _prefs.setInt(_simPushSeq, value);

  /// Offline copy of the published safety tips (public content) and its ETag.
  String? get tipsEtag => _prefs.getString(_tipsEtag);
  String? get tipsJson => _prefs.getString(_tipsJson);
  Future<void> setTips(String json, String? etag) async {
    await _prefs.setString(_tipsJson, json);
    if (etag == null) {
      await _prefs.remove(_tipsEtag);
    } else {
      await _prefs.setString(_tipsEtag, etag);
    }
  }

  /// Last active alerts seen (public content), shown when offline until they expire.
  String? get lastAlertsJson => _prefs.getString(_alertsJson);
  Future<void> setLastAlertsJson(String value) =>
      _prefs.setString(_alertsJson, value);

  /// Last weather answer and when it was fetched (`{"fetched_at", "report"}`), shown offline
  /// with its time. It holds the grid point (≈ 1 km), so it is wiped with the account.
  String? get lastWeatherJson => _prefs.getString(_weatherJson);
  Future<void> setLastWeatherJson(String value) =>
      _prefs.setString(_weatherJson, value);

  /// In-app battery saver: `auto` (default), `on` or `off`.
  String? get batterySaverMode => _prefs.getString(_batterySaver);
  Future<void> setBatterySaverMode(String value) =>
      _prefs.setString(_batterySaver, value);

  /// The user opted in to official alerts of the highest severity breaking through Do Not
  /// Disturb (Android; never enabled without this explicit choice).
  bool get criticalAlertsOptIn => _prefs.getBool(_criticalAlerts) ?? false;
  Future<void> setCriticalAlertsOptIn(bool value) =>
      _prefs.setBool(_criticalAlerts, value);

  /// When a ready volunteer was last asked to exempt the app from battery optimisation (asked
  /// at most once a month, never to other users).
  DateTime? get batteryOptAskedAt {
    final raw = _prefs.getString(_batteryOptAskedAt);
    return raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> setBatteryOptAskedAt(DateTime at) =>
      _prefs.setString(_batteryOptAskedAt, at.toUtc().toIso8601String());

  /// Anonymous report quota last announced by the server (phase 9 §3: `X-Anon-Quota-*` headers
  /// and `GET /reports/quota`). Null when unknown; the server stays the only authority.
  int? get anonQuotaLimit => _prefs.getInt(_anonQuotaLimit);
  int? get anonQuotaRemaining => _prefs.getInt(_anonQuotaRemaining);
  Future<void> setAnonQuota({int? limit, int? remaining}) async {
    if (limit == null) {
      await _prefs.remove(_anonQuotaLimit);
    } else {
      await _prefs.setInt(_anonQuotaLimit, limit);
    }
    if (remaining == null) {
      await _prefs.remove(_anonQuotaRemaining);
    } else {
      await _prefs.setInt(_anonQuotaRemaining, remaining);
    }
  }

  /// Account deletion: forgets everything except the language, theme and battery saver choice
  /// (the app then starts again from the charter).
  Future<void> wipeForAccountDeletion() async {
    for (final key in _prefs.getKeys().toList()) {
      if (!_keptOnWipe.contains(key)) await _prefs.remove(key);
    }
  }
}

/// Overridden in `main()` (and in tests) with an initialised [SharedPreferences].
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPreferencesProvider not overridden'),
);

final appPrefsProvider = Provider<AppPrefs>(
  (ref) => AppPrefs(ref.watch(sharedPreferencesProvider)),
);
