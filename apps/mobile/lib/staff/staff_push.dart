import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/logging/log.dart';
import '../core/push/push_messaging.dart' show firebaseOptionsFromEnvironment;
import '../core/push/push_notifications.dart'
    show alertSoundAndroid, alertVibrationPattern, alertLightColor;

final _log = logger('staff.push');

/// The leader's mission channel (phase P4d, design §9.4): rings on the alarm stream and opens full
/// screen on a locked phone. Versioned like the citizen app's channels.
const staffMissionChannelId = 'ehimaya_staff_missions_v1';

/// The notification of the mission that rings (one at a time: the newest replaces it).
const _missionNotificationId = 4401;

/// The mission push of the staff app. The server sends it data-only on Android (`type: mission`,
/// the assignment id, a generic title and text): the app shows it itself, full screen.
abstract class StaffPush {
  /// Starts push and returns the phone's token, or null on a build without push.
  Future<String?> start(String channelName);

  Stream<String> get onTokenRefresh;

  /// A mission push received while the app is open: the missions are fetched at once.
  Stream<void> get onMission;
}

class NoStaffPush implements StaffPush {
  const NoStaffPush();

  @override
  Future<String?> start(String channelName) async => null;
  @override
  Stream<String> get onTokenRefresh => const Stream.empty();
  @override
  Stream<void> get onMission => const Stream.empty();
}

AndroidNotificationDetails _missionDetails(String channelName) =>
    AndroidNotificationDetails(
      staffMissionChannelId,
      channelName,
      importance: Importance.max,
      priority: Priority.max,
      category: AndroidNotificationCategory.alarm,
      // A locked phone shows the mission full screen until the leader opens it.
      fullScreenIntent: true,
      visibility: NotificationVisibility.private,
      audioAttributesUsage: AudioAttributesUsage.alarm,
      sound: const RawResourceAndroidNotificationSound(alertSoundAndroid),
      vibrationPattern: alertVibrationPattern,
      enableLights: true,
      ledColor: alertLightColor,
      ledOnMs: 500,
      ledOffMs: 500,
      ongoing: true,
      autoCancel: true,
    );

Future<void> _showMission(
  FlutterLocalNotificationsPlugin local,
  Map<String, dynamic> data,
  String channelName,
) async {
  final title = data['title'];
  final body = data['body'];
  await local.show(
    id: _missionNotificationId,
    title: title is String ? title : null,
    body: body is String ? body : null,
    notificationDetails: NotificationDetails(
      android: _missionDetails(channelName),
      iOS: const DarwinNotificationDetails(
        presentAlert: true,
        presentSound: true,
        interruptionLevel: InterruptionLevel.timeSensitive,
      ),
    ),
    payload: 'mission',
  );
}

/// A data-only mission push while the app is in the background or killed (Android).
@pragma('vm:entry-point')
Future<void> staffBackgroundMessage(RemoteMessage m) async {
  if (m.notification != null || m.data['type'] != 'mission') return;
  final local = FlutterLocalNotificationsPlugin();
  await local.initialize(
    settings: const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
      ),
    ),
  );
  // The channel was created by the app; its name is the system's copy.
  await _showMission(local, m.data, 'e-Himaya');
}

class FirebaseStaffPush implements StaffPush {
  FirebaseStaffPush({FirebaseOptions? options})
    : _options = options ?? firebaseOptionsFromEnvironment();

  final FirebaseOptions? _options;
  final _local = FlutterLocalNotificationsPlugin();
  final _missions = StreamController<void>.broadcast();
  FirebaseMessaging? _messaging;

  @override
  Future<String?> start(String channelName) async {
    try {
      if (_messaging == null) {
        if (Firebase.apps.isEmpty) {
          final options = _options;
          if (options == null && defaultTargetPlatform != TargetPlatform.iOS) {
            _log.info('push not configured on this build');
            return null;
          }
          await Firebase.initializeApp(options: options);
        }
        FirebaseMessaging.onBackgroundMessage(staffBackgroundMessage);
        await _local.initialize(
          settings: const InitializationSettings(
            android: AndroidInitializationSettings('@mipmap/ic_launcher'),
            iOS: DarwinInitializationSettings(),
          ),
        );
        final android = _local
            .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin
            >();
        await android?.createNotificationChannel(
          AndroidNotificationChannel(
            staffMissionChannelId,
            channelName,
            importance: Importance.max,
            sound: const RawResourceAndroidNotificationSound(alertSoundAndroid),
            vibrationPattern: alertVibrationPattern,
            enableLights: true,
            ledColor: alertLightColor,
            audioAttributesUsage: AudioAttributesUsage.alarm,
          ),
        );
        await android?.requestFullScreenIntentPermission();
        final messaging = FirebaseMessaging.instance;
        await messaging.requestPermission();
        FirebaseMessaging.onMessage.listen((m) {
          if (m.data['type'] == 'mission') _missions.add(null);
        });
        _messaging = messaging;
      }
      // Kept with the citizen app's getToken() until the API sends to Installation IDs.
      // ignore: deprecated_member_use
      return await _messaging?.getToken();
    } on Object catch (e, st) {
      _log.warning('staff push unavailable', e, st);
      return null;
    }
  }

  @override
  Stream<String> get onTokenRefresh =>
      // ignore: deprecated_member_use
      _messaging?.onTokenRefresh ?? const Stream.empty();

  @override
  Stream<void> get onMission => _missions.stream;
}

final staffPushProvider = Provider<StaffPush>(
  (ref) => kIsWeb ? const NoStaffPush() : FirebaseStaffPush(),
);
