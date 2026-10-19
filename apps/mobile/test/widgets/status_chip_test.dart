import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/features/reports/status_chip.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Labels fixed by the contract (§3, status lifecycle).
const expected = {
  'ar': [
    'مستلم',
    'قيد المعالجة',
    'تم التدخل',
    'التدخل متواصل',
    'أُغلق التدخل',
    'مرفوض',
  ],
  'fr': [
    'Reçu',
    'En cours de traitement',
    'Intervention effectuée',
    'Intervention en cours',
    'Intervention clôturée',
    'Rejeté',
  ],
  'en': [
    'Received',
    'Being processed',
    'Intervened',
    'Intervention ongoing',
    'Closed',
    'Rejected',
  ],
};

void main() {
  test('wire values match the contract', () {
    expect(ReportStatus.values.map((s) => s.wire).toList(), [
      'received',
      'in_progress',
      'intervened',
      'ongoing',
      'closed',
      'rejected',
    ]);
    expect(ReportStatus.fromWire('in_progress'), ReportStatus.inProgress);
    expect(ReportStatus.fromWire('nope'), isNull);
  });

  for (final entry in expected.entries) {
    testWidgets('status chip labels (${entry.key})', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          locale: Locale(entry.key),
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          home: Scaffold(
            body: Column(
              children: [
                for (final s in ReportStatus.values)
                  ReportStatusChip(status: s),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      for (final label in entry.value) {
        expect(find.text(label), findsOneWidget, reason: label);
      }
    });
  }
}
