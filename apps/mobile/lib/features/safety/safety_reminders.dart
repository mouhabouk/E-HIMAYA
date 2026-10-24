import 'dart:convert';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timezone/timezone.dart' as tz;

import '../../core/logging/log.dart';
import '../../core/push/push_messaging.dart';
import '../../core/push/push_notifications.dart';
import '../../core/push/push_payload.dart';

final _log = logger('safety.reminders');

/// The two reminder texts of the current language.
typedef ReminderTexts = ({String title, String tenMinutes, String oneMinute});

/// Addition 8.1: the phone reminds the user 10 minutes and 1 minute before a safety check ends.
/// The alert itself is the server's (it goes even if the phone is off), so these reminders may
/// come a little late on a sleeping phone (inexact alarms, no special permission).
abstract class SafetyReminders {
  Future<void> schedule(DateTime dueAt, ReminderTexts texts);
  Future<void> cancel();
}

/// Times of the reminders still in the future, newest last.
List<(int, DateTime, bool)> reminderTimes(DateTime dueAt, DateTime now) => [
  (
    LocalSafetyReminders.tenMinutesId,
    dueAt.subtract(const Duration(minutes: 10)),
    true,
  ),
  (
    LocalSafetyReminders.oneMinuteId,
    dueAt.subtract(const Duration(minutes: 1)),
    false,
  ),
].where((r) => r.$2.isAfter(now)).toList();

class LocalSafetyReminders implements SafetyReminders {
  LocalSafetyReminders(this._notifications);

  static const tenMinutesId = 0x5AFE10;
  static const oneMinuteId = 0x5AFE01;

  final PushNotifications _notifications;

  FlutterLocalNotificationsPlugin? get _plugin =>
      _notifications is LocalPushNotifications ? _notifications.plugin : null;

  @override
  Future<void> schedule(DateTime dueAt, ReminderTexts texts) async {
    final plugin = _plugin;
    if (plugin == null) return;
    await cancel();
    final payload = jsonEncode({'type': PushKind.safetyCheckReminder.wire});
    for (final (id, at, ten) in reminderTimes(dueAt, DateTime.now())) {
      try {
        await plugin.zonedSchedule(
          id: id,
          title: texts.title,
          body: ten ? texts.tenMinutes : texts.oneMinute,
          scheduledDate: tz.TZDateTime.from(at.toUtc(), tz.UTC),
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
          payload: payload,
          notificationDetails: NotificationDetails(
            android: AndroidNotificationDetails(
              alertChannelId,
              texts.title,
              importance: Importance.max,
              priority: Priority.max,
              category: AndroidNotificationCategory.reminder,
              visibility: NotificationVisibility.private,
            ),
            iOS: const DarwinNotificationDetails(
              presentAlert: true,
              presentSound: true,
              interruptionLevel: InterruptionLevel.timeSensitive,
            ),
          ),
        );
      } on Object catch (e) {
        _log.info('reminder not scheduled: ${e.runtimeType}');
      }
    }
  }

  @override
  Future<void> cancel() async {
    final plugin = _plugin;
    if (plugin == null) return;
    try {
      await plugin.cancel(id: tenMinutesId);
      await plugin.cancel(id: oneMinuteId);
    } on Object catch (e) {
      _log.info('reminders not cancelled: ${e.runtimeType}');
    }
  }
}

final safetyRemindersProvider = Provider<SafetyReminders>(
  (ref) => LocalSafetyReminders(ref.watch(pushNotificationsProvider)),
);
