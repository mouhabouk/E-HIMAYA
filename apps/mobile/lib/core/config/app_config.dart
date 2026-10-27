/// Build-time configuration, injected with `--dart-define` (no secrets here: the mobile client
/// is public, PKCE protects the code exchange).
///
/// Defaults target the local development stack seen from the Android emulator (10.0.2.2 is the
/// host machine).
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.tusUrl,
    required this.oidcIssuer,
    required this.oidcClientId,
    required this.oidcRedirectUrl,
    required this.mapTileUrl,
    required this.mapAttribution,
    required this.portalUrl,
    this.smsReportNumber = '',
  });

  factory AppConfig.fromEnvironment() => const AppConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
    tusUrl: String.fromEnvironment(
      'TUS_URL',
      defaultValue: 'http://10.0.2.2:1080/api/v1/uploads/',
    ),
    oidcIssuer: String.fromEnvironment(
      'OIDC_ISSUER',
      defaultValue: 'http://10.0.2.2:8080/realms/ehimaya-public',
    ),
    oidcClientId: String.fromEnvironment(
      'OIDC_CLIENT_ID',
      defaultValue: 'ehimaya-mobile',
    ),
    oidcRedirectUrl: 'tn.ehimaya.app:/oauth2redirect',
    mapTileUrl: String.fromEnvironment(
      'MAP_TILE_URL',
      defaultValue: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    ),
    mapAttribution: String.fromEnvironment(
      'MAP_ATTRIBUTION',
      defaultValue: '© OpenStreetMap contributors',
    ),
    portalUrl: String.fromEnvironment(
      'PORTAL_URL',
      defaultValue: 'http://localhost:5174',
    ),
    smsReportNumber: String.fromEnvironment('SMS_REPORT_NUMBER'),
  );

  final String apiBaseUrl;
  final String tusUrl;
  final String oidcIssuer;
  final String oidcClientId;
  final String oidcRedirectUrl;
  final String mapTileUrl;
  final String mapAttribution;

  /// Institutions portal (phase 4): detailed editing of an institution is done there.
  final String portalUrl;

  /// FR-A-048: number of the platform's SMS gateway that receives `EH1 …` reports when the
  /// phone has no internet. Empty (the default): the "send by SMS" option is hidden.
  final String smsReportNumber;

  /// The OIDC issuer may be plain HTTP only on the development stack.
  bool get allowInsecureOidc => Uri.parse(oidcIssuer).scheme == 'http';

  /// Android application id / iOS bundle id, also sent as tile-server user agent.
  static const String applicationId = 'tn.ehimaya.app';

  /// Version of the privacy & personal-data charter whose text ships in the ARB files.
  static const String charterVersion = '2026-11';

  /// Version and build of this app, compared with the latest release the server announces
  /// (phase A, addition 3). Must match `version:` in pubspec.yaml (checked by a test).
  static const String appVersion = '0.19.0';
  static const int appBuild = 18;
}
