import 'dart:convert';
import 'dart:io';

import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> _load(String lang) =>
    jsonDecode(File('lib/l10n/app_$lang.arb').readAsStringSync())
        as Map<String, Object?>;

/// Phase 6 strings: the live indicator, the permission rationale, the fallback and the
/// simulation band exist in the three languages.
void main() {
  final langs = {'ar': _load('ar'), 'fr': _load('fr'), 'en': _load('en')};
  final liveKeys = _load('en').keys
      .where(
        (k) =>
            !k.startsWith('@') &&
            (k.startsWith('live') ||
                k == 'homeLive' ||
                k == 'homeLiveDesc' ||
                k == 'reportGoLive' ||
                k == 'errorStreamAlreadyActive' ||
                k == 'errorStreamNotActive' ||
                k == 'errorReportClosed'),
      )
      .toSet();

  test('every live key is translated in ar, fr and en', () {
    expect(liveKeys.length, greaterThan(40));
    for (final entry in langs.entries) {
      for (final key in liveKeys) {
        final value = entry.value[key];
        expect(value, isA<String>(), reason: '${entry.key}.$key');
        expect(
          (value! as String).trim(),
          isNotEmpty,
          reason: '${entry.key}.$key',
        );
      }
    }
  });

  test('the LIVE badge reads مباشر / EN DIRECT / LIVE', () {
    expect(langs['ar']!['liveBadge'], 'مباشر');
    expect(langs['fr']!['liveBadge'], 'EN DIRECT');
    expect(langs['en']!['liveBadge'], 'LIVE');
  });

  test('the simulation band uses the same wording as the rest of the app', () {
    for (final arb in langs.values) {
      expect(arb['liveSimulationBadge'], arb['pushSimulationBadge']);
    }
    expect(langs['ar']!['liveSimulationBadge'], 'وضع المحاكاة');
  });

  test('the permission rationale names the camera, the microphone and the location', () {
    expect(
      langs['ar']!['livePermissionRationale'],
      allOf(contains('الكاميرا'), contains('الميكروفون'), contains('موقعك')),
    );
    expect(
      langs['fr']!['livePermissionRationale'],
      allOf(contains('caméra'), contains('micro'), contains('position')),
    );
    expect(
      langs['en']!['livePermissionRationale'],
      allOf(contains('camera'), contains('microphone'), contains('location')),
    );
  });

  test('generated localizations format the placeholders', () async {
    for (final code in ['ar', 'fr', 'en']) {
      final l10n = await AppLocalizations.delegate.load(Locale(code));
      expect(l10n.liveReconnecting(2, 3), allOf(contains('2'), contains('3')));
      expect(l10n.liveEndedMaxDuration(15), contains('15'));
      expect(l10n.liveDuration('01:05'), contains('01:05'));
    }
  });
}
