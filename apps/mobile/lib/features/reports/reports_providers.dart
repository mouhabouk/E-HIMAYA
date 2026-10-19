import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';

/// One row of "My reports": the local queue merged with `GET /api/v1/reports/mine`.
class ReportListItem {
  const ReportListItem({
    required this.trackingCode,
    required this.isTemporary,
    required this.category,
    required this.createdAt,
    this.clientUuid,
    this.status,
    this.localState,
    this.mediaPending = 0,
    this.mediaFailed = 0,
  });

  final String? clientUuid;

  /// Server code when known, otherwise the local `TMP-XXXXXX`.
  final String trackingCode;
  final bool isTemporary;
  final ReportCategory category;
  final ReportStatus? status;

  /// [ReportState] of the local copy, null for server-only rows.
  final String? localState;
  final int mediaPending;

  /// Attachments refused (checksum mismatch, too late, too large…): not retried.
  final int mediaFailed;
  final DateTime createdAt;
}

/// Merge rule (NFR-04, server wins): status and tracking code come from the server when it
/// knows the report; the local row only adds its sync state.
List<ReportListItem> mergeReports({
  required List<PendingReport> local,
  required List<MediaItem> media,
  required List<ServerReport> server,
}) {
  final byUuid = {
    for (final s in server)
      if (s.clientUuid != null) s.clientUuid!: s,
  };
  final seen = <String>{};
  final items = <ReportListItem>[];
  for (final r in local) {
    final s = byUuid[r.clientUuid];
    if (s != null) seen.add(s.id);
    final code = s?.trackingCode ?? r.serverTrackingCode;
    final pendingMedia = media
        .where(
          (m) =>
              m.reportUuid == r.clientUuid &&
              !MediaState.terminal.contains(m.state),
        )
        .length;
    final failedMedia = media
        .where(
          (m) =>
              m.reportUuid == r.clientUuid &&
              (m.state == MediaState.rejected || m.state == MediaState.failed),
        )
        .length;
    items.add(
      ReportListItem(
        clientUuid: r.clientUuid,
        trackingCode: code ?? r.tempCode,
        isTemporary: code == null,
        category: ReportCategory.fromWire(r.category) ?? ReportCategory.other,
        status: ReportStatus.fromWire(s?.status ?? r.serverStatus),
        localState: r.state,
        mediaPending: pendingMedia,
        mediaFailed: failedMedia,
        createdAt: r.createdAt,
      ),
    );
  }
  for (final s in server) {
    if (seen.contains(s.id)) continue;
    items.add(
      ReportListItem(
        clientUuid: s.clientUuid,
        trackingCode: s.trackingCode,
        isTemporary: false,
        category: ReportCategory.fromWire(s.category) ?? ReportCategory.other,
        status: ReportStatus.fromWire(s.status),
        createdAt:
            s.createdAt ??
            s.receivedAt ??
            DateTime.fromMillisecondsSinceEpoch(0),
      ),
    );
  }
  items.sort((a, b) => b.createdAt.compareTo(a.createdAt));
  return items;
}

final localReportsProvider = StreamProvider<List<PendingReport>>(
  (ref) => ref.watch(databaseProvider).watchAllReports(),
);

final localMediaProvider = StreamProvider<List<MediaItem>>(
  (ref) => ref.watch(databaseProvider).watchAllMedia(),
);

/// Reports not yet accepted by the server, or whose attachments are still uploading.
final pendingSyncCountProvider = Provider<AsyncValue<int>>(
  (ref) => ref
      .watch(localReportsProvider)
      .whenData(
        (list) => list
            .where((r) => ReportState.pendingStates.contains(r.state))
            .length,
      ),
);

/// Server view of the caller's reports (first page, newest first).
class ServerReportsController extends AsyncNotifier<List<ServerReport>> {
  @override
  Future<List<ServerReport>> build() async {
    final identity = ref.watch(identityProvider.select((s) => s.fingerprint));
    if (identity == null) return const [];
    final page = await ref.read(apiProvider).myReports();
    return page.items;
  }

  /// Re-fetches while keeping the previous list visible.
  Future<void> refresh() async {
    ref.invalidateSelf();
    try {
      await future;
    } on Object {
      // Surfaced through the provider's error state.
    }
  }
}

final serverReportsProvider =
    AsyncNotifierProvider<ServerReportsController, List<ServerReport>>(
      ServerReportsController.new,
      retry: (_, _) => null,
    );

final mergedReportsProvider = Provider<AsyncValue<List<ReportListItem>>>((ref) {
  final local = ref.watch(localReportsProvider);
  final media = ref.watch(localMediaProvider);
  final server = ref.watch(serverReportsProvider);
  if (local is AsyncLoading || media is AsyncLoading) {
    return const AsyncLoading();
  }
  return AsyncData(
    mergeReports(
      local: local.value ?? const [],
      media: media.value ?? const [],
      server: server.value ?? const [],
    ),
  );
});
