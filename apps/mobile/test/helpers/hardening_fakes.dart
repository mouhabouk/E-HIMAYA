import 'dart:async';

import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_notifications.dart';
import 'package:ehimaya/core/push/push_payload.dart';

/// Native bridge stand-in: fixed battery and alert health, records what was opened.
class FakeDeviceServices implements DeviceServices {
  FakeDeviceServices({
    this.reading,
    this.health = const AlertHealth(),
    this.locked = false,
    this.unlockSucceeds = true,
  });

  BatteryReading? reading;
  AlertHealth health;
  final opened = <String>[];

  /// Displayed over a locked phone; [requestUnlock] clears it when [unlockSucceeds].
  bool locked;
  bool unlockSucceeds;
  int unlockRequests = 0;

  @override
  Future<bool> lockedAlertMode() async => locked;

  @override
  Future<bool> requestUnlock() async {
    unlockRequests++;
    if (unlockSucceeds) locked = false;
    return unlockSucceeds;
  }

  @override
  Future<BatteryReading?> battery() async => reading;
  @override
  Future<AlertHealth> alertHealth() async => health;
  @override
  Future<bool> openChannelSettings(String channelId) async {
    opened.add('channel:$channelId');
    return true;
  }

  @override
  Future<bool> openAppNotificationSettings() async {
    opened.add('app-notifications');
    return true;
  }

  @override
  Future<bool> requestIgnoreBatteryOptimizations() async {
    opened.add('battery-optimizations');
    return true;
  }

  @override
  Future<bool> openFullScreenIntentSettings() async {
    opened.add('full-screen');
    return true;
  }

  @override
  Future<bool> openDndAccessSettings() async {
    opened.add('dnd-access');
    return true;
  }

  /// History of [keepScreenOn] calls (live streaming).
  final screenOn = <bool>[];

  @override
  Future<void> keepScreenOn(bool on) async => screenOn.add(on);

  @override
  Future<bool> openAppSettings() async {
    opened.add('app-settings');
    return true;
  }
}

class ShownNotification {
  ShownNotification(this.id, this.payload, this.channelId);
  final int id;
  final PushPayload payload;
  final String? channelId;
}

/// Records the local notifications shown.
class RecordingNotifications implements PushNotifications {
  final shown = <ShownNotification>[];

  @override
  Future<PushPayload?> init(
    PushChannelNames names, {
    required void Function(PushPayload payload) onTap,
  }) async => null;

  @override
  Future<void> requestPermission() async {}

  @override
  Future<void> show(int id, PushPayload payload, {String? channelId}) async =>
      shown.add(ShownNotification(id, payload, channelId));
}

/// Connectivity whose state the test drives.
class ControlledConnectivity implements ConnectivityMonitor {
  ControlledConnectivity({
    this.online = true,
    this.kind = NetworkKind.unmetered,
  });

  bool online;
  NetworkKind kind;
  final _changes = StreamController<bool>.broadcast();

  void set(bool value) {
    online = value;
    _changes.add(value);
  }

  @override
  Stream<bool> get onlineChanges => _changes.stream;
  @override
  Future<bool> isOnline() async => online;
  @override
  Future<NetworkKind> networkKind() async => online ? kind : NetworkKind.none;
}

/// Location granted, at a position the test moves.
class MovableLocation extends LocationService {
  MovableLocation(this.fix);

  GeoPoint? fix;
  int watchCalls = 0;

  @override
  Future<LocationAvailability> ensurePermission() async =>
      LocationAvailability.granted;
  @override
  Future<GeoPoint?> current({Duration timeout = Duration.zero}) async => fix;
  @override
  Future<GeoPoint?> lastKnown() async => fix;
  @override
  Future<GeoPoint?> withoutPrompt() async => fix;
  @override
  Stream<GeoPoint> watch({bool lowPower = false}) {
    watchCalls++;
    return const Stream.empty();
  }
}
