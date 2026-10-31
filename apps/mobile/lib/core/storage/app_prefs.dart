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
  static const _teamNotices = 'reports.team_notices';
  static const _pushToken = 'push.registered_token';
  static const _simPushToken = 'push.sim_token';
  static const _simPushSeq = 'push.sim_last_seq';
  static const _tipsEtag = 'tips.etag';
  static const _tipsJson = 'tips.json';
  static const _guideEtag = 'guide.etag';
  static const _guideJson = 'guide.json';
  static const _placesOff = 'places.off';
  static const _beachWarnings = 'beaches.warnings';
  static const _beachPresence = 'beaches.presence';
  static const _beachToken = 'beaches.token';
  static const _alertsJson = 'alerts.last';
  static const _weatherJson = 'weather.last';
  static const _batterySaver = 'power.battery_saver';
  static const _criticalAlerts = criticalAlertsKey;

  /// Read directly by the push background isolate.
  static const criticalAlertsKey = 'alerts.critical_opt_in';
  static const _batteryOptAskedAt = 'power.battery_opt_asked_at';
  static const _anonQuotaLimit = 'quota.anon_limit';
  static const _anonQuotaRemaining = 'quota.anon_remaining';
  // Phase A: first-launch steps and the colour palette.
  static const _languageChosen = 'welcome.language_chosen';
  static const _introSeen = 'welcome.intro_seen';
  static const _permissionsSeen = 'welcome.permissions_seen';
  static const _palette = 'settings.palette';
  static const _releaseJson = 'update.release';
  static const _releaseCheckedAt = 'update.checked_at';
  static const _updatePostponedBuild = 'update.postponed_build';
  // Phase B2: SOS message template and cancel window, the live share in progress.
  static const _sosTemplate = 'safety.sos_template';
  static const _sosCancelWindow = 'safety.sos_cancel_window';
  static const _liveShare = 'safety.live_share';
  // Phase D (review point 6): order of the SOS message channels after the in-app alert, and those switched off.
  static const _sosChannels = 'safety.sos_channels';
  static const _sosChannelsOff = 'safety.sos_channels_off';
  static const _locationHistoryOn = 'safety.location_history_on';
  static const _a11yScreenFlash = 'a11y.screen_flash';
  static const _a11yTorchFlash = 'a11y.torch_flash';
  static const _a11yReadAlerts = 'a11y.read_alerts';
  static const _a11ySimpleMode = 'a11y.simple_mode';

  /// Kept when the account is deleted: interface choices, not personal data.
  static const _keptOnWipe = {
    _locale,
    _theme,
    _palette,
    _batterySaver,
    _languageChosen,
    _introSeen,
    _a11yScreenFlash,
    _a11yTorchFlash,
    _a11yReadAlerts,
    _a11ySimpleMode,
  };

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

  /// Phase P4d (F-APP-38): told when the team sets off for the user's report, then arrives. On
  /// by default; turned off in settings.
  bool get teamNotices => _prefs.getBool(_teamNotices) ?? true;
  Future<void> setTeamNotices(bool value) =>
      _prefs.setBool(_teamNotices, value);

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

  /// Offline copy of the emergency guide (public content, phase B1) and its ETag.
  String? get guideEtag => _prefs.getString(_guideEtag);
  String? get guideJson => _prefs.getString(_guideJson);
  Future<void> setGuide(String json, String? etag) async {
    await _prefs.setString(_guideJson, json);
    if (etag == null) {
      await _prefs.remove(_guideEtag);
    } else {
      await _prefs.setString(_guideEtag, etag);
    }
  }

  /// Layers the user turned off in "nearest to me" (every public layer is shown otherwise).
  List<String> get placesOff => _prefs.getStringList(_placesOff) ?? const [];
  Future<void> setPlacesOff(List<String> keys) =>
      _prefs.setStringList(_placesOff, keys);

  /// Phase L1b: the user agreed to be warned when near a yellow or red beach (computed on the
  /// phone, the position never leaves it). Off until the user turns it on.
  bool get beachWarnings => _prefs.getBool(_beachWarnings) ?? false;
  Future<void> setBeachWarnings(bool value) =>
      _prefs.setBool(_beachWarnings, value);

  /// Phase L1b: the user agreed to say "I am at this beach" (anonymous count for the room).
  bool get beachPresence => _prefs.getBool(_beachPresence) ?? false;
  Future<void> setBeachPresence(bool value) =>
      _prefs.setBool(_beachPresence, value);

  /// The random code of the day sent with "I am at this beach" (`yyyy-mm-dd|token`), drawn again
  /// each day so two days cannot be linked.
  String? get beachToken => _prefs.getString(_beachToken);
  Future<void> setBeachToken(String value) =>
      _prefs.setString(_beachToken, value);

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

  /// Users who already used the app before phase A (a role is stored) skip the language and
  /// introduction screens and the permissions step; they only accept the new terms.
  bool get _existingUser => role != null;

  bool get languageChosen =>
      _prefs.getBool(_languageChosen) ?? (_existingUser || localeCode != null);
  Future<void> setLanguageChosen() => _prefs.setBool(_languageChosen, true);

  bool get introSeen => _prefs.getBool(_introSeen) ?? _existingUser;
  Future<void> setIntroSeen() => _prefs.setBool(_introSeen, true);

  bool get permissionsSeen => _prefs.getBool(_permissionsSeen) ?? _existingUser;
  Future<void> setPermissionsSeen() => _prefs.setBool(_permissionsSeen, true);

  String? get palette => _prefs.getString(_palette);
  Future<void> setPalette(String value) => _prefs.setString(_palette, value);

  /// Last answer of `GET /api/v1/app/version` (JSON) and when it was fetched.
  String? get releaseJson => _prefs.getString(_releaseJson);
  DateTime? get releaseCheckedAt {
    final raw = _prefs.getString(_releaseCheckedAt);
    return raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> setRelease(String json, DateTime at) async {
    await _prefs.setString(_releaseJson, json);
    await _prefs.setString(_releaseCheckedAt, at.toUtc().toIso8601String());
  }

  /// "Later" on an optional update: not offered again for that build.
  int? get updatePostponedBuild => _prefs.getInt(_updatePostponedBuild);
  Future<void> setUpdatePostponedBuild(int build) =>
      _prefs.setInt(_updatePostponedBuild, build);

  /// Phase B2 (addition 5): the user's own SOS text (null: the default text of the language).
  String? get sosTemplate => _prefs.getString(_sosTemplate);
  Future<void> setSosTemplate(String? value) => value == null
      ? _prefs.remove(_sosTemplate)
      : _prefs.setString(_sosTemplate, value);

  /// The 5-second window to cancel an SOS message before it goes (on by default).
  bool get sosCancelWindow => _prefs.getBool(_sosCancelWindow) ?? true;
  Future<void> setSosCancelWindow(bool value) =>
      _prefs.setBool(_sosCancelWindow, value);

  /// Review point 6: the external channels of the SOS message in the user's order (the in-app
  /// alert to linked contacts always goes first). Unknown or missing names fall back to the
  /// default order.
  List<String> get sosChannels =>
      normaliseSosChannels(_prefs.getStringList(_sosChannels));
  Future<void> setSosChannels(List<String> value) =>
      _prefs.setStringList(_sosChannels, normaliseSosChannels(value));

  /// The channels the user switched off (never all of them: the screen keeps one on).
  Set<String> get sosChannelsOff =>
      (_prefs.getStringList(_sosChannelsOff) ?? const []).toSet();
  Future<void> setSosChannelsOff(Set<String> value) =>
      _prefs.setStringList(_sosChannelsOff, value.toList()..sort());

  /// Phase P5a (accessibility): flash the screen when an urgent alert arrives (off by default).
  bool get a11yScreenFlash => _prefs.getBool(_a11yScreenFlash) ?? false;
  Future<void> setA11yScreenFlash(bool value) =>
      _prefs.setBool(_a11yScreenFlash, value);

  /// Phase P5a: flash the camera light when an urgent alert arrives (off by default).
  bool get a11yTorchFlash => _prefs.getBool(_a11yTorchFlash) ?? false;
  Future<void> setA11yTorchFlash(bool value) =>
      _prefs.setBool(_a11yTorchFlash, value);

  /// Phase P5a: read an urgent alert aloud when it arrives (off by default).
  bool get a11yReadAlerts => _prefs.getBool(_a11yReadAlerts) ?? false;
  Future<void> setA11yReadAlerts(bool value) =>
      _prefs.setBool(_a11yReadAlerts, value);

  /// Phase P5b: the simplified home, large buttons and plain words (off by default).
  bool get a11ySimpleMode => _prefs.getBool(_a11ySimpleMode) ?? false;
  Future<void> setA11ySimpleMode(bool value) =>
      _prefs.setBool(_a11ySimpleMode, value);

  /// The live location share in progress (JSON: id, token, expires_at), so a restart resumes it.
  String? get liveShareJson => _prefs.getString(_liveShare);
  Future<void> setLiveShareJson(String? value) => value == null
      ? _prefs.remove(_liveShare)
      : _prefs.setString(_liveShare, value);

  /// The user turned the 72-hour location history on (the recorder restarts with the app).
  bool get locationHistoryOn => _prefs.getBool(_locationHistoryOn) ?? false;
  Future<void> setLocationHistoryOn(bool value) =>
      _prefs.setBool(_locationHistoryOn, value);

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

/// Review point 6: the external channels of the SOS message, in the default order.
const sosChannelDefaults = ['sms', 'whatsapp', 'email'];

/// Every known channel once, in the given order, the missing ones at the end.
List<String> normaliseSosChannels(List<String>? value) {
  final out = <String>[
    for (final c in value ?? const <String>[])
      if (sosChannelDefaults.contains(c)) c,
  ];
  return [
    ...{...out},
    for (final c in sosChannelDefaults)
      if (!out.contains(c)) c,
  ];
}
