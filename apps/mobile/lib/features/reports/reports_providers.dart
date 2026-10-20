import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/identity.dart';
import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/models.dart';
import '../../core/sync/report_queue.dart';
import '../institution/institution_providers.dart';

/// One row of "My reports": the local queue merged with `GET /api/v1/reports/mine`.
class ReportListItem {
  const ReportListItem({
    required this.trackingCode,
    required this.isTemporary,
    required this.category,
    required this.createdAt,
    this.clientUuid,
    this.serverId,
    this.status,
    this.localState,
    this.mediaPending = 0,
    this.mediaFailed = 0,
    this.organizationId,
    this.organizationName,
    this.lastError,
  });

  final String? clientUuid;

  /// Id of the report on the server, null until it was accepted (needed to go live, phase 6).
  final String? serverId;

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

  /// Institution the report was sent for (FR-B-011), null when sent by the user themselves.
  final String? organizationId;

  /// Its name; empty when not known on this phone.
  final String? organizationName;

  /// Machine code of the last sync failure of the local copy (e.g. `org_not_active`).
  final String? lastError;

  bool get isForOrganization => organizationId != null;

  /// A live stream can be opened on it (phase 6 §2: the server knows it and it is not over).
  bool get canGoLive =>
      serverId != null &&
      status != ReportStatus.closed &&
      status != ReportStatus.rejected;
}

/// Merge rule (NFR-04, server wins): status and tracking code come from the server when it
/// knows the report; the local row only adds its sync state.
List<ReportListItem> mergeReports({
  required List<PendingReport> local,
  required List<MediaItem> media,
  required List<ServerReport> server,
  Map<String, String> orgNames = const {},
}) {
  final byUuid = {
    for (final s in server)
      if (s.clientUuid != null) s.clientUuid!: s,
  };
  final seen = <String>{};
  final items = <ReportListItem>[];
  for (final r in local) {
    final s =
        byUuid[r.clientUuid] ??
        server.where((x) => x.id == r.serverId).firstOrNull;
    if (s != null) seen.add(s.id);
    if (r.serverId != null) seen.add(r.serverId!);
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
    final orgId = s?.organization?.id ?? payloadOrganizationId(r.payload);
    items.add(
      ReportListItem(
        clientUuid: r.clientUuid,
        serverId: s?.id ?? r.serverId,
        trackingCode: code ?? r.tempCode,
        isTemporary: code == null,
        category: ReportCategory.fromWire(r.category) ?? ReportCategory.other,
        status: ReportStatus.fromWire(s?.status ?? r.serverStatus),
        localState: r.state,
        mediaPending: pendingMedia,
        mediaFailed: failedMedia,
        createdAt: r.createdAt,
        organizationId: orgId,
        organizationName: orgId == null
            ? null
            : (s?.organization?.name ?? orgNames[orgId] ?? ''),
        lastError: r.lastError,
      ),
    );
  }
  for (final s in server) {
    if (seen.contains(s.id)) continue;
    items.add(
      ReportListItem(
        clientUuid: s.clientUuid,
        serverId: s.id,
        trackingCode: s.trackingCode,
        isTemporary: false,
        category: ReportCategory.fromWire(s.category) ?? ReportCategory.other,
        status: ReportStatus.fromWire(s.status),
        createdAt:
            s.createdAt ??
            s.receivedAt ??
            DateTime.fromMillisecondsSinceEpoch(0),
        organizationId: s.organization?.id,
        organizationName: s.organization?.name,
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
      orgNames: ref.watch(orgNamesProvider),
    ),
  );
});
