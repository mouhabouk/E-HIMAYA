// R4a (docs/phase-r/design-r4.md): count fields step with − and + buttons, keep a long
// press that speeds up, stay typeable, and name their buttons for screen readers.
import 'package:ehimaya/core/ui/components.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _host(
  TextEditingController c, {
  int min = 0,
  int max = 1000,
  int? start,
}) => MaterialApp(
  locale: const Locale('ar'),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  home: Scaffold(
    body: NumberStepper(
      fieldKey: const Key('n'),
      controller: c,
      label: 'السعة',
      min: min,
      max: max,
      start: start,
    ),
  ),
);

void main() {
  testWidgets('steps, stops at the bounds and names its buttons', (
    tester,
  ) async {
    final c = TextEditingController(text: '1');
    await tester.pumpWidget(_host(c, max: 2));
    await tester.pumpAndSettle();
    expect(find.bySemanticsLabel('زيادة السعة'), findsOneWidget);
    expect(find.bySemanticsLabel('إنقاص السعة'), findsOneWidget);
    await tester.tap(find.byKey(const Key('n-plus')));
    await tester.pump();
    expect(c.text, '2');
    await tester.tap(find.byKey(const Key('n-plus')));
    await tester.pump();
    expect(c.text, '2');
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.byKey(const Key('n-minus')));
      await tester.pump();
    }
    expect(c.text, '0');
  });

  testWidgets('starts an empty field at start, and repeats on a long press', (
    tester,
  ) async {
    final c = TextEditingController();
    await tester.pumpWidget(_host(c, min: 1, start: 10));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('n-plus')));
    await tester.pump();
    expect(c.text, '10');
    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('n-plus'))),
    );
    await tester.pump(kLongPressTimeout + const Duration(milliseconds: 10));
    await tester.pump(const Duration(milliseconds: 80 * 12));
    await gesture.up();
    final reached = int.parse(c.text);
    expect(reached, greaterThan(20));
    await tester.pump(const Duration(seconds: 1));
    expect(int.parse(c.text), reached);
  });

  testWidgets('stays typeable with digits only', (tester) async {
    final c = TextEditingController();
    await tester.pumpWidget(_host(c));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('n')), '4a2');
    expect(c.text, '42');
  });
}
