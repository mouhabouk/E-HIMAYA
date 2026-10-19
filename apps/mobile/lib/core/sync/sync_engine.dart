import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../auth/identity.dart';
import '../config/providers.dart';
import '../consent/consent_service.dart';
import '../db/app_database.dart';
import '../db/open_database.dart';
import '../http/api_client.dart';
import '../http/api_error.dart';
import '../http/ehimaya_api.dart';
import '../http/models.dart';
import '../logging/log.dart';
import '../tus/tus_client.dart';
import 'backoff.dart';
import 'report_queue.dart';

final _log = logger('sync');

class SyncSummary {
  SyncSummary();
  int reportsSent = 0;
  int mediaUploaded = 0;
  int mediaStored = 0;
  int failures = 0;

  @override
  String toString() =>
      'SyncSummary(reports: $reportsSent, uploaded: $mediaUploaded, '
      'stored: $mediaStored, failures: $failures)';
}

/// Pushes the offline queue to the server (FR-A-047, NFR-04):
///
/// 1. `POST /api/v1/reports` with the frozen payload. `client_uuid` makes it idempotent, so a
///    retry after a lost response returns 200 with the same report; 200 and 201 are equivalent.
///    The temporary code is replaced by the server tracking code.
/// 2. Media are uploaded with tus once the report has a server id; progress is persisted after
///    every chunk.
/// 3. Local files are kept until `GET /api/v1/reports/mine` reports the media as `stored`.
///
/// Failures are retried with exponential back-off and jitter. `428 consent_required` re-sends
/// the charter consent and retries at once. Conflicts: the server copy wins, the local copy is
/// kept and flagged. A report sent on behalf of an institution that the server refuses
/// (`org_not_found`, `org_not_active`) is kept as [ReportState.orgRefused] for the user to
/// resend as themselves; it is never dropped nor silently sent without the institution.
class SyncEngine {
  SyncEngine({
    required this.db,
    required this.api,
    required this.tus,
    required this.consent,
    required this.clock,
    required this.identity,
    required this.onAnonBlocked,
    Random? random,
  }) : _random = random ?? Random();

  final AppDatabase db;
  final EHimayaApi api;
  final TusClient tus;
  final ConsentSender consent;
  final DateTime Function() clock;
  final IdentityState Function() identity;
  final void Function() onAnonBlocked;
  final Random _random;

  /// Reconcile passes an uploaded file may be missing from `/reports/mine` before it is
  /// considered rejected (rejected media are hidden from lists).
  static const absentPassesBeforeRejected = 3;

  Future<SyncSummary>? _running;

  /// Runs one pass; concurrent calls share the pass in progress.
  Future<SyncSummary> runOnce() =>
      _running ??= _run().whenComplete(() => _running = null);

  Future<SyncSummary> _run() async {
    final summary = SyncSummary();
    final id = identity();
    if (!id.hasIdentity) return summary;

    await consent.sendIfNeeded();

    final reports = await db.reportsNeedingSync();
    // SOS first, then oldest first.
    reports.sort((a, b) {
      final sa = a.category == ReportCategory.sos.wire ? 0 : 1;
      final sb = b.category == ReportCategory.sos.wire ? 0 : 1;
      return sa != sb ? sa - sb : a.createdAt.compareTo(b.createdAt);
    });

    var awaitingStored = false;
    for (final report in reports) {
      if (report.state == ReportState.blocked && id.isAnonymous) continue;
      // An institution never reports anonymously (phase 4 §8): wait for a signed-in account.
      if (!id.isRegistered &&
          report.serverId == null &&
          payloadOrganizationId(report.payload) != null) {
        continue;
      }
      var current = report;
      if (current.serverId == null) {
        if (!_due(current.nextAttemptAt)) continue;
        final created = await _createOnServer(current, summary);
        if (created == null) continue;
        current = created;
      }
      final pending = await _uploadMedia(current, summary);
      awaitingStored |= pending;
    }

    if (awaitingStored) await _reconcileStoredMedia(summary);
    _log.fine('$summary');
    return summary;
  }

  bool _due(DateTime? next) => next == null || !next.isAfter(clock());

  Future<PendingReport?> _createOnServer(
    PendingReport report,
    SyncSummary summary,
  ) async {
    final body = jsonDecode(report.payload) as Map<String, Object?>;
    var consentRetried = false;
    while (true) {
      try {
        final result = await api.createReport(body);
        final server = result.report;
        final hasMedia = (await db.mediaForReport(report.clientUuid))
            .isNotEmpty;
        final conflict = !result.created && _differs(body, server);
        await db.updateReport(
          report.clientUuid,
          PendingReportsCompanion(
            serverId: Value(server.id),
            serverTrackingCode: Value(server.trackingCode),
            serverStatus: Value(server.status),
            serverSnapshot: Value(
              conflict ? jsonEncode(_snapshot(server)) : null,
            ),
            state: Value(hasMedia ? ReportState.created : ReportState.synced),
            attempts: const Value(0),
            lastError: const Value(null),
            nextAttemptAt: const Value(null),
            updatedAt: Value(clock().toUtc()),
          ),
        );
        summary.reportsSent++;
        return await db.reportByUuid(report.clientUuid);
      } on ApiException catch (e) {
        if (e.code == ApiErrorCode.consentRequired && !consentRetried) {
          consentRetried = true;
          if (await consent.sendIfNeeded(force: true)) continue;
        }
        await _recordReportFailure(report, e);
        summary.failures++;
        return null;
      }
    }
  }

  Future<void> _recordReportFailure(
    PendingReport report,
    ApiException e,
  ) async {
    final attempts = report.attempts + 1;
    String? state;
    DateTime? next;
    switch (e.code) {
      case ApiErrorCode.anonBlocked:
        state = ReportState.blocked;
        onAnonBlocked();
      case ApiErrorCode.clientUuidConflict:
        state = ReportState.conflict;
      case ApiErrorCode.orgNotFound || ApiErrorCode.orgNotActive:
        // Not a member any more, or the institution is not active: keep the report and let
        // the user resend it as themselves.
        state = ReportState.orgRefused;
      case ApiErrorCode.validation || ApiErrorCode.unknownCharterVersion:
        state = ReportState.failed;
      case ApiErrorCode.unknown
          when (e.statusCode ?? 0) >= 400 && (e.statusCode ?? 0) < 500:
        state = ReportState.failed;
      default:
        // Network, 5xx, 429, expired login, consent still missing: retry later.
        next = clock().add(
          backoffDelay(attempts, _random, retryAfter: e.retryAfter),
        );
    }
    _log.info('report ${report.clientUuid} not sent: ${e.code.wire}');
    await db.updateReport(
      report.clientUuid,
      PendingReportsCompanion(
        attempts: Value(attempts),
        lastError: Value(e.code.wire),
        nextAttemptAt: Value(next),
        state: state == null ? const Value.absent() : Value(state),
        updatedAt: Value(clock().toUtc()),
      ),
    );
  }

  /// Uploads pending media of [report]. Returns true when some media still wait for the server
  /// to confirm `stored`.
  Future<bool> _uploadMedia(PendingReport report, SyncSummary summary) async {
    final serverId = report.serverId;
    if (serverId == null) return false;
    var awaitingStored = false;
    for (final m in await db.mediaForReport(report.clientUuid)) {
      if (m.state == MediaState.uploaded) {
        awaitingStored = true;
        continue;
      }
      if (MediaState.terminal.contains(m.state)) continue;
      if (!_due(m.nextAttemptAt)) continue;
      final file = File(m.path);
      if (!await file.exists()) {
        await db.updateMedia(
          m.id,
          const MediaItemsCompanion(
            state: Value(MediaState.failed),
            lastError: Value('file_missing'),
          ),
        );
        continue;
      }
      try {
        await tus.upload(
          file: file,
          uploadUrl: m.uploadUrl == null ? null : Uri.parse(m.uploadUrl!),
          metadata: {
            'report_id': serverId,
            'kind': m.kind,
            'sha256': m.sha256,
            'filetype': m.mime,
            'filename': p.basename(m.path),
          },
          onProgress: (url, offset) => db.updateMedia(
            m.id,
            MediaItemsCompanion(
              uploadUrl: Value(url.toString()),
              uploadOffset: Value(offset),
              state: const Value(MediaState.uploading),
            ),
          ),
        );
        await db.updateMedia(
          m.id,
          const MediaItemsCompanion(
            state: Value(MediaState.uploaded),
            attempts: Value(0),
            lastError: Value(null),
            nextAttemptAt: Value(null),
          ),
        );
        summary.mediaUploaded++;
        awaitingStored = true;
      } on TusException catch (e) {
        summary.failures++;
        await _recordMediaFailure(m, e);
      } on FileSystemException {
        summary.failures++;
        await db.updateMedia(
          m.id,
          const MediaItemsCompanion(
            state: Value(MediaState.failed),
            lastError: Value('file_unreadable'),
          ),
        );
      }
    }
    await _refreshReportState(report.clientUuid);
    return awaitingStored;
  }

  Future<void> _recordMediaFailure(MediaItem m, TusException e) async {
    final attempts = m.attempts + 1;
    final blocked = e.api?.code == ApiErrorCode.anonBlocked;
    if (blocked) onAnonBlocked();
    // Contract §4: 4xx refusals are permanent for the file (except 401, refreshed and retried
    // by the interceptor, and anon_blocked, retried once the user registers). An expired
    // upload (404/410 on HEAD/PATCH) restarts with a new creation request.
    final restart = e.uploadGone && e.api?.code != ApiErrorCode.reportNotFound;
    final permanent = !e.isTransient && !restart && !blocked;
    _log.info('media ${m.id} upload failed: ${e.code}');
    await db.updateMedia(
      m.id,
      MediaItemsCompanion(
        attempts: Value(attempts),
        lastError: Value(e.code),
        uploadUrl: restart ? const Value(null) : const Value.absent(),
        uploadOffset: restart ? const Value(0) : const Value.absent(),
        state: Value(permanent ? MediaState.failed : MediaState.pending),
        nextAttemptAt: Value(
          permanent
              ? null
              : clock().add(
                  backoffDelay(
                    attempts,
                    _random,
                    retryAfter: e.api?.retryAfter,
                  ),
                ),
        ),
      ),
    );
  }

  /// Marks media `stored`/`rejected` from the server view and deletes stored local files.
  Future<void> _reconcileStoredMedia(SyncSummary summary) async {
    final waiting = <String, List<MediaItem>>{};
    for (final r in await db.reportsNeedingSync()) {
      final serverId = r.serverId;
      if (serverId == null) continue;
      final items = (await db.mediaForReport(r.clientUuid))
          .where((m) => m.state == MediaState.uploaded)
          .toList();
      if (items.isNotEmpty) waiting[serverId] = items;
    }
    if (waiting.isEmpty) return;

    String? before;
    for (var page = 0; page < 10 && waiting.isNotEmpty; page++) {
      final ReportsPage result;
      try {
        result = await api.myReports(before: before);
      } on ApiException catch (e) {
        _log.info('reconcile skipped: ${e.code.wire}');
        return;
      }
      for (final server in result.items) {
        final items = waiting.remove(server.id);
        if (items == null) continue;
        await _applyServerMedia(server, items, summary);
      }
      before = result.nextBefore;
      if (before == null) break;
    }
  }

  Future<void> _applyServerMedia(
    ServerReport server,
    List<MediaItem> items,
    SyncSummary summary,
  ) async {
    for (final m in items) {
      final match = server.media.where((s) => s.sha256 == m.sha256).firstOrNull;
      if (match == null) {
        // Rejected media are hidden from the server lists (contract §4). An upload whose bytes
        // were all accepted but which stays absent over several passes was rejected.
        final misses = m.attempts + 1;
        await db.updateMedia(
          m.id,
          MediaItemsCompanion(
            attempts: Value(misses),
            state: Value(
              misses >= absentPassesBeforeRejected
                  ? MediaState.rejected
                  : MediaState.uploaded,
            ),
            lastError: Value(
              misses >= absentPassesBeforeRejected
                  ? ApiErrorCode.mediaRejected.wire
                  : null,
            ),
          ),
        );
        continue;
      }
      if (match.status == 'stored') {
        final f = File(m.path);
        if (await f.exists()) await f.delete();
        await db.updateMedia(
          m.id,
          const MediaItemsCompanion(
            state: Value(MediaState.stored),
            lastError: Value(null),
          ),
        );
        summary.mediaStored++;
      } else if (match.status == 'rejected') {
        // Final: checksum mismatch on the server. Not retried; the local file is kept.
        await db.updateMedia(
          m.id,
          MediaItemsCompanion(
            state: const Value(MediaState.rejected),
            lastError: Value(ApiErrorCode.mediaRejected.wire),
          ),
        );
      }
      // `uploading` / `verifying`: wait for the next pass.
    }
    final local = await _byServerId(server.id);
    if (local != null) {
      await db.updateReport(
        local.clientUuid,
        PendingReportsCompanion(
          serverStatus: Value(server.status),
          serverTrackingCode: Value(server.trackingCode),
        ),
      );
      await _refreshReportState(local.clientUuid);
    }
  }

  Future<PendingReport?> _byServerId(String id) => (db.select(
    db.pendingReports,
  )..where((r) => r.serverId.equals(id))).getSingleOrNull();

  Future<void> _refreshReportState(String clientUuid) async {
    final report = await db.reportByUuid(clientUuid);
    if (report == null || report.state != ReportState.created) return;
    final media = await db.mediaForReport(clientUuid);
    if (media.every((m) => MediaState.terminal.contains(m.state))) {
      await db.updateReport(
        clientUuid,
        PendingReportsCompanion(
          state: const Value(ReportState.synced),
          updatedAt: Value(clock().toUtc()),
        ),
      );
    }
  }

  static bool _differs(Map<String, Object?> local, ServerReport server) =>
      local['category'] != server.category ||
      (local['text'] as String?) != server.text;

  static Map<String, Object?> _snapshot(ServerReport s) => {
    'category': s.category,
    'text': s.text,
    'status': s.status,
    'tracking_code': s.trackingCode,
  };
}

final syncEngineProvider = Provider<SyncEngine>(
  (ref) => SyncEngine(
    db: ref.watch(databaseProvider),
    api: ref.watch(apiProvider),
    tus: TusClient(ref.watch(tusDioProvider)),
    consent: ref.watch(consentServiceProvider),
    clock: ref.watch(clockProvider),
    identity: () => ref.read(identityProvider),
    onAnonBlocked: () => ref.read(anonBlockedProvider.notifier).set(true),
  ),
);
