// OS8 (design-os8.md §6): the citizen's consent to an address warning, from the medical file.
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/features/safety/address_warnings_consent_screen.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _saved = <String, Object?>{
  'location': {'lat': 34.95, 'lon': 10.41},
  'address': '12 rue de Tunis, Sfax',
  'needs': [
    {
      'id': 'n-1',
      'category': 'mob',
      'description': 'Wheelchair, 2nd floor',
      'review_on': '2027-11-12',
    },
  ],
  'reveals': [
    {
      'id': 7,
      'at': '2026-11-12T08:00:00Z',
      'category': 'mob',
      'reason': 'To call and check someone is home',
    },
  ],
  'categories': <Object?>[],
};

Future<void> _pump(WidgetTester tester, MyAddressWarnings? value) async {
  SharedPreferences.setMockInitialValues({});
  final sp = await SharedPreferences.getInstance();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(sp),
        myAddressWarningsProvider.overrideWith((ref) async => value),
      ],
      child: const MaterialApp(
        locale: Locale('en'),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: AddressWarningsConsentScreen(),
      ),
    ),
  );
}

void main() {
  test('reads the consent the server keeps', () {
    final m = MyAddressWarnings.fromJson(_saved);
    expect(m.location!.lat, 34.95);
    expect(m.address, '12 rue de Tunis, Sfax');
    expect(m.needs, {'mob': 'Wheelchair, 2nd floor'});
    expect(m.reveals.single.reason, 'To call and check someone is home');
    expect(m.reveals.single.id, 7);
    expect(m.reveals.single.disputedAt, isNull);
  });

  testWidgets('OS8-2: the owner may object to a reading of their name', (
    tester,
  ) async {
    await _pump(tester, MyAddressWarnings.fromJson(_saved));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('aw-dispute-7')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('I know of no incident at my home'), findsOneWidget);
  });

  testWidgets('OS8-2: an objection already sent is shown, not offered again', (
    tester,
  ) async {
    final disputed = MyAddressWarnings.fromJson({
      ..._saved,
      'reveals': [
        {
          'id': 7,
          'at': '2026-11-12T08:00:00Z',
          'category': 'mob',
          'reason': 'To call and check someone is home',
          'disputed_at': '2026-11-12T09:00:00Z',
        },
      ],
    });
    await _pump(tester, disputed);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('aw-disputed-7')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.byKey(const Key('aw-dispute-7')), findsNothing);
  });

  testWidgets('shows the needs, who read the name and why, and withdraw', (
    tester,
  ) async {
    await _pump(tester, MyAddressWarnings.fromJson(_saved));
    await tester.pumpAndSettle();
    final mob = tester.widget<CheckboxListTile>(
      find.byKey(const Key('aw-need-mob')),
    );
    expect(mob.value, isTrue);
    expect(
      tester
          .widget<CheckboxListTile>(find.byKey(const Key('aw-need-oxy')))
          .value,
      isFalse,
    );
    await tester.scrollUntilVisible(
      find.text('To call and check someone is home'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('When the room read your name'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('aw-withdraw')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.byKey(const Key('aw-withdraw')), findsOneWidget);
  });

  testWidgets('a guest account is told to register', (tester) async {
    await _pump(tester, null);
    await tester.pumpAndSettle();
    expect(find.textContaining('registered account'), findsOneWidget);
    expect(find.byKey(const Key('aw-save')), findsNothing);
  });
}
