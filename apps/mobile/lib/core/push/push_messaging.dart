import 'dart:async';
import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../auth/identity.dart' show FlagNotifier;
import '../http/api_client.dart' show httpAdapterProvider;
import '../logging/log.dart';
import '../storage/app_prefs.dart';
import 'push_dedup.dart';
import 'push_notifications.dart';
import 'push_payload.dart';
import 'simulated_push_messaging.dart';

final _log = logger('push');

/// Android channels. Their sound, vibration and importance cannot be changed once created, so
/// the ids are versioned: a change of settings ships as a new id (and the old one is deleted).
/// The server names the channel in each push (contract §6); a push naming a channel that does
/// not exist on the phone (the legacy `ehimaya_alerts`, or `ehimaya_critical_v2` before the user
/// opted in) falls back to the manifest default, [alertChannelId].
const alertChannelId = 'ehimaya_alerts_v2';

/// Most severe official alerts, bypassing Do Not Disturb. Created only after the user opted in
/// on the "critical alerts" screen and granted Do Not Disturb access.
const criticalChannelId = 'ehimaya_critical_v2';
const defaultChannelId = 'ehimaya_default';

/// Channel ids of earlier versions, deleted at start.
const legacyChannelIds = ['ehimaya_alerts'];

/// Channel names shown in the system settings (localized by the caller).
class PushChannelNames {
  const PushChannelNames({
    required this.alerts,
    required this.alertsDescription,
    required this.general,
    required this.generalDescription,
    String? critical,
    String? criticalDescription,
  }) : critical = critical ?? alerts,
       criticalDescription = criticalDescription ?? alertsDescription;

  final String alerts;
  final String alertsDescription;
  final String general;
  final String generalDescription;
  final String critical;
  final String criticalDescription;
}

/// Push delivery as used by the app. [FirebasePushMessaging] in production; the app works the
/// same without push ([start] returns false) and then polls the active alerts.
abstract class PushMessaging {
  /// Initialises push. False when it is not configured on this build or the platform refused.
  Future<bool> start(PushChannelNames names);

  /// Registration token of this installation (null when unavailable).
  Future<String?> token();

  Stream<String> get onTokenRefresh;

  /// Pushes received while the app is in the foreground (already shown to the user).
  Stream<PushPayload> get onForeground;

  /// Notifications the user tapped.
  Stream<PushPayload> get onOpened;

  /// The notification that launched the app, if any.
  Future<PushPayload?> launchPayload();

  /// `android` or `ios`, as the server expects.
  String get platform;
}

/// No push on this build: every stream is empty.
class NoPushMessaging implements PushMessaging {
  const NoPushMessaging();

  @override
  Future<bool> start(PushChannelNames names) async => false;
  @override
  Future<String?> token() async => null;
  @override
  Stream<String> get onTokenRefresh => const Stream.empty();
  @override
  Stream<PushPayload> get onForeground => const Stream.empty();
  @override
  Stream<PushPayload> get onOpened => const Stream.empty();
  @override
  Future<PushPayload?> launchPayload() async => null;
  @override
  String get platform => 'android';
}

/// Firebase options injected with `--dart-define` (FIREBASE_API_KEY, FIREBASE_APP_ID,
/// FIREBASE_MESSAGING_SENDER_ID, FIREBASE_PROJECT_ID). Without them the platform default
/// configuration (GoogleService-Info.plist on iOS) is tried, and push stays off if none exists.
FirebaseOptions? firebaseOptionsFromEnvironment() {
  const apiKey = String.fromEnvironment('FIREBASE_API_KEY');
  const appId = String.fromEnvironment('FIREBASE_APP_ID');
  const senderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');
  const projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
  if (apiKey.isEmpty ||
      appId.isEmpty ||
      senderId.isEmpty ||
      projectId.isEmpty) {
    return null;
  }
  return const FirebaseOptions(
    apiKey: apiKey,
    appId: appId,
    messagingSenderId: senderId,
    projectId: projectId,
  );
}

/// Pushes delivered while the app is in the background or killed (Android). A push with a
/// `notification` block was already shown by the system on the channel the server named; only
/// data-only pushes (which the server may use for the most severe alerts, so that they can open
/// full screen) are displayed here, on our channels.
@pragma('vm:entry-point')
Future<void> firebaseBackgroundMessage(RemoteMessage m) async {
  if (m.notification != null) return;
  final title = m.data['title'];
  final body = m.data['body'];
  final p = PushPayload.parse(
    m.data,
    title: title is String ? title : null,
    body: body is String ? body : null,
  );
  // A redacted push (A8) has no text to show before the app fetches it: the generic title the
  // server put in `title` is shown, the app resolves it when opened.
  if (p == null || p.title == null) return;
  final local = LocalPushNotifications();
  await local.initBackground(
    criticalOptIn: (await SharedPreferences.getInstance()).getBool(
      AppPrefs.criticalAlertsKey,
    ),
  );
  final channel = m.data['android_channel'];
  await local.show(
    notificationIdFor(p),
    p,
    channelId: channel is String ? channel : null,
  );
}

class FirebasePushMessaging implements PushMessaging {
  FirebasePushMessaging({
    FirebaseOptions? options,
    PushNotifications? notifications,
    PushDeduper? deduper,
  }) : _options = options ?? firebaseOptionsFromEnvironment(),
       _local = notifications ?? LocalPushNotifications(),
       _dedup = deduper ?? PushDeduper();

  final FirebaseOptions? _options;
  final PushNotifications _local;
  final PushDeduper _dedup;
  final _foreground = StreamController<PushPayload>.broadcast();
  final _opened = StreamController<PushPayload>.broadcast();
  FirebaseMessaging? _messaging;
  PushPayload? _launch;

  @override
  String get platform => !kIsWeb && Platform.isIOS ? 'ios' : 'android';

  @override
  Future<bool> start(PushChannelNames names) async {
    if (_messaging != null) return true;
    try {
      if (Firebase.apps.isEmpty) {
        final options = _options;
        if (options == null && !(!kIsWeb && Platform.isIOS)) {
          // Android needs explicit options (no google-services plugin in this build).
          _log.info('push not configured on this build');
          return false;
        }
        await Firebase.initializeApp(options: options);
      }
      FirebaseMessaging.onBackgroundMessage(firebaseBackgroundMessage);
      final messaging = FirebaseMessaging.instance;
      await _initLocal(names);
      final settings = await messaging.requestPermission();
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        _log.info('notifications refused by the user');
      }
      // iOS: show alerts received in the foreground like in the background.
      await messaging.setForegroundNotificationPresentationOptions(
        alert: true,
        sound: true,
      );
      FirebaseMessaging.onMessage.listen(_onForegroundMessage);
      FirebaseMessaging.onMessageOpenedApp.listen((m) {
        final p = _payload(m);
        if (p != null) _opened.add(p);
      });
      final initial = await messaging.getInitialMessage();
      if (initial != null) _launch = _payload(initial);
      _messaging = messaging;
      return true;
    } on Object catch (e, st) {
      // Missing configuration, no Google Play services…: the app works without push.
      _log.warning('push unavailable', e, st);
      return false;
    }
  }

  Future<void> _initLocal(PushChannelNames names) async {
    final launch = await _local.init(names, onTap: _opened.add);
    _launch ??= launch;
  }

  static PushPayload? _payload(RemoteMessage m) => PushPayload.parse(
    m.data,
    title: m.notification?.title,
    body: m.notification?.body,
  );

  Future<void> _onForegroundMessage(RemoteMessage m) async {
    final p = _payload(m);
    if (p == null) return;
    final first = _dedup.firstTime(p, DateTime.now());
    _foreground.add(p);
    // Android does not display pushes received in the foreground: show it ourselves, once
    // (a repeated push only refreshes the screens).
    if (!first || platform != 'android' || p.title == null) return;
    await _local.show(
      notificationIdFor(p),
      p,
      channelId: m.notification?.android?.channelId,
    );
  }

  @override
  Future<String?> token() async {
    try {
      // firebase_messaging 17 deprecates FCM tokens in favour of register()/onRegistered, which hand out a
      // Firebase Installation ID instead. The API's FCM provider sends to registration tokens, so both sides
      // move together (planned with the server change); until then the token API is kept on purpose.
      // ignore: deprecated_member_use
      return await _messaging?.getToken();
    } on Object catch (e) {
      _log.info('no push token: ${e.runtimeType}');
      return null;
    }
  }

  @override
  Stream<String> get onTokenRefresh =>
      // Kept with getToken() above until the API sends to Installation IDs.
      // ignore: deprecated_member_use
      _messaging?.onTokenRefresh ?? const Stream.empty();

  @override
  Stream<PushPayload> get onForeground => _foreground.stream;

  @override
  Stream<PushPayload> get onOpened => _opened.stream;

  @override
  Future<PushPayload?> launchPayload() async {
    final p = _launch;
    _launch = null;
    return p;
  }
}

/// The one local-notification displayer of the app (shared by push and the settings screens).
final pushNotificationsProvider = Provider<PushNotifications>(
  (ref) => LocalPushNotifications(),
);

final pushMessagingProvider = Provider<PushMessaging>((ref) {
  // ┏━━ SIMULATION ━━ Picks the notify-sim poller when Firebase is absent and the URL is set.
  // ┃ PRODUCTION: nothing to change here: build without --dart-define=PUSH_SIMULATOR_URL and
  // ┃   with FIREBASE_API_KEY / FIREBASE_APP_ID / FIREBASE_MESSAGING_SENDER_ID /
  // ┃   FIREBASE_PROJECT_ID (Firebase console > Project settings > Your apps); the Firebase
  // ┃   options always win over the simulator. See simulated_push_messaging.dart.
  // ┗━━━━━━━━━━━━━━━━
  if (pushSimulatorUrl.isNotEmpty && firebaseOptionsFromEnvironment() == null) {
    final simulated = SimulatedPushMessaging(
      dio: buildSimulatorDio(
        pushSimulatorUrl,
        adapter: ref.watch(httpAdapterProvider),
      ),
      prefs: ref.watch(appPrefsProvider),
      notifications: ref.watch(pushNotificationsProvider),
    );
    ref.onDispose(simulated.dispose);
    return simulated;
  }
  return FirebasePushMessaging(
    notifications: ref.watch(pushNotificationsProvider),
  );
});

// ┏━━ SIMULATION ━━ True while pushes come from notify-sim (drives the "Simulation mode" badge).
// ┃ PRODUCTION: always false once the build has no PUSH_SIMULATOR_URL (see above).
// ┗━━━━━━━━━━━━━━━━
final pushSimulationActiveProvider = Provider<bool>(
  (ref) =>
      ref.watch(pushAvailableProvider) &&
      ref.watch(pushMessagingProvider) is SimulatedPushMessaging,
);

/// Whether push works on this phone (false until started, and on builds without Firebase).
final pushAvailableProvider = NotifierProvider<FlagNotifier, bool>(
  FlagNotifier.new,
);
