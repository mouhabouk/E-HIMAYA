import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/alerts/alerts_providers.dart';
import '../../features/reports/reports_providers.dart';
import '../../features/volunteer/volunteer_providers.dart';
import '../auth/identity.dart';
import '../http/api_error.dart';
import '../http/ehimaya_api.dart';
import '../location/location_service.dart';
import '../logging/log.dart';
import '../routing/app_router.dart';
import '../settings/settings_controller.dart';
import '../storage/app_prefs.dart';
import 'push_messaging.dart';
import 'push_payload.dart';

final _log = logger('push');

/// Registers this phone's push token with the server for the current identity (bearer or
/// device key), with its coarse position when the user allows location alerts (FR-A-061).
class DeviceRegistrar {
  DeviceRegistrar(this._ref);

  final Ref _ref;

  AppPrefs get _prefs => _ref.read(appPrefsProvider);

  /// Sends the token (and position) again. Silently skipped without identity or token.
  Future<void> register() async {
    if (!_ref.read(identityProvider).hasIdentity) return;
    final messaging = _ref.read(pushMessagingProvider);
    final token = await messaging.token();
    if (token == null) return;
    final locationAlerts = _prefs.locationAlerts;
    final position = locationAlerts
        ? await _ref.read(locationServiceProvider).withoutPrompt()
        : null;
    try {
      await _ref
          .read(apiProvider)
          .putDevice(
            token: token,
            platform: messaging.platform,
            locale: _ref.read(localeCodeProvider),
            locationAlerts: locationAlerts,
            position: position != null && position.isInTunisiaBox
                ? position
                : null,
          );
      await _prefs.setPushToken(token);
    } on ApiException catch (e) {
      _log.info('device not registered: ${e.code.wire}');
    }
  }

  /// Called before signing out, while the session can still prove whose device it is.
  Future<void> unregister() async {
    final token = _prefs.pushToken;
    if (token == null) return;
    try {
      await _ref.read(apiProvider).deleteDevice(token);
    } on ApiException catch (e) {
      _log.info('device not unregistered: ${e.code.wire}');
    }
    await _prefs.setPushToken(null);
  }
}

final deviceRegistrarProvider = Provider<DeviceRegistrar>(DeviceRegistrar.new);

/// Wires push into the app: registration, refresh of the affected screens when a push arrives,
/// and navigation when one is tapped. Started once from `main()`; widget tests never start it.
class PushController {
  PushController(this._ref);

  final Ref _ref;
  final _subscriptions = <StreamSubscription<Object?>>[];
  bool _started = false;

  Future<void> start(PushChannelNames names) async {
    if (_started) return;
    _started = true;
    final messaging = _ref.read(pushMessagingProvider);
    final available = await messaging.start(names);
    _ref.read(pushAvailableProvider.notifier).set(available);
    if (!available) return;
    final registrar = _ref.read(deviceRegistrarProvider);
    _subscriptions
      ..add(messaging.onTokenRefresh.listen((_) => registrar.register()))
      ..add(messaging.onForeground.listen(handleReceived))
      ..add(messaging.onOpened.listen(handleOpened));
    _ref
      ..listen(identityProvider.select((s) => s.fingerprint), (prev, next) {
        if (next != null && next != prev) registrar.register();
      })
      ..listen(localeCodeProvider, (_, _) => registrar.register());
    await registrar.register();
    final launch = await messaging.launchPayload();
    if (launch != null) handleOpened(launch);
  }

  /// Refreshes what the push is about (the user may be looking at it).
  void handleReceived(PushPayload p) {
    switch (p.kind) {
      case PushKind.alert || PushKind.alertCancelled:
        unawaited(_ref.read(activeAlertsProvider.notifier).refresh());
        _ref.invalidate(inboxProvider);
      case PushKind.info:
        _ref.invalidate(inboxProvider);
      case PushKind.callout:
        _ref.invalidate(myCalloutsProvider);
      case PushKind.reportStatus:
        _ref.invalidate(serverReportsProvider);
    }
  }

  void handleOpened(PushPayload p) {
    handleReceived(p);
    _ref.read(routerProvider).push(p.route);
  }

  void dispose() {
    for (final s in _subscriptions) {
      s.cancel();
    }
  }
}

final pushControllerProvider = Provider<PushController>((ref) {
  final controller = PushController(ref);
  ref.onDispose(controller.dispose);
  return controller;
});
