import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/api_error.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/volunteer_models.dart';
import '../../core/storage/secure_store.dart';

/// Phase D (S2-5): a volunteer, a doctor among them, answers a call-out by SMS when there is no
/// internet: «قبلت» (with the minutes to arrive), «أعتذر», «وصلت». The message goes to the same
/// number as the SMS reports (EH1) and is signed with the volunteer's own key
/// (services/api/app/modules/volunteers/callout_sms.py):
///
/// `EH3 <volunteer> <callout> <reply> <eta> <unix time> <signature>`
String eh3Body({
  required String key,
  required String volunteerId,
  required String calloutId,
  required String reply,
  int eta = 0,
  required DateTime at,
}) {
  String hex(String uuid) => uuid.replaceAll('-', '').toLowerCase();
  final parts = [
    hex(volunteerId),
    hex(calloutId),
    reply,
    '${reply == 'accept' ? eta : 0}',
    '${at.millisecondsSinceEpoch ~/ 1000}',
  ];
  final mac = Hmac(
    sha256,
    utf8.encode(key),
  ).convert(utf8.encode(['EH3', ...parts].join('|')));
  return ['EH3', ...parts, mac.toString().substring(0, 16)].join(' ');
}

/// The volunteer's key and id, asked once while online and kept in the phone's keystore.
const _storeKey = 'volunteer_sms_key_v1';

final volunteerSmsKeyProvider = FutureProvider<VolunteerSmsKey?>((ref) async {
  final store = ref.read(secureStoreProvider);
  final kept = await store.read(_storeKey);
  if (kept != null) {
    final parts = kept.split(' ');
    if (parts.length == 2) return VolunteerSmsKey(parts[0], parts[1]);
  }
  try {
    final fresh = await ref.read(apiProvider).volunteerSmsKey();
    await store.write(_storeKey, '${fresh.key} ${fresh.volunteerId}');
    return fresh;
  } on ApiException {
    return null;
  }
}, retry: (_, _) => null);
