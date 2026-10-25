import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/http/notify_models.dart';
import '../../core/logging/log.dart';
import '../../core/storage/app_prefs.dart';
import '../../core/storage/secure_store.dart';

final _log = logger('institutions');

/// Offline copy of the account's institutions and of the last summary seen for each one
/// (FR-A-081). Kept in the platform keystore with the other account data (the safety team's
/// phone numbers are personal data) and tied to the identity that fetched it: another account
/// on the same phone never sees it, and signing out deletes it.
class OrgCache {
  OrgCache(this._store);

  final SecureStore _store;
  Future<void> _lock = Future.value();

  Future<Map<String, Object?>> _read(String owner) async {
    final raw = await _store.read(SecureStoreKeys.orgCache);
    if (raw == null) return {};
    try {
      final json = jsonDecode(raw);
      if (json is Map<String, Object?> && json['owner'] == owner) return json;
    } on FormatException {
      // Corrupted copy: start again.
    }
    return {};
  }

  /// Serialises read-modify-write cycles on the single keystore entry.
  Future<void> _update(
    String owner,
    void Function(Map<String, Object?> json) change,
  ) {
    final next = _lock.then((_) async {
      final json = await _read(owner);
      change(json);
      json['owner'] = owner;
      await _store.write(SecureStoreKeys.orgCache, jsonEncode(json));
    });
    _lock = next.catchError((Object _) {});
    return next;
  }

  Future<List<MyOrg>?> readMine(String owner) async {
    final mine = (await _read(owner))['mine'];
    if (mine is! List) return null;
    return [
      for (final o in mine)
        if (o is Map<String, Object?>) MyOrg.fromJson(o),
    ];
  }

  Future<void> writeMine(String owner, List<MyOrg> orgs) => _update(owner, (
    json,
  ) {
    json['mine'] = [for (final o in orgs) o.toJson()];
    // Forget the summaries of institutions the account no longer belongs to.
    final ids = {for (final o in orgs) o.id};
    final summaries = json['summaries'];
    if (summaries is Map) {
      json['summaries'] = {
        for (final e in summaries.entries)
          if (ids.contains(e.key)) e.key: e.value,
      };
    }
  });

  Future<CachedOrgSummary?> readSummary(String owner, String orgId) async {
    final summaries = (await _read(owner))['summaries'];
    if (summaries is! Map) return null;
    final entry = summaries[orgId];
    if (entry is! Map) return null;
    final data = entry['data'];
    if (data is! Map<String, Object?>) return null;
    try {
      return CachedOrgSummary(
        OrgSummary.fromJson(data),
        DateTime.tryParse(entry['saved_at'] as String? ?? ''),
      );
    } on Object {
      return null;
    }
  }

  Future<void> writeSummary(String owner, OrgSummary summary, DateTime at) =>
      _update(owner, (json) {
        final summaries = json['summaries'];
        json['summaries'] = {
          if (summaries is Map) ...summaries.cast<String, Object?>(),
          summary.id: {
            'saved_at': at.toUtc().toIso8601String(),
            'data': summary.source,
          },
        };
      });

  Future<void> removeSummary(String owner, String orgId) =>
      _update(owner, (json) {
        final summaries = json['summaries'];
        if (summaries is Map) summaries.remove(orgId);
      });
}

class CachedOrgSummary {
  const CachedOrgSummary(this.summary, this.savedAt);
  final OrgSummary summary;
  final DateTime? savedAt;
}

final orgCacheProvider = Provider<OrgCache>(
  (ref) => OrgCache(ref.watch(secureStoreProvider)),
);

/// Identity the institutions belong to: only registered accounts (never anonymous) have any.
final orgOwnerProvider = Provider<String?>(
  (ref) => ref.watch(
    identityProvider.select((s) => s.isRegistered ? s.fingerprint : null),
  ),
);

/// `GET /api/v1/orgs/mine`, fetched after sign-in and cached for offline use. The cached list
/// is returned at once and refreshed in the background.
class MyOrgsController extends AsyncNotifier<List<MyOrg>> {
  @override
  Future<List<MyOrg>> build() async {
    final owner = ref.watch(orgOwnerProvider);
    if (owner == null) return const [];
    final api = ref.read(apiProvider);
    final cache = ref.read(orgCacheProvider);
    final cached = await cache.readMine(owner);
    if (cached != null) {
      unawaited(_refreshQuietly(api, cache, owner));
      return cached;
    }
    return _fetch(api, cache, owner);
  }

  Future<List<MyOrg>> _fetch(
    EHimayaApi api,
    OrgCache cache,
    String owner,
  ) async {
    final orgs = await api.myOrgs();
    if (ref.mounted) await cache.writeMine(owner, orgs);
    return orgs;
  }

  Future<void> _refreshQuietly(
    EHimayaApi api,
    OrgCache cache,
    String owner,
  ) async {
    try {
      final orgs = await _fetch(api, cache, owner);
      if (ref.mounted) state = AsyncData(orgs);
    } on ApiException catch (e) {
      // Offline: the cached list stays.
      _log.info('institutions not refreshed: ${e.code.wire}');
    }
  }

  /// Re-fetches from the server; keeps the cached list when offline.
  Future<void> refresh() async {
    final owner = ref.read(orgOwnerProvider);
    if (owner == null) return;
    await _refreshQuietly(
      ref.read(apiProvider),
      ref.read(orgCacheProvider),
      owner,
    );
  }
}

final myOrgsProvider = AsyncNotifierProvider<MyOrgsController, List<MyOrg>>(
  MyOrgsController.new,
  retry: (_, _) => null,
);

/// Institutions the user can report for: `active` only (phase 4 §8).
final activeOrgsProvider = Provider<List<MyOrg>>(
  (ref) => [
    for (final o in ref.watch(myOrgsProvider).value ?? const <MyOrg>[])
      if (o.isActive) o,
  ],
);

/// Whether the "My institution" entry points are shown.
final hasInstitutionsProvider = Provider<bool>(
  (ref) => (ref.watch(myOrgsProvider).value ?? const <MyOrg>[]).isNotEmpty,
);

/// Name of an institution from the cached list (for local rows of "My reports").
final orgNamesProvider = Provider<Map<String, String>>(
  (ref) => {
    for (final o in ref.watch(myOrgsProvider).value ?? const <MyOrg>[])
      o.id: o.name,
  },
);

/// Keeps [choice] only when it is one of the [active] institutions (otherwise: myself).
String? validReportAs(String? choice, List<MyOrg> active) =>
    choice != null && active.any((o) => o.id == choice) ? choice : null;

/// "Report as" of the report form: the last choice, persisted (null: myself).
class ReportAsController extends Notifier<String?> {
  @override
  String? build() => ref.watch(appPrefsProvider).reportAsOrgId;

  Future<void> choose(String? orgId) async {
    await ref.read(appPrefsProvider).setReportAsOrgId(orgId);
    state = orgId;
  }
}

final reportAsChoiceProvider = NotifierProvider<ReportAsController, String?>(
  ReportAsController.new,
);

/// Institution the report form sends for by default (validated against the active list).
final reportAsProvider = Provider<String?>(
  (ref) => validReportAs(
    ref.watch(reportAsChoiceProvider),
    ref.watch(activeOrgsProvider),
  ),
);

/// SOS default chosen in settings (null: myself, the default).
class SosReportAsController extends Notifier<String?> {
  @override
  String? build() => ref.watch(appPrefsProvider).sosReportAsOrgId;

  Future<void> choose(String? orgId) async {
    await ref.read(appPrefsProvider).setSosReportAsOrgId(orgId);
    state = orgId;
  }
}

final sosReportAsChoiceProvider =
    NotifierProvider<SosReportAsController, String?>(SosReportAsController.new);

/// Institution the SOS is sent for by default (validated against the active list).
final sosReportAsProvider = Provider<String?>(
  (ref) => validReportAs(
    ref.watch(sosReportAsChoiceProvider),
    ref.watch(activeOrgsProvider),
  ),
);

/// A summary and whether it is the offline copy.
class OrgSummaryView {
  const OrgSummaryView(this.summary, {this.offlineSince});

  final OrgSummary summary;

  /// Set when the server could not be reached: time the shown copy was saved.
  final DateTime? offlineSince;
  bool get isOffline => offlineSince != null;
}

/// `GET /api/v1/orgs/{id}/summary`; the last copy is kept for offline viewing.
final orgSummaryProvider = FutureProvider.autoDispose
    .family<OrgSummaryView, String>((ref, orgId) async {
      final owner = ref.watch(orgOwnerProvider);
      final api = ref.watch(apiProvider);
      final cache = ref.watch(orgCacheProvider);
      final clock = ref.watch(clockProvider);
      try {
        final summary = await api.orgSummary(orgId);
        if (owner != null) await cache.writeSummary(owner, summary, clock());
        return OrgSummaryView(summary);
      } on ApiException catch (e) {
        if (owner == null) rethrow;
        if (!e.isTransient) {
          if (e.code == ApiErrorCode.orgNotFound) {
            await cache.removeSummary(owner, orgId);
          }
          rethrow;
        }
        final cached = await cache.readSummary(owner, orgId);
        if (cached == null) rethrow;
        return OrgSummaryView(
          cached.summary,
          offlineSince:
              cached.savedAt ?? DateTime.fromMillisecondsSinceEpoch(0),
        );
      }
    }, retry: (_, _) => null);

/// `GET /api/v1/orgs/{id}/reports` (first page, newest first).
final orgReportsProvider = FutureProvider.autoDispose
    .family<List<OrgReport>, String>(
      (ref, orgId) async =>
          (await ref.watch(apiProvider).orgReports(orgId)).items,
      retry: (_, _) => null,
    );

/// `GET /api/v1/orgs/{id}`: the full card with its version (online only).
final orgCardProvider = FutureProvider.autoDispose.family<OrgCardData, String>(
  (ref, orgId) => ref.watch(apiProvider).orgCard(orgId),
  retry: (_, _) => null,
);

final orgEquipmentProvider = FutureProvider.autoDispose
    .family<List<OrgEquipment>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgEquipment(orgId),
      retry: (_, _) => null,
    );

final orgFeaturesProvider = FutureProvider.autoDispose
    .family<List<OrgFeature>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgFeatures(orgId),
      retry: (_, _) => null,
    );

final orgCertificatesProvider = FutureProvider.autoDispose
    .family<List<OrgCertificate>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgCertificates(orgId),
      retry: (_, _) => null,
    );

final orgMembersProvider = FutureProvider.autoDispose
    .family<List<OrgMember>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgMembers(orgId),
      retry: (_, _) => null,
    );

/// The account's role in an institution, from the cached list (null: unknown).
final myOrgRoleProvider = Provider.family<String?, String>((ref, orgId) {
  for (final o in ref.watch(myOrgsProvider).value ?? const <MyOrg>[]) {
    if (o.id == orgId) return o.myRole;
  }
  return null;
});

/// Opens a web page outside the app (institutions portal). Returns false when it cannot.
typedef UrlOpener = Future<bool> Function(Uri url);

Future<bool> _openExternal(Uri url) async {
  try {
    return await launchUrl(url, mode: LaunchMode.externalApplication);
  } on Exception {
    return false;
  }
}

final urlOpenerProvider = Provider<UrlOpener>((ref) => _openExternal);

// ---- Phase P2b ----

/// `GET /api/v1/orgs/{id}/messages`: Office messages, newest first.
final orgMessagesProvider = FutureProvider.autoDispose
    .family<List<OrgMessage>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgMessages(orgId),
      retry: (_, _) => null,
    );

/// `GET /api/v1/orgs/{id}/awareness`: safety tips for the institution's kind.
final orgAwarenessProvider = FutureProvider.autoDispose
    .family<List<SafetyTip>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgAwareness(orgId),
      retry: (_, _) => null,
    );

/// `GET /api/v1/orgs/{id}/activities`: drills and events, latest first.
final orgActivitiesProvider = FutureProvider.autoDispose
    .family<List<OrgActivity>, String>(
      (ref, orgId) => ref.watch(apiProvider).orgActivities(orgId),
      retry: (_, _) => null,
    );

/// Maintenance log of one equipment: `(orgId, equipmentId)`.
final equipmentMaintenanceProvider = FutureProvider.autoDispose
    .family<List<OrgMaintenance>, (String, String)>(
      (ref, ids) => ref.watch(apiProvider).equipmentMaintenance(ids.$1, ids.$2),
      retry: (_, _) => null,
    );
