import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/identity.dart';
import '../connectivity/connectivity.dart';
import '../http/api_error.dart';
import '../http/ehimaya_api.dart';
import '../http/models.dart';
import '../logging/log.dart';
import '../storage/app_prefs.dart';
import 'anon_quota.dart';

final _log = logger('quota');

/// Last anonymous quota announced by the server (phase 9 §3), kept across restarts so the app
/// can warn offline. Updated by the sync engine after every accepted (or quota-refused) report
/// and by [refresh] (`GET /api/v1/reports/quota`) when the app starts online.
class AnonQuotaController extends Notifier<AnonQuota?> {
  @override
  AnonQuota? build() {
    final prefs = ref.watch(appPrefsProvider);
    final remaining = prefs.anonQuotaRemaining;
    if (remaining == null) return null;
    return AnonQuota(limit: prefs.anonQuotaLimit, remaining: remaining);
  }

  /// Stores what the server said (a missing limit keeps the one already known).
  Future<void> record(AnonQuota quota) async {
    final next = quota.mergedWith(state);
    state = next;
    await ref
        .read(appPrefsProvider)
        .setAnonQuota(limit: next.limit, remaining: next.remaining);
  }

  /// Registered accounts have no quota.
  Future<void> clear() async {
    state = null;
    await ref.read(appPrefsProvider).setAnonQuota();
  }

  /// Asks the server. Failures keep the last known value: the quota is only a warning on the
  /// device, the server decides.
  Future<void> refresh() async {
    try {
      final quota = await ref.read(apiProvider).reportQuota();
      if (quota == null) {
        await clear();
      } else {
        await record(quota);
      }
    } on ApiException catch (e) {
      _log.fine('quota not refreshed: ${e.code.wire}');
    }
  }
}

final anonQuotaProvider = NotifierProvider<AnonQuotaController, AnonQuota?>(
  AnonQuotaController.new,
);

/// `GET /api/v1/reports/quota` once on start (and again after the identity changes) when the
/// installation reports anonymously and a network is up. Watched by the quota cards.
final anonQuotaStartupProvider = FutureProvider<void>((ref) async {
  final anonymous = ref.watch(identityProvider.select((i) => i.isAnonymous));
  if (!anonymous) return;
  if (!await ref.read(connectivityProvider).isOnline()) return;
  await ref.read(anonQuotaProvider.notifier).refresh();
});

/// Whether a new report must not be queued for sending now: an anonymous installation whose
/// last known quota is exhausted, for any category but SOS. An SOS is never gated on the
/// device (the server accepts it beyond the quota and flags it, phase 9 §3).
bool anonQuotaBlocks({
  required IdentityState identity,
  required ReportCategory category,
  required AnonQuota? quota,
}) =>
    identity.isAnonymous &&
    category != ReportCategory.sos &&
    (quota?.exhausted ?? false);
