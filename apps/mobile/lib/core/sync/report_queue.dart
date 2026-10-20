import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../config/providers.dart';
import '../db/app_database.dart';
import '../db/open_database.dart';
import '../http/models.dart';
import '../media/media_rules.dart';

/// A file attached to a report draft.
class DraftAttachment {
  const DraftAttachment({
    required this.path,
    required this.kind,
    required this.mime,
    this.deleteSourceAfterQueue = false,
  });

  final String path;
  final MediaKind kind;
  final String mime;

  /// True for files the app created itself (audio recordings): the queued copy replaces them.
  final bool deleteSourceAfterQueue;
}

class ReportDraft {
  const ReportDraft({
    required this.category,
    required this.location,
    this.text,
    this.lang,
    this.attachments = const [],
    this.organizationId,
  });

  final ReportCategory category;
  final GeoPoint location;
  final String? text;
  final String? lang;
  final List<DraftAttachment> attachments;

  /// Institution the report is sent for (phase 4 §8); null: the user themselves.
  final String? organizationId;
}

/// A report to attach a file to: its local row and/or its server id.
class AttachTarget {
  const AttachTarget({
    this.clientUuid,
    this.serverId,
    this.trackingCode,
    this.category = ReportCategory.other,
  });

  final String? clientUuid;
  final String? serverId;
  final String? trackingCode;

  /// Used only when a local row must be created for a server-only report.
  final ReportCategory category;
}

/// `lastError` of a report kept on the device because the anonymous quota was exhausted
/// (the wire code of `ApiErrorCode.anonQuotaExhausted`).
const anonQuotaExhaustedWire = 'anon_quota_exhausted';

class QueuedReport {
  const QueuedReport(this.clientUuid, this.tempCode);
  final String clientUuid;
  final String tempCode;
}

/// Saves reports into the encrypted local queue (FR-A-047) and hands out the temporary
/// tracking code `TMP-XXXXXX` immediately, before any network call.
class ReportQueue {
  ReportQueue({
    required this.db,
    required this.mediaDir,
    required this.clock,
    Random? random,
    Uuid? uuid,
  }) : _random = random ?? Random.secure(),
       _uuid = uuid ?? const Uuid();

  final AppDatabase db;
  final Future<Directory> Function() mediaDir;
  final DateTime Function() clock;
  final Random _random;
  final Uuid _uuid;

  /// No 0/O or 1/I to keep the code readable over the phone.
  static const _alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  static final tempCodeFormat = RegExp(r'^TMP-[A-HJ-NP-Z2-9]{6}$');

  String newTempCode() =>
      'TMP-${List.generate(6, (_) => _alphabet[_random.nextInt(_alphabet.length)]).join()}';

  /// Saves [draft] with its temporary code. [blocked]: the anonymous quota of the installation
  /// is known to be exhausted (phase 9 §3), so the report is kept as [ReportState.blocked] and
  /// sent once the user signs in instead of being refused by the server now.
  Future<QueuedReport> enqueue(
    ReportDraft draft, {
    bool blocked = false,
  }) async {
    if (draft.attachments.length > MediaRules.maxFilesPerReport) {
      throw ArgumentError('too many attachments');
    }
    final clientUuid = _uuid.v4();
    final tempCode = newTempCode();
    final now = clock().toUtc();
    final text = draft.text?.trim();
    final payload = <String, Object?>{
      'client_uuid': clientUuid,
      'category': draft.category.wire,
      if (text != null && text.isNotEmpty) 'text': text,
      if (text != null && text.isNotEmpty && draft.lang != null)
        'lang': draft.lang,
      'location': draft.location.toJson(),
      'created_at': now.toIso8601String(),
      organizationIdKey: ?draft.organizationId,
    };

    final media = <MediaItemsCompanion>[];
    if (draft.attachments.isNotEmpty) {
      final root = await mediaDir();
      final dir = Directory(p.join(root.path, clientUuid));
      await dir.create(recursive: true);
      var index = 0;
      for (final a in draft.attachments) {
        final source = File(a.path);
        final ext = p.extension(a.path);
        final target = File(p.join(dir.path, '${index++}$ext'));
        await source.copy(target.path);
        if (a.deleteSourceAfterQueue) {
          try {
            await source.delete();
          } on FileSystemException {
            // Best effort: the recorder's temp file is cleaned with the cache anyway.
          }
        }
        media.add(
          MediaItemsCompanion.insert(
            reportUuid: clientUuid,
            path: target.path,
            kind: a.kind.name,
            mime: a.mime,
            size: await target.length(),
            sha256: await sha256OfFile(target),
          ),
        );
      }
    }

    await db.insertReport(
      PendingReportsCompanion.insert(
        clientUuid: clientUuid,
        category: draft.category.wire,
        payload: jsonEncode(payload),
        tempCode: tempCode,
        state: blocked
            ? const Value(ReportState.blocked)
            : const Value.absent(),
        lastError: blocked
            ? const Value(anonQuotaExhaustedWire)
            : const Value.absent(),
        createdAt: now,
        updatedAt: now,
      ),
      media,
    );
    return QueuedReport(clientUuid, tempCode);
  }

  /// A report refused for its institution (`org_not_found` / `org_not_active`) is queued again
  /// without `organization_id`, i.e. as the user themselves. The server never stored it, so
  /// the same `client_uuid` is reused.
  Future<bool> resendAsSelf(String clientUuid) async {
    final row = await db.reportByUuid(clientUuid);
    if (row == null || row.state != ReportState.orgRefused) return false;
    final payload = jsonDecode(row.payload) as Map<String, Object?>
      ..remove(organizationIdKey);
    await db.updateReport(
      clientUuid,
      PendingReportsCompanion(
        payload: Value(jsonEncode(payload)),
        state: const Value(ReportState.queued),
        attempts: const Value(0),
        lastError: const Value(null),
        nextAttemptAt: const Value(null),
        updatedAt: Value(clock().toUtc()),
      ),
    );
    return true;
  }

  /// Adds a file to a report that was already queued or sent (phase 6: the clip recorded when a
  /// live stream is not possible, FR-A-051). [target] names the report by its local
  /// `client_uuid` and/or its server id. A report known only from the server (sent from another
  /// install of the queue, or whose local row was cleaned) gets a local row in state `created`,
  /// so the sync engine uploads the file with tus exactly like any other attachment.
  ///
  /// Returns the `client_uuid` of the local row. Throws [ArgumentError] when the report already
  /// holds [MediaRules.maxFilesPerReport] files or when it is unknown and has no server id.
  Future<String> attach(AttachTarget target, DraftAttachment attachment) async {
    var row = target.clientUuid == null
        ? null
        : await db.reportByUuid(target.clientUuid!);
    final serverId = target.serverId;
    if (row == null && serverId != null) {
      row = await (db.select(
        db.pendingReports,
      )..where((r) => r.serverId.equals(serverId))).getSingleOrNull();
    }
    final now = clock().toUtc();
    if (row == null) {
      if (serverId == null) throw ArgumentError('unknown report');
      final uuid = target.clientUuid ?? _uuid.v4();
      await db.insertReport(
        PendingReportsCompanion.insert(
          clientUuid: uuid,
          category: target.category.wire,
          payload: jsonEncode({
            'client_uuid': uuid,
            'category': target.category.wire,
          }),
          tempCode: target.trackingCode ?? newTempCode(),
          serverId: Value(serverId),
          serverTrackingCode: Value(target.trackingCode),
          state: const Value(ReportState.created),
          createdAt: now,
          updatedAt: now,
        ),
        const [],
      );
      row = (await db.reportByUuid(uuid))!;
    }
    final existing = await db.mediaForReport(row.clientUuid);
    if (existing.length >= MediaRules.maxFilesPerReport) {
      throw ArgumentError('too many attachments');
    }
    final root = await mediaDir();
    final dir = Directory(p.join(root.path, row.clientUuid));
    await dir.create(recursive: true);
    final source = File(attachment.path);
    final copy = File(
      p.join(
        dir.path,
        'live_${now.millisecondsSinceEpoch}${p.extension(attachment.path)}',
      ),
    );
    await source.copy(copy.path);
    if (attachment.deleteSourceAfterQueue) {
      try {
        await source.delete();
      } on FileSystemException {
        // Best effort: a temporary file.
      }
    }
    final uuid = row.clientUuid;
    await db.transaction(() async {
      await db
          .into(db.mediaItems)
          .insert(
            MediaItemsCompanion.insert(
              reportUuid: uuid,
              path: copy.path,
              kind: attachment.kind.name,
              mime: attachment.mime,
              size: await copy.length(),
              sha256: await sha256OfFile(copy),
            ),
          );
      // A report already fully synced goes back to `created` so the engine picks the file up.
      final current = await db.reportByUuid(uuid);
      if (current != null && current.state == ReportState.synced) {
        await db.updateReport(
          uuid,
          PendingReportsCompanion(
            state: const Value(ReportState.created),
            updatedAt: Value(now),
          ),
        );
      }
    });
    return uuid;
  }

  /// Removes the local copy of a report the user dismissed (only used for failed/conflict).
  Future<void> discard(String clientUuid) async {
    final items = await db.mediaForReport(clientUuid);
    for (final m in items) {
      final f = File(m.path);
      if (await f.exists()) await f.delete();
    }
    await db.transaction(() async {
      await (db.delete(
        db.mediaItems,
      )..where((m) => m.reportUuid.equals(clientUuid))).go();
      await (db.delete(
        db.pendingReports,
      )..where((r) => r.clientUuid.equals(clientUuid))).go();
    });
  }
}

/// Key of the institution in the `POST /api/v1/reports` body (phase 4 §8).
const organizationIdKey = 'organization_id';

/// Institution a queued report is sent for, read from its frozen payload.
String? payloadOrganizationId(String payload) {
  try {
    final json = jsonDecode(payload);
    if (json is! Map) return null;
    final id = json[organizationIdKey];
    return id is String ? id : null;
  } on FormatException {
    return null;
  }
}

/// Lowercase hex SHA-256 computed by streaming the file (videos can be 300 MB).
Future<String> sha256OfFile(File file) async =>
    (await sha256.bind(file.openRead()).first).toString();

Future<Directory> defaultMediaDir() async {
  final base = await getApplicationSupportDirectory();
  return Directory(p.join(base.path, 'queue_media'));
}

final mediaDirProvider = Provider<Future<Directory> Function()>(
  (ref) => defaultMediaDir,
);

final reportQueueProvider = Provider<ReportQueue>(
  (ref) => ReportQueue(
    db: ref.watch(databaseProvider),
    mediaDir: ref.watch(mediaDirProvider),
    clock: ref.watch(clockProvider),
  ),
);
