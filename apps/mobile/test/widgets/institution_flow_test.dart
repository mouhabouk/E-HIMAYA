import 'dart:convert';

import 'package:drift/drift.dart' show Value;
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/institution/my_institution_screen.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/org_fixtures.dart';

FakeResponse api(SeenRequest r, {bool offline = false}) {
  if (offline) return const FakeResponse.network();
  switch (r.path) {
    case '/api/v1/orgs/mine':
      return FakeResponse(200, json: [orgRow(orgId, 'Société X', 'active')]);
    case '/api/v1/orgs/$orgId/summary':
      return FakeResponse(200, json: summaryJson());
    case '/api/v1/orgs/$orgId/reports':
      return const FakeResponse(
        200,
        json: {
          'items': [
            {
              'id': 'r9',
              'tracking_code': 'EH-26-61-0000099',
              'category': 'chemical_leak',
              'status': 'in_progress',
              'text': null,
              'received_at': '2026-10-19T10:15:02Z',
              'updated_at': '2026-10-19T10:20:00Z',
              'reporter_display_name': 'amel',
            },
          ],
          'next_cursor': null,
        },
      );
    case '/api/v1/reports/mine':
      return const FakeResponse(
        200,
        json: {
          'items': [
            {
              'id': 'r9',
              'tracking_code': 'EH-26-61-0000099',
              'client_uuid': 'u9',
              'category': 'chemical_leak',
              'status': 'in_progress',
              'created_at': '2026-10-19T10:15:00Z',
              'media': <Object?>[],
              'organization': {'id': orgId, 'name': 'Société X'},
            },
          ],
          'next_before': null,
        },
      );
  }
  return const FakeResponse(404, json: {'detail': 'not_found'});
}

void main() {
  Future<void> tallScreen(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 3000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
  }

  testWidgets('no institution entry for anonymous users', (tester) async {
    final h = await pumpApp(tester, prefs: onboardedPrefs(locale: 'fr'));
    expect(find.byKey(const Key('home-institution')), findsNothing);
    expect(
      h.adapter.requests.where((r) => r.path.startsWith('/api/v1/orgs')),
      isEmpty,
    );
    await unmountApp(tester);
  });

  testWidgets('"My institution" summary card (FR-A-081)', (tester) async {
    await tallScreen(tester);
    final opened = <Uri>[];
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: api,
      opened: opened,
    );
    expect(find.byType(HomeScreen), findsOneWidget);
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();

    expect(find.byType(MyInstitutionScreen), findsOneWidget);
    expect(find.text('Société X'), findsOneWidget);
    expect(find.text('Industrielle'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('420'), findsOneWidget);
    expect(find.text('Route de Gabès km 4'), findsOneWidget);
    expect(find.text('Établissement industriel'), findsOneWidget);
    expect(find.textContaining('Provisoire'), findsOneWidget);
    expect(find.text('2 alertes'), findsOneWidget);
    // Safety team with training status and tap-to-call.
    expect(find.text('Amel Ben Salah'), findsOneWidget);
    expect(find.text('Représentant'), findsOneWidget);
    expect(find.text('Formation : valide'), findsOneWidget);
    expect(find.text('Formation : expirée'), findsOneWidget);
    await tester.tap(find.byKey(const Key('call-+21698123456')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri(scheme: 'tel', path: '+21698123456')]);
    // Hazardous materials.
    expect(find.text('Matières dangereuses (1)'), findsOneWidget);
    expect(find.text('Acétone'), findsOneWidget);
    expect(find.textContaining('ONU 1090'), findsOneWidget);
    // Detailed editing is on the portal.
    await tester.ensureVisible(find.byKey(const Key('open-portal')));
    await tester.tap(find.byKey(const Key('open-portal')));
    await tester.pumpAndSettle();
    expect(opened, [Uri.parse('http://localhost:5174')]);
    // Recent reports of the institution with their status.
    expect(find.text('EH-26-61-0000099'), findsOneWidget);
    expect(find.text('En cours de traitement'), findsOneWidget);
    expect(find.text('Par amel'), findsOneWidget);

    // The summary is cached for offline viewing.
    expect(
      h.adapter.requests.map((r) => r.path),
      contains('/api/v1/orgs/mine'),
    );
    await unmountApp(tester);
  });

  testWidgets('offline: the last summary is shown with a notice', (
    tester,
  ) async {
    await tallScreen(tester);
    final secure = MemorySecureStore({
      SecureStoreKeys.orgCache: jsonEncode({
        'owner': 'sub:unknown',
        'mine': [orgRow(orgId, 'Société X', 'active')],
        'summaries': {
          orgId: {'saved_at': '2026-10-18T08:00:00Z', 'data': summaryJson()},
        },
      }),
    });
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: (r) => api(r, offline: true),
      secure: secure,
    );
    // The cached list is enough to show the entry point offline.
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Offline: copy saved on'), findsOneWidget);
    expect(find.text('Société X'), findsOneWidget);
    expect(find.text('Amel Ben Salah'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('Arabic summary is right-to-left with LTR phone numbers', (
    tester,
  ) async {
    await tallScreen(tester);
    await pumpApp(
      tester,
      prefs: registeredPrefs(),
      session: testSession,
      api: api,
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(MyInstitutionScreen));
    expect(Directionality.of(context), TextDirection.rtl);
    expect(find.text('صناعية'), findsOneWidget);
    final phone = tester.widget<Text>(find.text('+21698123456'));
    expect(phone.textDirection, TextDirection.ltr);
    await unmountApp(tester);
  });

  testWidgets('My reports: institution chip and "send as myself"', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: api,
    );
    final now = DateTime.utc(2026, 10, 19, 11);
    await h.db.insertReport(
      PendingReportsCompanion.insert(
        clientUuid: 'u1',
        category: 'fire',
        payload: jsonEncode({
          'client_uuid': 'u1',
          'category': 'fire',
          'location': {'lat': 34.7, 'lon': 10.7},
          'created_at': now.toIso8601String(),
          'organization_id': orgId,
        }),
        tempCode: 'TMP-ABCDEF',
        createdAt: now,
        updatedAt: now,
        state: const Value(ReportState.orgRefused),
        lastError: const Value('org_not_active'),
      ),
      const [],
    );
    await tester.tap(find.text('Mes signalements').last);
    await tester.pumpAndSettle();

    // Server row sent for the institution + local refused row: both show the chip.
    expect(find.text('Société X'), findsNWidgets(2));
    expect(find.text('Refusé pour l’établissement'), findsOneWidget);
    expect(find.textContaining('n’est pas actif'), findsOneWidget);

    await tester.tap(find.byKey(const Key('resend-as-self-u1')));
    await tester.pumpAndSettle();
    final row = (await h.db.reportByUuid('u1'))!;
    expect(row.state, ReportState.queued);
    expect(jsonDecode(row.payload), isNot(contains('organization_id')));
    expect(
      find.text('Le signalement sera envoyé en votre nom.'),
      findsOneWidget,
    );
    await unmountApp(tester);
  });

  testWidgets('SOS sheet offers "report as"; default is myself', (
    tester,
  ) async {
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: api,
    );
    await tester.tap(find.text('Mes signalements').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-fab')));
    await tester.pumpAndSettle();
    expect(find.text('Signaler en tant que'), findsOneWidget);
    await tester.tap(find.byKey(const Key('report-as-$orgId')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('sos-confirm')));
    await tester.pumpAndSettle();
    expect(h.sos.organizations, [orgId]);

    // The big button uses the settings default: myself.
    await tester.tap(find.text('Accueil').last);
    await tester.pumpAndSettle();
    await tester.longPress(find.byKey(const Key('sos-button')));
    await tester.pumpAndSettle();
    expect(h.sos.organizations, [orgId, null]);
    await unmountApp(tester);
  });

  testWidgets('SOS default for an institution is chosen in settings', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: api,
    );
    await tester.tap(find.text('Paramètres').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings-institution')), findsOneWidget);
    final choice = find.descendant(
      of: find.byKey(const Key('settings-sos-report-as')),
      matching: find.byKey(const Key('report-as-$orgId')),
    );
    await tester.ensureVisible(choice);
    await tester.tap(choice);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Accueil').last);
    await tester.pumpAndSettle();
    await tester.longPress(find.byKey(const Key('sos-button')));
    await tester.pumpAndSettle();
    expect(h.sos.organizations, [orgId]);
    await unmountApp(tester);
  });

  test('kind labels fixed by the contract (§1)', () {
    const expected = {
      'ar': ['صناعية', 'تعليمية', 'نزل', 'حكومية', 'خاصة', 'أخرى'],
      'fr': [
        'Industrielle',
        'Éducative',
        'Hôtel',
        'Administration publique',
        'Privée',
        'Autre',
      ],
      'en': [
        'Industrial',
        'Educational',
        'Hotel',
        'Government',
        'Private',
        'Other',
      ],
    };
    for (final entry in expected.entries) {
      final l10n = lookupAppLocalizations(Locale(entry.key));
      expect([
        l10n.orgKindIndustrial,
        l10n.orgKindEducational,
        l10n.orgKindHotel,
        l10n.orgKindGovernment,
        l10n.orgKindPrivate,
        l10n.orgKindOther,
      ], entry.value);
    }
  });
}
