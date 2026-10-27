import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/providers.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/storage/app_prefs.dart';
import 'beach_models.dart';

/// Today's risk of every beach (asked when the screen opens; the server caches it 15 minutes).
final beachesProvider = FutureProvider.autoDispose<BeachesReport>(
  (ref) => ref.read(apiProvider).coastalBeaches(),
  retry: (_, _) => null,
);

final beachDetailProvider = FutureProvider.autoDispose
    .family<BeachDetail, String>(
      (ref, id) => ref.read(apiProvider).coastalBeach(id),
      retry: (_, _) => null,
    );

/// A consent the user gives or takes back in one tap, kept on the phone.
class _Consent extends Notifier<bool> {
  _Consent(this._read, this._write);

  final bool Function(AppPrefs) _read;
  final Future<void> Function(AppPrefs, bool) _write;

  @override
  bool build() => _read(ref.read(appPrefsProvider));

  Future<void> set(bool value) async {
    state = value;
    await _write(ref.read(appPrefsProvider), value);
  }
}

/// "Warn me near a yellow or red beach": off until the user turns it on.
final beachWarningsProvider = NotifierProvider<_Consent, bool>(
  () => _Consent((p) => p.beachWarnings, (p, v) => p.setBeachWarnings(v)),
);

/// "Count me at the beach I say I am at" (anonymous): off until the user turns it on.
final beachPresenceProvider = NotifierProvider<_Consent, bool>(
  () => _Consent((p) => p.beachPresence, (p, v) => p.setBeachPresence(v)),
);

/// The random code of [day] (`yyyy-mm-dd`), drawn again each day so two days cannot be linked.
Future<String> dailyToken(AppPrefs prefs, String day, {Random? random}) async {
  final held = prefs.beachToken;
  if (held != null && held.startsWith('$day|')) {
    return held.substring(day.length + 1);
  }
  final rng = random ?? Random.secure();
  final token = base64Url
      .encode(List<int>.generate(24, (_) => rng.nextInt(256)))
      .replaceAll('=', '');
  await prefs.setBeachToken('$day|$token');
  return token;
}

/// Sends "I am at this beach" with the code of the day (the user agreed to it).
Future<void> sayPresent(Ref ref, String beachId) async {
  final now = ref.read(clockProvider)();
  final tunis = now.toUtc().add(const Duration(hours: 1));
  final day =
      '${tunis.year.toString().padLeft(4, '0')}-'
      '${tunis.month.toString().padLeft(2, '0')}-'
      '${tunis.day.toString().padLeft(2, '0')}';
  final token = await dailyToken(ref.read(appPrefsProvider), day);
  await ref.read(apiProvider).coastalPresence(beachId, token);
}

final presenceSenderProvider = Provider<Future<void> Function(String)>(
  (ref) =>
      (id) => sayPresent(ref, id),
);
