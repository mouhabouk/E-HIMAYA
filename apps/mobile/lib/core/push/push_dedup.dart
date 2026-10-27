import 'push_payload.dart';

/// What a push is about: `<type>:<id>`, exactly the Android notification `tag` and the APNs
/// `apns-collapse-id` the server sets (contract, phase 5.5). The app shows its own notifications
/// with the same tag, so a push received again in the foreground replaces the one the system
/// displayed in the background instead of stacking a second one. The id is the one in `data`:
/// `id`, else `callout_id` / `report_id` (the tracking code as a last resort).
String pushSubject(PushPayload p) {
  final d = p.data;
  String? first(List<String> keys) {
    for (final k in keys) {
      final v = d[k];
      if (v != null && v.isNotEmpty) return v;
    }
    return null;
  }

  final id = switch (p.kind) {
    PushKind.callout => first(['callout_id', 'id']),
    PushKind.reportStatus ||
    PushKind.teamStatus => first(['report_id', 'id', 'tracking_code', 'code']),
    _ => first(['id']),
  };
  return '${p.kind.wire}:${id ?? ''}';
}

/// One delivery of [pushSubject]: a second push with the same key is a duplicate (FCM retry,
/// the server re-sending, the simulator and FCM both delivering). A changed severity or report
/// status is a new event and alerts again.
String pushEventKey(PushPayload p) {
  final d = p.data;
  return [
    p.kind.wire,
    pushSubject(p),
    d['severity'] ?? '',
    d['status'] ?? '',
    d['team'] ?? '',
    d['version'] ?? '',
  ].join('|');
}

/// Stable 31-bit notification id for [pushSubject] (FNV-1a; `String.hashCode` is not
/// guaranteed stable across runs, the id must be).
int notificationIdFor(PushPayload p) {
  var h = 0x811c9dc5;
  for (final unit in pushSubject(p).codeUnits) {
    h ^= unit;
    h = (h * 0x01000193) & 0xffffffff;
  }
  return h & 0x7fffffff;
}

/// Remembers the pushes shown recently so a repeated push does not ring again.
class PushDeduper {
  PushDeduper({this.window = const Duration(minutes: 30), this.capacity = 128});

  final Duration window;
  final int capacity;
  final _seen = <String, DateTime>{}; // insertion-ordered

  /// True the first time [p] is seen within [window] (and records it).
  bool firstTime(PushPayload p, DateTime now) {
    _seen.removeWhere((_, at) => now.difference(at) >= window);
    final key = pushEventKey(p);
    if (_seen.containsKey(key)) return false;
    _seen[key] = now;
    while (_seen.length > capacity) {
      _seen.remove(_seen.keys.first);
    }
    return true;
  }
}
