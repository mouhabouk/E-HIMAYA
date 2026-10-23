import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui' show Color;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'push_dedup.dart';
import 'push_messaging.dart';
import 'push_payload.dart';

/// Vibration of official alerts: long-short-long, unlike any messaging app.
final alertVibrationPattern = Int64List.fromList([0, 700, 250, 700, 250, 1400]);

/// Red notification light (on phones that still have one).
const alertLightColor = Color(0xFFD32F2F);

/// Android raw resource / iOS bundle sound of official alerts (res/raw/ehimaya_alert.ogg,
/// ios/Runner/alert.caf). The server names the iOS file in the APNs payload.
const alertSoundAndroid = 'ehimaya_alert';
const alertSoundIos = 'alert.caf';

/// Our notifications form their own group: never bundled with another app's (Android groups
/// per app; the key also keeps alerts apart from ordinary messages of ours).
const alertGroupKey = 'tn.ehimaya.app.alerts';

/// iOS notification categories (also set by the server as `category` when it sends them).
abstract final class IosCategories {
  static const alert = 'EHIMAYA_ALERT';
  static const callout = 'EHIMAYA_CALLOUT';
  static const general = 'EHIMAYA_GENERAL';
}

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

  /// Shows [payload] on [channelId] (its kind's channel when null or unknown). Showing again
  /// with the same [id] replaces the notification without ringing again.
  Future<void> show(int id, PushPayload payload, {String? channelId});
}

/// [PushNotifications] backed by `flutter_local_notifications`.
class LocalPushNotifications implements PushNotifications {
  LocalPushNotifications([FlutterLocalNotificationsPlugin? plugin])
    : _local = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _local;
  PushChannelNames? _names;
  bool _critical = false;

  AndroidFlutterLocalNotificationsPlugin? get _android => _local
      .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
      >();

  /// The plugin, for the settings screens (permission requests, policy access).
  FlutterLocalNotificationsPlugin get plugin => _local;

  /// Whether the Do Not Disturb-bypassing channel exists (user opted in).
  bool get criticalEnabled => _critical;

  static final _iosCategories = [
    DarwinNotificationCategory(
      IosCategories.alert,
      options: {DarwinNotificationCategoryOption.hiddenPreviewShowTitle},
    ),
    DarwinNotificationCategory(
      IosCategories.callout,
      options: {DarwinNotificationCategoryOption.hiddenPreviewShowTitle},
    ),
    DarwinNotificationCategory(IosCategories.general),
  ];

  static AndroidNotificationChannel _alertChannel(PushChannelNames names) =>
      AndroidNotificationChannel(
        alertChannelId,
        names.alerts,
        description: names.alertsDescription,
        importance: Importance.max,
        sound: const RawResourceAndroidNotificationSound(alertSoundAndroid),
        vibrationPattern: alertVibrationPattern,
        enableLights: true,
        ledColor: alertLightColor,
      );

  static AndroidNotificationChannel _criticalChannel(PushChannelNames names) =>
      AndroidNotificationChannel(
        criticalChannelId,
        names.critical,
        description: names.criticalDescription,
        importance: Importance.max,
        bypassDnd: true,
        sound: const RawResourceAndroidNotificationSound(alertSoundAndroid),
        vibrationPattern: alertVibrationPattern,
        enableLights: true,
        ledColor: alertLightColor,
        // Plays on the alarm stream: audible even with the ringer on silent.
        audioAttributesUsage: AudioAttributesUsage.alarm,
      );

  /// Initialises the plugin only (background isolate): no channel work, no tap handler.
  /// [criticalOptIn] is the stored opt-in (the channel itself was created by the app).
  Future<void> initBackground({bool? criticalOptIn}) async {
    _critical = criticalOptIn ?? false;
    await _local.initialize(
      settings: InitializationSettings(
        android: const AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false,
          notificationCategories: _iosCategories,
        ),
      ),
    );
  }

  @override
  Future<PushPayload?> init(
    PushChannelNames names, {
    required void Function(PushPayload payload) onTap,
  }) async {
    _names = names;
    await _local.initialize(
      settings: InitializationSettings(
        android: const AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(
          requestAlertPermission: false,
          requestBadgePermission: false,
          requestSoundPermission: false,
          // ┃ Critical alerts (sound through mute and Focus) need Apple's
          // ┃ com.apple.developer.usernotifications.critical-alerts entitlement, granted on
          // ┃ request to public-safety apps. Once granted: add it to Runner.entitlements, set
          // ┃ requestCriticalPermission: true here, and use InterruptionLevel.critical for
          // ┃ severe alerts in [show] (server: aps.interruption-level "critical" and
          // ┃ aps.sound {critical: 1, name: "alert.caf", volume: 1}).
          requestCriticalPermission: false,
          notificationCategories: _iosCategories,
        ),
      ),
      onDidReceiveNotificationResponse: (response) {
        final p = decodePushPayload(response.payload);
        if (p != null) onTap(p);
      },
    );
    final android = _android;
    if (android != null) {
      for (final id in legacyChannelIds) {
        await android.deleteNotificationChannel(channelId: id);
      }
      await android.createNotificationChannel(_alertChannel(names));
      await android.createNotificationChannel(
        AndroidNotificationChannel(
          defaultChannelId,
          names.general,
          description: names.generalDescription,
          importance: Importance.defaultImportance,
        ),
      );
      final channels = await android.getNotificationChannels() ?? const [];
      _critical = channels.any((c) => c.id == criticalChannelId);
    }
    final launch = await _local.getNotificationAppLaunchDetails();
    if (!(launch?.didNotificationLaunchApp ?? false)) return null;
    return decodePushPayload(launch!.notificationResponse?.payload);
  }

  /// Creates (opt-in) or deletes (opt-out) the Do Not Disturb-bypassing channel. Android
  /// ignores bypassDnd without notification policy access, so the caller asks for it first.
  /// Returns whether the channel now exists.
  Future<bool> setCriticalChannel(bool enabled) async {
    final android = _android;
    final names = _names;
    if (android == null) return false;
    if (!enabled || names == null) {
      await android.deleteNotificationChannel(channelId: criticalChannelId);
      return _critical = false;
    }
    await android.createNotificationChannel(_criticalChannel(names));
    return _critical = true;
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
    final channel = pushChannelFor(payload, channelId, _critical);
    final urgent = channel != defaultChannelId;
    // Official alerts are public; personal pushes (call-outs, reports, messages) show only
    // their app name on a locked screen, even once their text was resolved on the phone.
    final public =
        payload.kind == PushKind.alert ||
        payload.kind == PushKind.alertCancelled;
    final names = _names;
    final tag = pushSubject(payload);
    // The same subject shown by the system in the background (FCM: this tag, id 0).
    await _cancelSystemShown(tag);
    if (payload.kind == PushKind.alertCancelled) {
      // A lifted alert removes the alert's own notification.
      final alertTag = pushSubject(
        PushPayload(kind: PushKind.alert, data: payload.data),
      );
      await _cancelSystemShown(alertTag);
      await _local.cancel(
        id: notificationIdFor(
          PushPayload(kind: PushKind.alert, data: payload.data),
        ),
        tag: alertTag,
      );
    }
    final channelName = switch (channel) {
      alertChannelId => names?.alerts,
      criticalChannelId => names?.critical,
      _ => names?.general,
    };
    await _local.show(
      id: id,
      title: payload.title,
      body: payload.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          channel,
          channelName ?? channel,
          importance: urgent ? Importance.max : Importance.defaultImportance,
          priority: urgent ? Priority.max : Priority.defaultPriority,
          category:
              channel == criticalChannelId ||
                  payload.severe ||
                  payload.kind == PushKind.safetyAlert
              ? AndroidNotificationCategory.alarm
              : (urgent
                    ? AndroidNotificationCategory.event
                    : AndroidNotificationCategory.status),
          // Readable on the lock screen: official alerts are public information; personal
          // pushes are content-free (A8) until resolved on the phone.
          visibility: public
              ? NotificationVisibility.public
              : NotificationVisibility.private,
          fullScreenIntent: payload.severe,
          groupKey: urgent ? alertGroupKey : null,
          tag: tag,
          onlyAlertOnce: true,
          sound: urgent
              ? const RawResourceAndroidNotificationSound(alertSoundAndroid)
              : null,
          vibrationPattern: urgent ? alertVibrationPattern : null,
          enableLights: urgent,
          ledColor: urgent ? alertLightColor : null,
          ledOnMs: urgent ? 500 : null,
          ledOffMs: urgent ? 500 : null,
          color: urgent ? alertLightColor : null,
          ticker: payload.title,
          styleInformation: BigTextStyleInformation(payload.body ?? ''),
        ),
        iOS: DarwinNotificationDetails(
          presentAlert: true,
          presentBanner: true,
          presentList: true,
          presentSound: urgent,
          sound: urgent ? alertSoundIos : null,
          categoryIdentifier: switch (payload.kind) {
            PushKind.alert || PushKind.alertCancelled => IosCategories.alert,
            PushKind.callout => IosCategories.callout,
            _ => IosCategories.general,
          },
          threadIdentifier: tag,
          // Through Focus modes (Time Sensitive Notifications capability); see the critical
          // alerts note in [init].
          interruptionLevel: urgent
              ? InterruptionLevel.timeSensitive
              : InterruptionLevel.active,
        ),
      ),
      payload: jsonEncode(payload.data),
    );
  }
}

extension on LocalPushNotifications {
  Future<void> _cancelSystemShown(String tag) async {
    try {
      await _local.cancel(id: 0, tag: tag);
    } on Object {
      // Nothing to cancel, or not on Android.
    }
  }
}

/// The Android channel for [payload]: [requested] when it is one of ours (the legacy alerts id
/// maps to the current one), else by kind. The most severe alerts use the Do Not Disturb
/// channel only when it exists ([criticalAvailable], the user opted in).
String pushChannelFor(
  PushPayload payload, [
  String? requested,
  bool criticalAvailable = false,
]) {
  if (payload.severe && criticalAvailable) return criticalChannelId;
  // Phase B2: a linked contact in distress rings through Do Not Disturb when the user opted in.
  if (payload.kind == PushKind.safetyAlert) {
    return criticalAvailable ? criticalChannelId : alertChannelId;
  }
  if (requested == criticalChannelId) {
    return criticalAvailable ? criticalChannelId : alertChannelId;
  }
  if (requested == alertChannelId || legacyChannelIds.contains(requested)) {
    return alertChannelId;
  }
  if (requested == defaultChannelId) return defaultChannelId;
  return payload.kind.urgent ? alertChannelId : defaultChannelId;
}

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
