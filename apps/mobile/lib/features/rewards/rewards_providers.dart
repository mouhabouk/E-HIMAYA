import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/connectivity/connectivity.dart';
import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/rewards_models.dart';
import '../../core/logging/log.dart';
import '../../core/storage/secure_store.dart';

final _log = logger('rewards');

/// Offline copy of the last rewards summary (FR-A-072). Kept in the platform keystore with the
/// other account data (the history names the citizen's reports) and tied to the identity that
/// fetched it: another account on the same phone never sees it, and signing out deletes it.
class RewardsCache {
  RewardsCache(this._store);

  final SecureStore _store;

  Future<CachedRewards?> read(String owner) async {
    final raw = await _store.read(SecureStoreKeys.rewardsCache);
    if (raw == null) return null;
    try {
      final json = jsonDecode(raw);
      if (json is! Map<String, Object?> || json['owner'] != owner) return null;
      final data = json['data'];
      if (data is! Map<String, Object?>) return null;
      return CachedRewards(
        RewardsSummary.fromJson(data),
        DateTime.tryParse(json['saved_at'] as String? ?? '') ??
            DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      );
    } on Object {
      // Corrupted copy: as if there were none.
      return null;
    }
  }

  Future<void> write(String owner, RewardsSummary summary, DateTime at) =>
      _store.write(
        SecureStoreKeys.rewardsCache,
        jsonEncode({
          'owner': owner,
          'saved_at': at.toUtc().toIso8601String(),
          'data': summary.source,
        }),
      );
}

class CachedRewards {
  const CachedRewards(this.summary, this.savedAt);
  final RewardsSummary summary;
  final DateTime savedAt;
}

final rewardsCacheProvider = Provider<RewardsCache>(
  (ref) => RewardsCache(ref.watch(secureStoreProvider)),
);

/// Identity whose rewards are shown: signed-in citizens only. Anonymous reports earn no points
/// and institution accounts have none, so neither asks the server.
final rewardsOwnerProvider = Provider<String?>(
  (ref) => ref.watch(
    identityProvider.select(
      (s) =>
          s.isRegistered && s.role == UserRole.citizen ? s.fingerprint : null,
    ),
  ),
);

/// A summary and whether it is the offline copy.
class RewardsView {
  const RewardsView(this.summary, {this.offlineSince});

  final RewardsSummary summary;

  /// Set when the server could not be reached: time the shown copy was saved.
  final DateTime? offlineSince;
  bool get isOffline => offlineSince != null;
}

/// `GET /api/v1/me/rewards` for the signed-in citizen (null for anyone else). Each answer is
/// kept; without network (or when the server does not answer) the last copy is shown with its
/// date.
final rewardsProvider = FutureProvider.autoDispose<RewardsView?>((ref) async {
  final owner = ref.watch(rewardsOwnerProvider);
  if (owner == null) return null;
  final api = ref.watch(apiProvider);
  final cache = ref.watch(rewardsCacheProvider);
  final clock = ref.watch(clockProvider);

  Future<RewardsView> offline(ApiException cause) async {
    final cached = await cache.read(owner);
    if (cached == null) throw cause;
    return RewardsView(cached.summary, offlineSince: cached.savedAt);
  }

  if (!await ref.read(connectivityProvider).isOnline()) {
    return offline(const ApiException(ApiErrorCode.network));
  }
  try {
    final summary = await api.myRewards();
    await cache.write(owner, summary, clock());
    return RewardsView(summary);
  } on ApiException catch (e) {
    if (!e.isTransient) rethrow;
    _log.info('rewards not refreshed: ${e.code.wire}');
    return offline(e);
  }
}, retry: (_, _) => null);

/// Opens a local file in the phone's viewer. Returns false when no app can open it.
typedef FileOpener = Future<bool> Function(String path, String mimeType);

Future<bool> _openWithViewer(String path, String mimeType) async {
  try {
    final result = await OpenFilex.open(path, type: mimeType);
    return result.type == ResultType.done;
  } on Exception {
    return false;
  }
}

final fileOpenerProvider = Provider<FileOpener>((ref) => _openWithViewer);

/// Folder the certificate PDFs are written to before they are opened: the app's cache (never
/// shared storage), so the system may clear them. Overridden in tests.
final certificateDirProvider = Provider<Future<Directory> Function()>(
  (ref) =>
      () async => Directory(
        p.join((await getTemporaryDirectory()).path, 'certificates'),
      ),
);

/// Downloads a certificate (`GET /api/v1/me/rewards/certificates/{id}`) and opens it. Throws
/// [ApiException] when the download fails; returns false when no PDF viewer could open it.
final openCertificateProvider = Provider<Future<bool> Function(String id)>((
  ref,
) {
  return (id) async {
    final bytes = await ref.read(apiProvider).rewardCertificatePdf(id);
    final dir = await ref.read(certificateDirProvider)();
    await dir.create(recursive: true);
    // The id is a server UUID; keep only safe characters for the file name anyway.
    final name = id.replaceAll(RegExp('[^A-Za-z0-9_-]'), '');
    final file = File(p.join(dir.path, 'ehimaya-certificate-$name.pdf'));
    await file.writeAsBytes(bytes, flush: true);
    return ref.read(fileOpenerProvider)(file.path, 'application/pdf');
  };
});
