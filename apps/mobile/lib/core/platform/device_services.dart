import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../logging/log.dart';
import '../power/scheduling.dart';

final _log = logger('device');

/// What the system says about the delivery of our alerts (Android; iOS fills what it can).
/// Every field is null when the platform cannot tell.
class AlertHealth {
  const AlertHealth({
    this.notificationsEnabled,
    this.channelImportance = const {},
    this.doNotDisturb,
    this.policyAccess,
    this.ignoringBatteryOptimizations,
    this.fullScreenIntentAllowed,
  });

  /// App-level switch (POST_NOTIFICATIONS on Android 13+, authorization on iOS).
  final bool? notificationsEnabled;

  /// Importance of each existing Android channel (0 = blocked by the user).
  final Map<String, int> channelImportance;

  /// Do Not Disturb / Focus is filtering notifications right now.
  final bool? doNotDisturb;

  /// The user let the app manage Do Not Disturb (needed for a DND-bypassing channel).
  final bool? policyAccess;
  final bool? ignoringBatteryOptimizations;

  /// Android 14+: USE_FULL_SCREEN_INTENT still granted.
  final bool? fullScreenIntentAllowed;

  static AlertHealth fromMap(Map<Object?, Object?> m) {
    bool? flag(String k) => m[k] is bool ? m[k]! as bool : null;
    final channels = m['channels'];
    return AlertHealth(
      notificationsEnabled: flag('notificationsEnabled'),
      channelImportance: {
        if (channels is Map)
          for (final e in channels.entries)
            if (e.key is String && e.value is int)
              e.key! as String: e.value! as int,
      },
      doNotDisturb: flag('doNotDisturb'),
      policyAccess: flag('policyAccess'),
      ignoringBatteryOptimizations: flag('ignoringBatteryOptimizations'),
      fullScreenIntentAllowed: flag('fullScreenIntentAllowed'),
    );
  }
}

/// Small native bridge (MainActivity.kt / AppDelegate.swift) for what no pinned plugin offers:
/// battery level, Do Not Disturb state, battery optimisation, channel settings. Avoids adding
/// battery_plus or a permissions package.
abstract class DeviceServices {
  Future<BatteryReading?> battery();
  Future<AlertHealth> alertHealth();

  /// Opens the system settings of one notification channel (Android 8+), else the app's
  /// notification settings.
  Future<bool> openChannelSettings(String channelId);
  Future<bool> openAppNotificationSettings();

  /// Shows the system dialog that exempts the app from battery optimisation (Android).
  Future<bool> requestIgnoreBatteryOptimizations();

  /// Android 14+: the "Full screen notifications" special access page.
  Future<bool> openFullScreenIntentSettings();

  /// The "Do Not Disturb access" page, where the user grants notification policy access.
  Future<bool> openDndAccessSettings();

  /// Android: the app is displayed over a locked phone (opened by a severe alert's full-screen
  /// intent). Only the public alert view may then be shown.
  Future<bool> lockedAlertMode();

  /// Asks the user to unlock the phone. True once unlocked (the app then stops showing over the
  /// lock screen), false when cancelled.
  Future<bool> requestUnlock();

  /// Keeps the screen on (and the activity in front) while live streaming (phase 6); off again
  /// when the stream ends.
  Future<void> keepScreenOn(bool on);

  /// The app's page in the system settings (camera or microphone refused for good).
  Future<bool> openAppSettings();

  /// Phase B2: the system contact picker. Only the chosen number reaches the app (no contacts
  /// permission). Null when cancelled or unavailable.
  Future<PickedContact?> pickContact();

  /// Phase B2: the phone's own lock (PIN, pattern, fingerprint) before the medical file opens.
  /// True when confirmed, false when cancelled, null when the phone has no secure lock.
  Future<bool?> confirmCredential({String? title, String? description});

  /// Phase B2: the shortcut chosen on a long press of the icon (`sos_message`, `report`), once.
  Future<String?> takeShortcut();
}

/// One number chosen in the system contact picker.
class PickedContact {
  const PickedContact({required this.name, required this.phone});

  final String name;
  final String phone;
}

class PlatformDeviceServices implements DeviceServices {
  const PlatformDeviceServices([
    this._channel = const MethodChannel('tn.ehimaya.app/device'),
  ]);

  final MethodChannel _channel;

  Future<T?> _call<T>(String method, [Object? args]) async {
    try {
      return await _channel.invokeMethod<T>(method, args);
    } on MissingPluginException {
      return null;
    } on PlatformException catch (e) {
      _log.info('$method failed: ${e.code}');
      return null;
    }
  }

  @override
  Future<BatteryReading?> battery() async {
    final m = await _call<Map<Object?, Object?>>('battery');
    if (m == null) return null;
    final level = m['level'];
    return BatteryReading(
      level: level is int && level >= 0 && level <= 100 ? level : null,
      charging: m['charging'] == true,
      systemPowerSave: m['powerSave'] == true,
    );
  }

  @override
  Future<AlertHealth> alertHealth() async {
    final m = await _call<Map<Object?, Object?>>('alertHealth');
    return m == null ? const AlertHealth() : AlertHealth.fromMap(m);
  }

  @override
  Future<bool> openChannelSettings(String channelId) async =>
      await _call<bool>('openChannelSettings', {'channelId': channelId}) ??
      false;

  @override
  Future<bool> openAppNotificationSettings() async =>
      await _call<bool>('openAppNotificationSettings') ?? false;

  @override
  Future<bool> requestIgnoreBatteryOptimizations() async =>
      await _call<bool>('requestIgnoreBatteryOptimizations') ?? false;

  @override
  Future<bool> openFullScreenIntentSettings() async =>
      await _call<bool>('openFullScreenIntentSettings') ?? false;

  @override
  Future<bool> openDndAccessSettings() async =>
      await _call<bool>('openDndAccessSettings') ?? false;

  @override
  Future<bool> lockedAlertMode() async =>
      await _call<bool>('lockedAlertMode') ?? false;

  /// Fails closed: an error keeps the phone treated as locked.
  @override
  Future<bool> requestUnlock() async =>
      await _call<bool>('requestUnlock') ?? false;

  @override
  Future<void> keepScreenOn(bool on) async {
    await _call<bool>('keepScreenOn', {'on': on});
  }

  @override
  Future<bool> openAppSettings() async =>
      await _call<bool>('openAppSettings') ?? false;

  @override
  Future<PickedContact?> pickContact() async {
    final m = await _call<Map<Object?, Object?>>('pickContact');
    final phone = m?['phone'];
    if (phone is! String || phone.trim().isEmpty) return null;
    final name = m?['name'];
    return PickedContact(
      name: name is String && name.trim().isNotEmpty ? name.trim() : phone,
      phone: phone.trim(),
    );
  }

  /// A failed call counts as cancelled (never as "no lock", which would open the file).
  @override
  Future<bool?> confirmCredential({String? title, String? description}) async {
    try {
      return await _channel.invokeMethod<bool>('confirmCredential', {
        'title': title,
        'description': description,
      });
    } on MissingPluginException {
      return null;
    } on PlatformException catch (e) {
      _log.info('confirmCredential failed: ${e.code}');
      return false;
    }
  }

  @override
  Future<String?> takeShortcut() => _call<String>('takeShortcut');
}

final deviceServicesProvider = Provider<DeviceServices>(
  (ref) => const PlatformDeviceServices(),
);
