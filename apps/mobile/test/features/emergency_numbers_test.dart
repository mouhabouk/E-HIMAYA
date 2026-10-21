// covers: FR-A-033
import 'package:ehimaya/features/emergency/emergency_numbers.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('the four national emergency numbers, civil protection first', () {
    expect(emergencyNumbers.map((n) => n.number).toList(), [
      '198',
      '190',
      '197',
      '193',
    ]);
    expect(emergencyNumbers.map((n) => n.service).toList(), [
      EmergencyService.civilProtection,
      EmergencyService.samu,
      EmergencyService.police,
      EmergencyService.nationalGuard,
    ]);
  });

  test('numbers are dialled with tel: URIs (native SIM call)', () {
    for (final n in emergencyNumbers) {
      expect(n.telUri.scheme, 'tel');
      expect(n.telUri.toString(), 'tel:${n.number}');
    }
  });

  test('every service has a label in ar, fr and en', () {
    for (final code in ['ar', 'fr', 'en']) {
      final l10n = lookupAppLocalizations(Locale(code));
      final labels = emergencyNumbers.map((n) => n.label(l10n)).toSet();
      expect(labels, hasLength(4));
      expect(labels.every((l) => l.isNotEmpty), isTrue);
    }
    expect(
      emergencyNumbers.first.label(lookupAppLocalizations(const Locale('ar'))),
      'الحماية المدنية',
    );
  });
}
