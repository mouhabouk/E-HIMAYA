import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart' show FlagNotifier;
import '../logging/log.dart';
import 'push_payload.dart';

final _log = logger('push');

/// Android channels (the server names them in each push, contract §6).
const alertChannelId = 'ehimaya_alerts';
const defaultChannelId = 'ehimaya_default';

/// Channel names shown in the system settings (localized by the caller).
class PushChannelNames {
  const PushChannelNames({
    required this.alerts,
    required this.alertsDescription,
    required this.general,
    required this.generalDescription,
  });

  final String alerts;
  final String alertsDescription;
  final String general;
  final String generalDescription;
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

class FirebasePushMessaging implements PushMessaging {
  FirebasePushMessaging({FirebaseOptions? options})
    : _options = options ?? firebaseOptionsFromEnvironment();

  final FirebaseOptions? _options;
  final _local = FlutterLocalNotificationsPlugin();
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
    await _local.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false,
        ),
      ),
      onDidReceiveNotificationResponse: (response) {
        final p = _decode(response.payload);
        if (p != null) _opened.add(p);
      },
    );
    final launch = await _local.getNotificationAppLaunchDetails();
    if (launch?.didNotificationLaunchApp ?? false) {
      _launch ??= _decode(launch!.notificationResponse?.payload);
    }
    final android = _local
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    await android?.createNotificationChannel(
      AndroidNotificationChannel(
        alertChannelId,
        names.alerts,
        description: names.alertsDescription,
        importance: Importance.max,
      ),
    );
    await android?.createNotificationChannel(
      AndroidNotificationChannel(
        defaultChannelId,
        names.general,
        description: names.generalDescription,
        importance: Importance.defaultImportance,
      ),
    );
  }

  static PushPayload? _payload(RemoteMessage m) => PushPayload.parse(
    m.data,
    title: m.notification?.title,
    body: m.notification?.body,
  );

  static PushPayload? _decode(String? raw) {
    if (raw == null) return null;
    try {
      final json = jsonDecode(raw);
      return json is Map<String, Object?> ? PushPayload.parse(json) : null;
    } on FormatException {
      return null;
    }
  }

  Future<void> _onForegroundMessage(RemoteMessage m) async {
    final p = _payload(m);
    if (p == null) return;
    _foreground.add(p);
    // Android does not display pushes received in the foreground: show it ourselves.
    if (platform != 'android' || p.title == null) return;
    final channel = p.kind.urgent ? alertChannelId : defaultChannelId;
    await _local.show(
      id: m.messageId.hashCode & 0x7fffffff,
      title: p.title,
      body: p.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          channel,
          channel,
          importance: p.kind.urgent
              ? Importance.max
              : Importance.defaultImportance,
          priority: p.kind.urgent ? Priority.high : Priority.defaultPriority,
          styleInformation: BigTextStyleInformation(p.body ?? ''),
        ),
      ),
      payload: jsonEncode(p.data),
    );
  }

  @override
  Future<String?> token() async {
    try {
      return await _messaging?.getToken();
    } on Object catch (e) {
      _log.info('no push token: ${e.runtimeType}');
      return null;
    }
  }

  @override
  Stream<String> get onTokenRefresh =>
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

final pushMessagingProvider = Provider<PushMessaging>(
  (ref) => FirebasePushMessaging(),
);

/// Whether push works on this phone (false until started, and on builds without Firebase).
final pushAvailableProvider = NotifierProvider<FlagNotifier, bool>(
  FlagNotifier.new,
);
