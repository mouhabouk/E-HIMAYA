import 'dart:convert';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'push_messaging.dart';
import 'push_payload.dart';

/// Displays pushes as local notifications. Shared by every [PushMessaging] implementation so
/// the Android channels, their importance and the tap payload are the same everywhere.
abstract class PushNotifications {
  /// Initialises the plugin and creates the Android channels. Taps on a notification are
  /// reported to [onTap]. Returns the payload of the notification that launched the app.
  Future<PushPayload?> init(
    PushChannelNames names, {
    required void Function(PushPayload payload) onTap,
  });

  /// Asks the system for permission to show notifications (Android 13+, iOS).
  Future<void> requestPermission();

  /// Shows [payload] on [channelId] (its kind's channel when null or unknown).
  Future<void> show(int id, PushPayload payload, {String? channelId});
}

/// [PushNotifications] backed by `flutter_local_notifications`.
class LocalPushNotifications implements PushNotifications {
  LocalPushNotifications([FlutterLocalNotificationsPlugin? plugin])
    : _local = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _local;

  AndroidFlutterLocalNotificationsPlugin? get _android => _local
      .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
      >();

  @override
  Future<PushPayload?> init(
    PushChannelNames names, {
    required void Function(PushPayload payload) onTap,
  }) async {
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
        final p = decodePushPayload(response.payload);
        if (p != null) onTap(p);
      },
    );
    await _android?.createNotificationChannel(
      AndroidNotificationChannel(
        alertChannelId,
        names.alerts,
        description: names.alertsDescription,
        importance: Importance.max,
      ),
    );
    await _android?.createNotificationChannel(
      AndroidNotificationChannel(
        defaultChannelId,
        names.general,
        description: names.generalDescription,
        importance: Importance.defaultImportance,
      ),
    );
    final launch = await _local.getNotificationAppLaunchDetails();
    if (!(launch?.didNotificationLaunchApp ?? false)) return null;
    return decodePushPayload(launch!.notificationResponse?.payload);
  }

  @override
  Future<void> requestPermission() async {
    await _android?.requestNotificationsPermission();
    await _local
        .resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin
        >()
        ?.requestPermissions(alert: true, badge: true, sound: true);
  }

  @override
  Future<void> show(int id, PushPayload payload, {String? channelId}) async {
    final channel = pushChannelFor(payload, channelId);
    final urgent = channel == alertChannelId;
    await _local.show(
      id: id,
      title: payload.title,
      body: payload.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          channel,
          channel,
          importance: urgent ? Importance.max : Importance.defaultImportance,
          priority: urgent ? Priority.high : Priority.defaultPriority,
          styleInformation: BigTextStyleInformation(payload.body ?? ''),
        ),
        iOS: DarwinNotificationDetails(presentSound: urgent),
      ),
      payload: jsonEncode(payload.data),
    );
  }
}

/// The Android channel for [payload]: [requested] when it is one of ours, else by kind.
String pushChannelFor(PushPayload payload, [String? requested]) =>
    requested == alertChannelId || requested == defaultChannelId
    ? requested!
    : (payload.kind.urgent ? alertChannelId : defaultChannelId);

/// Reads back the payload stored on a local notification (null when absent or malformed).
PushPayload? decodePushPayload(String? raw) {
  if (raw == null) return null;
  try {
    final json = jsonDecode(raw);
    return json is Map<String, Object?> ? PushPayload.parse(json) : null;
  } on FormatException {
    return null;
  }
}
