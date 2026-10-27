import 'dart:convert';

import 'package:crypto/crypto.dart';

import 'mission_box.dart';

/// The `EH2` text message of a write that waits, for the gateway number when there is no
/// internet (phase P4d, design §9.3; read by `services/api/app/modules/ops/crew_sms.py`):
///
/// `EH2 <device> <assignment> <event> <unix time> <client_id> <signature>`
///
/// The ids are UUIDs without dashes; the signature is the first 16 hex digits of
/// HMAC-SHA256(phone's key, `EH2|device|assignment|event|time|client_id`). Under 160 characters,
/// ASCII only. Null for a write that has no text message (a note, a photo, the counters…).
String? crewSmsBody({
  required String key,
  required String deviceId,
  required MissionWrite write,
}) {
  final event = write.smsEvent;
  if (event == null) return null;
  String hex(String uuid) => uuid.replaceAll('-', '').toLowerCase();
  final parts = [
    hex(deviceId),
    hex(write.missionId),
    event,
    '${write.at.millisecondsSinceEpoch ~/ 1000}',
    hex(write.id),
  ];
  final mac = Hmac(
    sha256,
    utf8.encode(key),
  ).convert(utf8.encode(['EH2', ...parts].join('|')));
  return ['EH2', ...parts, mac.toString().substring(0, 16)].join(' ');
}
