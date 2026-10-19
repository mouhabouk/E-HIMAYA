import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
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
  });

  final ReportCategory category;
  final GeoPoint location;
  final String? text;
  final String? lang;
  final List<DraftAttachment> attachments;
}

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

  Future<QueuedReport> enqueue(ReportDraft draft) async {
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
        createdAt: now,
        updatedAt: now,
      ),
      media,
    );
    return QueuedReport(clientUuid, tempCode);
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
