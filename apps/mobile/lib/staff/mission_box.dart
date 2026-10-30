import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/storage/secure_store.dart';
import 'prevention/prevention_store.dart';

/// One write of a mission kept on the phone until the server has it (phase P4d, design §9.1).
/// Its `client_id` and `device_at` are fixed when the leader presses the button: sent twice (over
/// the internet, or by SMS then over the internet) it is applied once, at the phone's time.
@immutable
class MissionWrite {
  const MissionWrite({
    required this.missionId,
    required this.action,
    required this.body,
    this.mediaType,
    this.smsAt,
    this.shown = const {},
  });

  factory MissionWrite.fromJson(Map<String, dynamic> j) => MissionWrite(
    missionId: j['mission'] as String,
    action: j['action'] as String,
    body: Map<String, dynamic>.of(j['body'] as Map<String, dynamic>),
    mediaType: j['media_type'] as String?,
    smsAt: j['sms_at'] == null ? null : DateTime.parse(j['sms_at'] as String),
    shown: j['shown'] as Map<String, dynamic>? ?? const {},
  );

  final String missionId;

  /// The last part of `/missions/{id}/…`: `ack`, `status`, `situation`, `casualties`,
  /// `transports`, `alerts`, `notes`, `attachments`, `detailed-report`, or (phase S2)
  /// `milestone` and `record`.
  final String action;

  /// The JSON body, or the query of an attachment (the bytes are sealed next to it).
  final Map<String, dynamic> body;

  /// An attachment's content type; its bytes are in the box under [id].
  final String? mediaType;

  /// When the leader opened the SMS app with this write (it stays queued until the internet).
  final DateTime? smsAt;

  /// What only the phone shows while the write waits (the hospital's name for a hospital of the
  /// map); never sent.
  final Map<String, dynamic> shown;

  String get id => body['client_id'] as String;
  DateTime get at => DateTime.parse(body['device_at'] as String);

  /// The event of the `EH2` text message, for the writes that have one (design §9.3).
  String? get smsEvent => switch (action) {
    'ack' => 'ack',
    'status' => body['status'] as String?,
    'milestone' => body['step'] as String?,
    'alerts' => body['kind'] as String?,
    _ => null,
  };

  MissionWrite sentBySms(DateTime at) => MissionWrite(
    missionId: missionId,
    action: action,
    body: body,
    mediaType: mediaType,
    smsAt: at,
    shown: shown,
  );

  Map<String, dynamic> toJson() => {
    'mission': missionId,
    'action': action,
    'body': body,
    'media_type': ?mediaType,
    'sms_at': ?smsAt?.toUtc().toIso8601String(),
    if (shown.isNotEmpty) 'shown': shown,
  };
}

/// A position of the vehicle waiting to be sent (design §9.2).
@immutable
class QueuedPosition {
  const QueuedPosition(
    this.missionId,
    this.lat,
    this.lon,
    this.at, [
    this.accuracyM,
  ]);

  factory QueuedPosition.fromJson(Map<String, dynamic> j) => QueuedPosition(
    j['mission'] as String,
    (j['lat'] as num).toDouble(),
    (j['lon'] as num).toDouble(),
    DateTime.parse(j['at'] as String),
    (j['accuracy_m'] as num?)?.toDouble(),
  );

  final String missionId;
  final double lat;
  final double lon;
  final DateTime at;
  final double? accuracyM;

  /// One position per mission and instant (the server's key too).
  String get key => '$missionId@${at.toUtc().toIso8601String()}';

  /// One point of `POST /missions/{id}/positions`.
  Map<String, dynamic> get wire => {
    'lat': lat,
    'lon': lon,
    'accuracy_m': ?accuracyM,
    'at': at.toUtc().toIso8601String(),
  };

  Map<String, dynamic> toJson() => {'mission': missionId, ...wire};
}

/// The last `/me` and missions, the writes that wait and the positions not sent yet, sealed on
/// the leader's phone (design §9.1). Erased with the vault: sign-out, remote wipe, five wrong PINs.
class MissionBox {
  MissionBox(BlobStore blobs, SecureStore secure)
    : _sealed = SealedBlobs(blobs, secure, keyName);

  /// In [StaffVault.keys].
  static const keyName = 'staff_box_key_v1';

  static const _cache = 'cache.bin';
  static const _outbox = 'outbox.bin';
  static const _positions = 'positions.bin';
  static String _media(String id) => 'media-$id.bin';

  final SealedBlobs _sealed;

  Future<MissionCache?> cache() async {
    if (!await _sealed.opened()) return null;
    final j = await _sealed.readJson(_cache);
    return j == null ? null : MissionCache.fromJson(j as Map<String, dynamic>);
  }

  Future<void> saveCache(MissionCache cache) =>
      _sealed.writeJson(_cache, cache.toJson());

  Future<List<MissionWrite>> outbox() async {
    if (!await _sealed.opened()) return const [];
    final j = await _sealed.readJson(_outbox) as List? ?? const [];
    return [
      for (final w in j) MissionWrite.fromJson(w as Map<String, dynamic>),
    ];
  }

  Future<void> saveOutbox(List<MissionWrite> writes) =>
      _sealed.writeJson(_outbox, [for (final w in writes) w.toJson()]);

  Future<List<QueuedPosition>> positions() async {
    if (!await _sealed.opened()) return const [];
    final j = await _sealed.readJson(_positions) as List? ?? const [];
    return [
      for (final p in j) QueuedPosition.fromJson(p as Map<String, dynamic>),
    ];
  }

  Future<void> savePositions(List<QueuedPosition> points) =>
      _sealed.writeJson(_positions, [for (final p in points) p.toJson()]);

  Future<void> saveMedia(String id, List<int> bytes) =>
      _sealed.write(_media(id), bytes);

  Future<Uint8List?> media(String id) async {
    final clear = await _sealed.read(_media(id));
    return clear == null ? null : Uint8List.fromList(clear);
  }

  Future<void> deleteMedia(String id) => _sealed.delete(_media(id));

  Future<void> wipe() => _sealed.wipe();
}

/// What the leader last saw: shown when the app opens without network.
@immutable
class MissionCache {
  const MissionCache({this.me, this.missions = const []});

  factory MissionCache.fromJson(Map<String, dynamic> j) => MissionCache(
    me: j['me'] as Map<String, dynamic>?,
    missions: [
      for (final m in j['missions'] as List? ?? const [])
        m as Map<String, dynamic>,
    ],
  );

  final Map<String, dynamic>? me;
  final List<Map<String, dynamic>> missions;

  Map<String, dynamic> toJson() => {'me': me, 'missions': missions};
}

/// [mission] as the leader will see it once the server has [w]: the step, the counters, the
/// alert or the note at once, marked as waiting. The server's answer replaces it.
Map<String, dynamic> applyLocally(
  Map<String, dynamic> mission,
  MissionWrite w,
) {
  final m = Map<String, dynamic>.of(mission);
  final at = w.body['device_at'] as String;
  final b = w.body;
  switch (w.action) {
    case 'ack':
      m['acknowledged_at'] ??= at;
    case 'status':
      final status = b['status'] as String;
      m['status'] = status;
      m['${status}_at'] = at;
      if (m['acknowledged_at'] == null) m['acknowledged_at'] = at;
    case 'milestone':
      final step = b['step'] as String;
      m['${step}_at'] ??= at;
      // Free on the way back or back at the unit ends the mission (record.py RELEASING).
      if ((step == 'available' || step == 'back_at_unit') &&
          m['status'] == 'on_scene') {
        m['status'] = 'released';
        m['released_at'] = at;
      }
    case 'record':
      if (b['crew_count'] != null) m['crew_count'] = b['crew_count'];
      if (b['consumables'] != null) m['consumables'] = b['consumables'];
    case 'casualties':
      final c = Map<String, dynamic>.of(
        m['casualties'] as Map<String, dynamic>? ?? const {},
      );
      for (final e in b.entries) {
        if (e.value case final int n) c[e.key] = ((c[e.key] as int?) ?? 0) + n;
      }
      m['casualties'] = c;
    case 'alerts':
      m['alerts'] = [
        ...m['alerts'] as List? ?? const [],
        {
          'id': w.id,
          'kind': b['kind'],
          'items': b['items'],
          'created_at': at,
          'pending': true,
        },
      ];
    case 'notes':
      m['attachments'] = [
        ...m['attachments'] as List? ?? const [],
        {'id': w.id, 'kind': 'text', 'body': b['body'], 'created_at': at},
      ];
    case 'attachments':
      m['attachments'] = [
        ...m['attachments'] as List? ?? const [],
        {
          'id': w.id,
          'kind': b['kind'],
          'duration_s': b['duration_s'],
          'created_at': at,
        },
      ];
    case 'transports':
      m['transports'] = [
        ...m['transports'] as List? ?? const [],
        {
          'id': w.id,
          'triage': b['triage'],
          'age_band': b['age_band'],
          'sex': b['sex'],
          'hospital': w.shown['hospital'] ?? b['hospital'] ?? '',
          'created_at': at,
        },
      ];
      final c = Map<String, dynamic>.of(
        m['casualties'] as Map<String, dynamic>? ?? const {},
      );
      c['transported'] = ((c['transported'] as int?) ?? 0) + 1;
      m['casualties'] = c;
    case 'situation':
      m['field_report'] = {
        'kind': m['field_report'] == null ? 'first' : 'update',
        'category': b['category'],
        'severity': b['severity'],
        'backup_needed': b['backup_needed'],
        'backup_kinds': b['backup_kinds'],
        'crew_danger': b['crew_danger'],
        'created_at': at,
      };
    case 'detailed-report':
      m['detailed_report'] = {
        'kind': 'detailed',
        'category': (m['incident'] as Map?)?['category'],
        'template_id': b['template_id'],
        'answers': b['answers'],
        'note': b['note'],
        'created_at': at,
      };
  }
  return m;
}

/// The missions' folder (phase P4d), apart from the visits'.
final missionBlobStoreProvider = Provider<BlobStore>(
  (ref) => FileBlobStore(folder: 'staff_missions'),
);

final missionBoxProvider = Provider<MissionBox>(
  (ref) => MissionBox(
    ref.watch(missionBlobStoreProvider),
    ref.watch(secureStoreProvider),
  ),
);
