import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/db/open_database.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/identity/device_key.dart';
import '../../core/logging/log.dart';
import '../../core/push/push_messaging.dart';
import '../../core/push/push_notifications.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/storage/secure_store.dart';
import '../../core/sync/report_queue.dart';
import '../charter/charter_controller.dart';

final _log = logger('privacy');

/// A6, the citizen's rights on the phone: a copy of their data, and deleting their account.
class CitizenRights {
  CitizenRights(this._ref);

  final Ref _ref;

  /// `GET /api/v1/me/export`, as indented JSON text.
  Future<String> exportData() => _ref.read(apiProvider).exportMyData();

  /// `POST /api/v1/me/delete`, then wipes everything the phone kept about the user. Throws
  /// [LastAdminException] or [ApiException] when the server refused or could not be reached:
  /// nothing is wiped then. After a deletion the same token or device key would resolve to a
  /// new, empty account, so the session is dropped (signed out locally) and the device key
  /// forgotten (a new one is generated if the user continues anonymously).
  Future<void> deleteAccount() async {
    await _ref.read(apiProvider).deleteMyAccount();
    await wipeLocalData();
  }

  /// Forgets the user on this phone: the offline queue and its media files, the emergency contacts,
  /// the alert history and the medical file (phase B2), the session, the
  /// anonymous device key, the cached institutions, notifications already shown, and every
  /// preference except the language, the theme and the battery saver choice. The encrypted
  /// database itself stays (empty) with its key, so the app keeps working.
  Future<void> wipeLocalData() async {
    final db = _ref.read(databaseProvider);
    await db.transaction(() async {
      await db.delete(db.mediaItems).go();
      await db.delete(db.pendingReports).go();
      // Phase B2: emergency contacts and groups, the alert history and the medical file.
      await db.delete(db.emergencyContacts).go();
      await db.delete(db.contactGroups).go();
      await db.delete(db.safetyAlertHistory).go();
      await db.delete(db.medicalProfiles).go();
    });
    try {
      final dir = await _ref.read(mediaDirProvider)();
      // Synchronous: a handful of files, and the wipe must not depend on the event loop.
      if (dir.existsSync()) dir.deleteSync(recursive: true);
    } on Object catch (e) {
      // Never block the wipe on the media folder (files are also unreadable without the queue).
      _log.info('media not deleted: ${e.runtimeType}');
    }
    final secure = _ref.read(secureStoreProvider);
    await secure.delete(SecureStoreKeys.authSession);
    await secure.delete(SecureStoreKeys.orgCache);
    await secure.delete(SecureStoreKeys.rewardsCache);
    await _ref.read(deviceKeyStoreProvider).forget();
    final notifications = _ref.read(pushNotificationsProvider);
    if (notifications is LocalPushNotifications) {
      try {
        await notifications.plugin.cancelAll();
      } on Object catch (e) {
        _log.info('notifications not cleared: ${e.runtimeType}');
      }
    }
    await _ref.read(appPrefsProvider).wipeForAccountDeletion();
    _ref.read(identityProvider.notifier).resetAfterAccountDeletion();
    _ref
      ..invalidate(charterAcceptedProvider)
      ..invalidate(profilePromptedProvider);
  }
}

final citizenRightsProvider = Provider<CitizenRights>(CitizenRights.new);
