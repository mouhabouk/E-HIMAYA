/// Build-time configuration of the staff app (phase P4a), injected with `--dart-define` like the
/// citizen app's [AppConfig]. The client is public: the device authorization grant (RFC 8628)
/// signs the team leader in from the phone's browser, with the second factor, and no password is
/// ever typed into this app.
class StaffConfig {
  const StaffConfig({
    required this.apiBaseUrl,
    required this.issuer,
    required this.clientId,
    this.roomPhone = '198',
    this.smsNumber = '',
  });

  factory StaffConfig.fromEnvironment() => const StaffConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
    issuer: String.fromEnvironment(
      'STAFF_OIDC_ISSUER',
      defaultValue: 'http://10.0.2.2:8080/realms/ehimaya-staff',
    ),
    clientId: String.fromEnvironment(
      'STAFF_OIDC_CLIENT_ID',
      defaultValue: 'ehimaya-staff-app',
    ),
    roomPhone: String.fromEnvironment('STAFF_ROOM_PHONE', defaultValue: '198'),
    smsNumber: String.fromEnvironment(
      'STAFF_SMS_NUMBER',
      defaultValue: String.fromEnvironment('SMS_REPORT_NUMBER'),
    ),
  );

  final String apiBaseUrl;
  final String issuer;
  final String clientId;

  /// The operations room's number, behind the "Room" button of a mission (design §5.3).
  final String roomPhone;

  /// The platform's SMS gateway, for the signed text messages without internet (phase P4d,
  /// design §9.3); empty hides «أرسل برسالة قصيرة».
  final String smsNumber;

  String get deviceEndpoint => '$issuer/protocol/openid-connect/auth/device';
  String get tokenEndpoint => '$issuer/protocol/openid-connect/token';

  /// The app locks itself after this long in the background (PIN asked again).
  static const lockAfter = Duration(minutes: 5);

  /// Wrong PINs in a row before the phone forgets everything.
  static const maxPinFailures = 5;

  /// How often the missions are fetched while the app is open (push rings sooner).
  static const pollEvery = Duration(seconds: 15);

  /// How often the phone tries again to send the writes that wait (design §9.1).
  static const retryEvery = Duration(seconds: 30);

  /// The vehicle's position: every 30 s on the way, every 2 min on scene (design §9.2).
  static const trackEnRoute = Duration(seconds: 30);
  static const trackOnScene = Duration(minutes: 2);

  /// Distance under which arriving on scene is suggested.
  static const onSceneRadiusM = 150;
}
