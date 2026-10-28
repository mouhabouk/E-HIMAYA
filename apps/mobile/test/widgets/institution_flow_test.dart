import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show Value;
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/institution/maintenance_photo.dart';
import 'package:ehimaya/features/institution/my_institution_screen.dart';
import 'package:ehimaya/features/report/report_queued_screen.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/org_fixtures.dart';

final photoBytes = List.generate(2048, (i) => i % 251);

Map<String, Object?> messageJson() => {
  'id': 'msg1',
  'topic': 'other',
  'title': {'ar': 'تنبيه', 'fr': 'Vigilance canicule'},
  'body': {'ar': 'نص', 'fr': 'Vérifiez vos extincteurs et vos réserves d’eau.'},
  'published_at': '2026-10-24T08:00:00Z',
  'ack_required': true,
  'acked_at': null,
  'acked_by': null,
};

/// A decided prevention visit with one reservation (phase P3b).
const visitJson = <String, Object?>{
  'id': 'v1',
  'org_id': orgId,
  'origin': 'request',
  'status': 'decided',
  'request_note': null,
  'requested_by_name': 'Amel',
  'requested_at': '2026-10-01T08:00:00Z',
  'scheduled_on': '2026-10-20',
  'inspector_name': 'Cdt Ben Salah',
  'inspected_on': '2026-10-20',
  'attendees': null,
  'comparison': {
    'items': [
      {
        'key': 'building.capacity',
        'section': 'building',
        'declared': 300,
        'result': 'nonconform',
        'observed': '420',
        'note': null,
      },
    ],
    'conform': 14,
    'nonconform': 1,
    'not_checked': 2,
    'missing': [],
    'changes': [],
    'suggested': 'approved_with_reservations',
  },
  'decision': 'approved_with_reservations',
  'decision_reason': null,
  'decided_by_name': 'Cdt Ben Salah',
  'decided_at': '2026-10-22T10:00:00Z',
  'certificate': {
    'id': 'cp1',
    'kind': 'prevention',
    'code': 'EHP-26-61-000009',
    'status': 'approved',
    'superseded': false,
    'valid_until': '2027-10-22',
    'stamps': [],
  },
  'reservations': [
    {
      'id': 'r1',
      'visit_id': 'v1',
      'item_key': 'building.capacity',
      'text': 'Mettre à jour la capacité déclarée',
      'due_on': '2026-11-22',
      'state': 'open',
      'response_note': null,
      'responded_by_name': null,
      'responded_at': null,
      'lifted_by_name': null,
      'lift_note': null,
      'lifted_at': null,
    },
  ],
  'has_report': true,
  'cancel_reason': null,
  'cancelled_at': null,
  'created_at': '2026-10-01T08:00:00Z',
};

FakeResponse api(
  SeenRequest r, {
  bool offline = false,
  String role = 'member',
  int pending = 0,
}) {
  if (offline) return const FakeResponse.network();
  switch ((r.method, r.path)) {
    case ('PUT', '/api/v1/orgs/$orgId'):
      final body = r.json! as Map<String, Object?>;
      return FakeResponse(
        200,
        json: {
          ...cardJson(role: role, version: 4),
          ...body,
        },
      );
    case ('POST', '/api/v1/orgs'):
      return FakeResponse(
        201,
        json: {...cardJson(), 'id': 'new-org', 'status': 'pending_review'},
      );
    case ('POST', '/api/v1/orgs/$orgId/equipment/e1/maintenance'):
      final body = r.json! as Map<String, Object?>;
      return FakeResponse(
        201,
        json: {
          'id': 'm2',
          'equipment_id': 'e1',
          ...body,
          'photo_version': null,
          'recorded_by': 'Amel',
          'recorded_at': '2026-10-25T09:00:00Z',
        },
      );
    case ('POST', '/api/v1/orgs/$orgId/documents'):
      return const FakeResponse(
        201,
        json: {'id': 'd9', 'kind': 'maintenance_photo'},
      );
    case ('POST', '/api/v1/uploads/'):
      return const FakeResponse(
        201,
        headers: {'Location': '/api/v1/uploads/t9'},
      );
    case ('PATCH', '/api/v1/uploads/t9'):
      return FakeResponse(
        204,
        headers: {'Upload-Offset': '${photoBytes.length}'},
      );
    case ('POST', '/api/v1/orgs/$orgId/messages/msg1/ack'):
      return FakeResponse(
        200,
        json: {
          ...messageJson(),
          'acked_at': '2026-10-25T09:00:00Z',
          'acked_by': 'Amel',
        },
      );
    case ('POST', '/api/v1/orgs/$orgId/activities'):
      final body = r.json! as Map<String, Object?>;
      return FakeResponse(
        201,
        json: {
          'id': 'a2',
          ...body,
          'created_by': 'Amel',
          'created_at': '2026-10-25T09:00:00Z',
        },
      );
    case ('DELETE', '/api/v1/orgs/$orgId/activities/a1'):
      return const FakeResponse(204);
    case ('POST', '/api/v1/orgs/$orgId/invitations'):
      return const FakeResponse(201, json: {});
  }
  switch (r.path) {
    case '/api/v1/orgs/mine':
      return FakeResponse(
        200,
        json: [orgRow(orgId, 'Société X', 'active', role: role)],
      );
    case '/api/v1/orgs/$orgId':
      return FakeResponse(200, json: cardJson(role: role));
    case '/api/v1/orgs/$orgId/equipment':
      return FakeResponse(200, json: [equipmentJson()]);
    case '/api/v1/orgs/$orgId/features':
      return const FakeResponse(
        200,
        json: [
          {
            'id': 'f1',
            'kind': 'evacuation_point',
            'label': 'Parking nord',
            'location': {'lat': 34.701, 'lon': 10.72},
          },
        ],
      );
    case '/api/v1/orgs/$orgId/certificates':
      return const FakeResponse(
        200,
        json: [
          {
            'id': 'c1',
            'code': 'EH-CERT-0001',
            'status': 'approved',
            'superseded': false,
            'valid_until': '2027-06-30',
            'needs_update': true,
            'changes': [
              {
                'section': 'building',
                'field': 'capacity',
                'certified': 300,
                'current': 420,
              },
              {
                'section': 'hazmat',
                'field': 'items',
                'certified': [],
                'current': ['Chlore (UN 1017): 200 kg'],
              },
            ],
            'stamps': [
              {
                'id': 's1',
                'place': 'Direction régionale de Sfax',
                'gouvernorat_code': 61,
                'stamped_on': '2026-10-20',
                'note': null,
                'stamped_by_name': 'Leila',
                'recorded_at': '2026-10-20T09:00:00Z',
                'has_photo': false,
                'changes': [],
              },
            ],
          },
        ],
      );
    case '/api/v1/orgs/$orgId/prevention/visits':
      return const FakeResponse(200, json: [visitJson]);
    case '/api/v1/orgs/$orgId/prevention/visits/v1/report':
    case '/api/v1/orgs/$orgId/certificates/cp1/pdf':
      return FakeResponse(
        200,
        json: {'url': 'https://files.test${r.path}.pdf?sig=1'},
      );
    case '/api/v1/orgs/$orgId/annual-report':
      return FakeResponse(
        200,
        json: {
          'year': int.parse(r.uri.queryParameters['year']!),
          'org_id': orgId,
          'org_name': 'Société X',
          'generated_on': '2026-10-25',
          'drills': [
            {
              'id': 'a1',
              'kind': 'drill',
              'title': 'Évacuation générale',
              'starts_on': '2026-03-12',
              'ends_on': null,
              'participants': 120,
              'notes': 'Évacuation en 4 minutes',
              'created_by': 'Amel',
              'created_at': '2026-03-12T09:00:00Z',
            },
          ],
          'events': [],
          'participants': 120,
          'maintenance': 3,
          'training': {'valid': 2, 'expiring': 1, 'expired': 1, 'unknown': 0},
          'visits': [visitJson],
          'reservations': {'opened': 1, 'lifted': 0, 'open': 1, 'overdue': 0},
          'certificates': [visitJson['certificate']],
          'stamps': 1,
          'reports': 4,
        },
      );
    case '/api/v1/orgs/$orgId/members':
      return const FakeResponse(
        200,
        json: [
          {
            'user_id': 'u1',
            'display_name': 'Amel',
            'email': 'amel@societe-x.tn',
            'role': 'admin',
            'joined_at': '2026-01-01T00:00:00Z',
          },
        ],
      );
    case '/api/v1/orgs/$orgId/summary':
      return FakeResponse(200, json: summaryJson(messagesPending: pending));
    case '/api/v1/orgs/$orgId/messages':
      return FakeResponse(200, json: [messageJson()]);
    case '/api/v1/orgs/$orgId/awareness':
      return const FakeResponse(
        200,
        json: [
          {
            'id': 't1',
            'hazard': 'chemical_leak',
            'content': {
              'fr': {
                'title': 'Fuite de produit chimique sur le site',
                'do': ['Couper la ventilation de l’atelier'],
                'dont': ['Ne pas utiliser d’eau sur l’acide'],
              },
            },
            'updated_at': '2026-10-01T00:00:00Z',
          },
        ],
      );
    case '/api/v1/orgs/$orgId/activities':
      return const FakeResponse(
        200,
        json: [
          {
            'id': 'a1',
            'kind': 'drill',
            'title': 'Évacuation de l’atelier',
            'starts_on': '2026-09-12',
            'ends_on': null,
            'participants': 48,
            'notes': null,
            'created_by': 'Amel',
            'created_at': '2026-09-12T10:00:00Z',
          },
        ],
      );
    case '/api/v1/orgs/$orgId/equipment/e1/maintenance':
      return const FakeResponse(
        200,
        json: [
          {
            'id': 'm1',
            'equipment_id': 'e1',
            'done_on': '2025-06-01',
            'note': 'Recharge',
            'document_id': 'd1',
            'photo_version': 1,
            'recorded_by': 'Amel',
            'recorded_at': '2025-06-01T09:00:00Z',
          },
        ],
      );
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

  testWidgets('"My institution" home: readiness, alerts, sections (P2a)', (
    tester,
  ) async {
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
    // Readiness ring and what is missing.
    expect(find.text('50%'), findsOneWidget);
    expect(find.text('1 exigence manquante'), findsOneWidget);
    expect(find.textContaining('Dossier de sécurité'), findsOneWidget);
    // Alerts with their wording.
    expect(
      find.text('Formation expirée dans l’équipe de sécurité'),
      findsOneWidget,
    );
    expect(find.text('Maintenance d’équipement en retard'), findsOneWidget);
    // Recent reports of the institution with their status.
    await tester.ensureVisible(find.text('EH-26-61-0000099'));
    expect(find.text('En cours de traitement'), findsOneWidget);
    expect(find.text('Par amel'), findsOneWidget);

    // Safety team section with training status and tap-to-call.
    await tester.ensureVisible(find.byKey(const Key('org-section-team')));
    await tester.tap(find.byKey(const Key('org-section-team')));
    await tester.pumpAndSettle();
    expect(find.text('Amel Ben Salah'), findsOneWidget);
    expect(find.text('Représentant'), findsOneWidget);
    expect(find.text('Formation : valide'), findsOneWidget);
    expect(find.text('Formation : expirée'), findsOneWidget);
    await tester.tap(find.byKey(const Key('call-+21698123456')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri(scheme: 'tel', path: '+21698123456')]);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    // Hazardous materials section.
    await tester.ensureVisible(find.byKey(const Key('org-section-hazmat')));
    await tester.tap(find.byKey(const Key('org-section-hazmat')));
    await tester.pumpAndSettle();
    expect(find.text('Matières dangereuses (1)'), findsOneWidget);
    expect(find.text('Acétone'), findsOneWidget);
    expect(find.textContaining('ONU 1090'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    // Large files and full editing stay on the portal.
    await tester.ensureVisible(find.byKey(const Key('open-portal')));
    await tester.tap(find.byKey(const Key('open-portal')));
    await tester.pumpAndSettle();
    expect(opened, [Uri.parse('http://localhost:5174')]);

    // The bottom bar: 198 first, then reporting for the institution.
    await tester.tap(find.byKey(const Key('org-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled.last, Uri(scheme: 'tel', path: '198'));
    expect(find.byKey(const Key('org-report-as')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('card tabs show who sees each field; an admin edits them (P2a)', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: (r) => api(r, role: 'admin'),
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('org-section-card')));
    await tester.pumpAndSettle();
    // Identity tab.
    expect(find.text('1234567A'), findsOneWidget);
    expect(find.text('Public'), findsWidgets);
    expect(find.text('Établissement et Office'), findsWidgets);
    // Kind tab: the working list and the field only the operations room sees on a report.
    await tester.tap(find.text('Propre au type').first);
    await tester.pumpAndSettle();
    expect(find.textContaining('[SIM]'), findsOneWidget);
    expect(find.text('Ouvriers par poste'), findsOneWidget);
    expect(find.text('35'), findsOneWidget);
    expect(find.text('Réservoirs'), findsOneWidget);
    expect(find.text("Lors d'un signalement proche"), findsOneWidget);

    // Edit: a number above the limit is caught (the field takes digits only), then the card is saved with its version.
    await tester.tap(find.byKey(const Key('org-card-edit')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('kf-tanks')), '99999999');
    await tester.tap(find.byKey(const Key('org-card-save')));
    await tester.pumpAndSettle();
    expect(
      find.text('Saisissez un nombre entier dans les limites.'),
      findsWidgets,
    );
    await tester.enterText(find.byKey(const Key('kf-tanks')), '3');
    await tester.enterText(find.byKey(const Key('edit-capacity')), '450');
    await tester.tap(find.byKey(const Key('org-card-save')));
    await tester.pumpAndSettle();
    final put = h.adapter.requests.lastWhere((r) => r.method == 'PUT');
    final body = put.json! as Map<String, Object?>;
    expect(body['version'], 3);
    expect(body['capacity'], 450);
    expect(body['kind_fields'], {'workers_per_shift': 35, 'tanks': 3});
    expect(body['identifier'], '1234567A');
    expect(find.text('Enregistré.'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets(
    'sections: maintenance logged, evacuation, certificates, invite',
    (tester) async {
      await tallScreen(tester);
      final h = await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'fr'),
        session: testSession,
        api: (r) => api(r, role: 'admin'),
      );
      await tester.tap(find.byKey(const Key('home-institution')));
      await tester.pumpAndSettle();
      Future<void> open(String section) async {
        await tester.ensureVisible(find.byKey(Key('org-section-$section')));
        await tester.tap(find.byKey(Key('org-section-$section')));
        await tester.pumpAndSettle();
      }

      await open('equipment');
      expect(find.text('Extincteur'), findsOneWidget);
      expect(find.text('Maintenance en retard'), findsOneWidget);
      await tester.tap(find.byKey(const Key('log-maintenance-e1')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('maintenance-note')),
        'Recharge annuelle',
      );
      await tester.tap(find.byKey(const Key('maintenance-save')));
      await tester.pumpAndSettle();
      final post = h.adapter.requests.lastWhere((r) => r.method == 'POST');
      expect(post.path, '/api/v1/orgs/$orgId/equipment/e1/maintenance');
      final sent = post.json! as Map;
      expect(sent['done_on'], matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
      expect(sent['note'], 'Recharge annuelle');
      expect(sent['document_id'], isNull);
      expect(find.text('Maintenance notée.'), findsOneWidget);
      // The log, with the state of each photo.
      await tester.tap(find.byKey(const Key('maintenance-history-toggle-e1')));
      await tester.pumpAndSettle();
      expect(find.text('Recharge'), findsOneWidget);
      expect(find.text('Photo conservée'), findsOneWidget);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();

      await open('evacuation');
      expect(find.text('Parking nord'), findsOneWidget);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();

      await open('certificates');
      expect(find.text('EH-CERT-0001'), findsOneWidget);
      expect(find.textContaining('Approuvé'), findsOneWidget);
      // P3a: needs updating with the sections that changed, and the hand stamp.
      expect(find.text('À mettre à jour'), findsOneWidget);
      expect(
        find.text(
          'Changé depuis l’approbation : Bâtiment, Matières dangereuses. '
          'Générez un nouveau certificat sur le portail.',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('Cacheté · Direction régionale de Sfax'),
        findsOneWidget,
      );
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();

      await open('members');
      expect(find.text('Amel'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('invite-email')),
        'nouveau@societe-x.tn',
      );
      await tester.tap(find.byKey(const Key('invite-send')));
      await tester.pumpAndSettle();
      final invite = h.adapter.requests.lastWhere((r) => r.method == 'POST');
      expect(invite.json, {'email': 'nouveau@societe-x.tn', 'role': 'member'});
      expect(
        find.text('Invitation envoyée à nouveau@societe-x.tn.'),
        findsOneWidget,
      );
      await unmountApp(tester);
    },
  );

  testWidgets('P3b: reports and records (F-APP-132)', (tester) async {
    await tallScreen(tester);
    final opened = <Uri>[];
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      opened: opened,
      api: (r) => api(r, role: 'member'),
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('org-section-records')));
    await tester.tap(find.byKey(const Key('org-section-records')));
    await tester.pumpAndSettle();

    expect(find.text('Rapports et procès-verbaux'), findsWidgets);
    // Reminders from the summary.
    expect(
      find.text('Formation expirée dans l’équipe de sécurité'),
      findsOneWidget,
    );
    // The visit: decision, comparison, certificate [SIM] and its documents.
    expect(find.text('Demandée par l’établissement'), findsOneWidget);
    expect(find.text('Avis favorable avec réserves'), findsOneWidget);
    expect(
      find.text(
        'Comparaison : 14 conformes · 1 non conformes · 2 non vérifiés',
      ),
      findsOneWidget,
    );
    expect(find.text('[SIM] Modèle en attente de l’Office'), findsOneWidget);
    await tester.tap(find.byKey(const Key('org-visit-report-v1')));
    await tester.pumpAndSettle();
    expect(
      opened.last.toString(),
      'https://files.test/api/v1/orgs/$orgId/prevention/visits/v1/report.pdf?sig=1',
    );
    await tester.tap(find.byKey(const Key('org-visit-certificate-v1')));
    await tester.pumpAndSettle();
    expect(opened.last.path, endsWith('/certificates/cp1/pdf.pdf'));
    // Reservations and deadlines.
    expect(find.text('Mettre à jour la capacité déclarée'), findsOneWidget);
    expect(find.textContaining('Ouverte · À lever avant le'), findsOneWidget);
    // Certificates of both kinds.
    expect(find.text('Certificat de sécurité · EH-CERT-0001'), findsOneWidget);
    // Annual report of this year, with the drill reports.
    final annual = h.adapter.requests.lastWhere(
      (r) => r.path.endsWith('/annual-report'),
    );
    expect(annual.uri.queryParameters['year'], '${DateTime.now().year}');
    await tester.ensureVisible(find.byKey(const Key('org-annual')));
    expect(find.text('1 exercice(s), 120 participant(s)'), findsOneWidget);
    expect(
      find.text('Réserves : 1 émises · 0 levées · 0 en retard'),
      findsOneWidget,
    );
    expect(find.text('Évacuation générale'), findsOneWidget);
    // Another year.
    await tester.ensureVisible(find.byKey(const Key('org-records-year')));
    await tester.tap(find.byKey(const Key('org-records-year')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('${DateTime.now().year - 1}').last);
    await tester.pumpAndSettle();
    expect(
      h.adapter.requests
          .lastWhere((r) => r.path.endsWith('/annual-report'))
          .uri
          .queryParameters['year'],
      '${DateTime.now().year - 1}',
    );
    await unmountApp(tester);
  });

  testWidgets('P2b: Office message acknowledged, awareness, drills', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: (r) => api(r, role: 'editor', pending: 1),
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();

    // The home says a message waits for the acknowledgement.
    expect(
      find.text('1 message du bureau attend votre accusé de lecture'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('org-messages-pending')));
    await tester.pumpAndSettle();
    expect(find.text('Messages du bureau'), findsOneWidget);
    expect(find.text('Vigilance canicule'), findsOneWidget);
    expect(find.text('Accusé de lecture demandé'), findsOneWidget);
    await tester.tap(find.byKey(const Key('org-message-ack-msg1')));
    await tester.pumpAndSettle();
    expect(
      h.adapter.requests.where(
        (r) =>
            r.method == 'POST' &&
            r.path == '/api/v1/orgs/$orgId/messages/msg1/ack',
      ),
      hasLength(1),
    );
    expect(find.text('Le bureau sait que vous l’avez lu.'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    Future<void> open(String section) async {
      await tester.ensureVisible(find.byKey(Key('org-section-$section')));
      await tester.tap(find.byKey(Key('org-section-$section')));
      await tester.pumpAndSettle();
    }

    // Awareness for the institution's kind.
    await open('awareness');
    expect(find.text('Fuite de produit chimique sur le site'), findsOneWidget);
    expect(find.text('Couper la ventilation de l’atelier'), findsOneWidget);
    expect(find.text('Ne pas utiliser d’eau sur l’acide'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    // Drills and events: the list, then a new drill held today, then a deletion.
    await open('activities');
    expect(find.text('Évacuation de l’atelier'), findsOneWidget);
    expect(find.text('48 participants'), findsOneWidget);
    await tester.tap(find.byKey(const Key('org-activity-add')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('org-activity-save')));
    await tester.pumpAndSettle();
    expect(find.text('Saisissez un titre.'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('org-activity-title')),
      'Exercice incendie',
    );
    await tester.enterText(
      find.byKey(const Key('org-activity-participants')),
      '60',
    );
    await tester.tap(find.byKey(const Key('org-activity-save')));
    await tester.pumpAndSettle();
    final added = h.adapter.requests.lastWhere(
      (r) => r.method == 'POST' && r.path.endsWith('/activities'),
    );
    final body = added.json! as Map;
    expect(body['kind'], 'drill');
    expect(body['title'], 'Exercice incendie');
    expect(body['participants'], 60);
    expect(body['ends_on'], isNull);
    expect(body['starts_on'], matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
    expect(find.text('Enregistré.'), findsOneWidget);

    await tester.tap(find.byKey(const Key('org-activity-delete-a1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('org-activity-delete-confirm')));
    await tester.pumpAndSettle();
    expect(h.adapter.requests.where((r) => r.method == 'DELETE'), hasLength(1));
    expect(find.text('Supprimé.'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('P2b: a maintenance with its photo; members cannot log', (
    tester,
  ) async {
    await tallScreen(tester);
    final dir = (await tester.runAsync(
      () => Directory.systemTemp.createTemp('maint'),
    ))!;
    addTearDown(() => dir.deleteSync(recursive: true));
    final photo = File('${dir.path}/photo.jpg')..writeAsBytesSync(photoBytes);
    var role = 'admin';
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: (r) => api(r, role: role),
      overrides: [
        maintenancePhotoPickerProvider.overrideWithValue(() async => photo),
      ],
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('org-section-equipment')));
    await tester.tap(find.byKey(const Key('org-section-equipment')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('log-maintenance-e1')));
    await tester.pumpAndSettle();

    // The photo is checked on the device, then sent before the maintenance.
    await tester.runAsync(() async {
      await tester.tap(find.byKey(const Key('maintenance-photo')));
      await Future<void>.delayed(const Duration(milliseconds: 200));
    });
    await tester.pumpAndSettle();
    expect(find.text('Photo jointe'), findsOneWidget);
    await tester.runAsync(() async {
      await tester.tap(find.byKey(const Key('maintenance-save')));
      await Future<void>.delayed(const Duration(milliseconds: 500));
    });
    await tester.pumpAndSettle();
    final paths = [
      for (final r in h.adapter.requests)
        if (r.method != 'GET') '${r.method} ${r.path}',
    ];
    expect(paths, [
      'POST /api/v1/orgs/$orgId/documents',
      'POST /api/v1/uploads/',
      'PATCH /api/v1/uploads/t9',
      'POST /api/v1/orgs/$orgId/equipment/e1/maintenance',
    ]);
    final created = h.adapter.requests.firstWhere(
      (r) => r.path == '/api/v1/uploads/',
    );
    final meta = {
      for (final pair in created.header('Upload-Metadata')!.split(','))
        pair.split(' ').first: utf8.decode(base64.decode(pair.split(' ').last)),
    };
    expect(meta['target'], 'org_document');
    expect(meta['document_id'], 'd9');
    expect(meta['filetype'], 'image/jpeg');
    final recorded = h.adapter.requests.lastWhere(
      (r) => r.method == 'POST' && r.path.endsWith('/maintenance'),
    );
    expect((recorded.json! as Map)['document_id'], 'd9');
    expect(find.text('Maintenance notée.'), findsOneWidget);
    await unmountApp(tester);

    // A member sees the log but cannot record.
    role = 'member';
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: (r) => api(r, role: role),
    );
    await tester.tap(find.byKey(const Key('home-institution')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('org-section-equipment')));
    await tester.tap(find.byKey(const Key('org-section-equipment')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('log-maintenance-e1')), findsNothing);
    expect(
      find.byKey(const Key('maintenance-history-toggle-e1')),
      findsOneWidget,
    );
    await unmountApp(tester);
  });

  testWidgets('registration from the phone in four steps (P2a)', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: api,
    );
    unawaited(
      GoRouter.of(tester.element(find.byType(HomeScreen)))
          .push(Routes.institutions),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('org-register')));
    await tester.pumpAndSettle();
    expect(find.text('Étape 1 sur 4'), findsOneWidget);
    // Step 1: the kind is required.
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    expect(find.text('Étape 1 sur 4'), findsOneWidget);
    await tester.tap(find.byKey(const Key('kind-health')));
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    // Step 2: identifier checked on the phone.
    await tester.enterText(find.byKey(const Key('org-name')), 'Clinique X');
    await tester.enterText(find.byKey(const Key('org-identifier')), '12345A');
    await tester.enterText(
      find.byKey(const Key('org-manager_name')),
      'Karim Trabelsi',
    );
    await tester.enterText(
      find.byKey(const Key('org-manager_phone')),
      '20 123 456',
    );
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    expect(
      find.text('Identifiant invalide : 7 chiffres et une lettre.'),
      findsOneWidget,
    );
    await tester.enterText(
      find.byKey(const Key('org-identifier')),
      ' 1234567a ',
    );
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    // Step 3: location from the phone, building and the kind's fields.
    expect(find.text('Étape 3 sur 4'), findsOneWidget);
    await tester.tap(find.byKey(const Key('org-locate')));
    await tester.pumpAndSettle();
    expect(find.textContaining('36.80000'), findsWidgets);
    await tester.enterText(
      find.byKey(const Key('org-address')),
      'Avenue Habib Bourguiba',
    );
    await tester.enterText(find.byKey(const Key('org-capacity')), '80');
    await tester.enterText(find.byKey(const Key('kf-beds')), '40');
    await tester.ensureVisible(find.byKey(const Key('kf-generator')));
    await tester.tap(find.byKey(const Key('kf-generator')));
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    // Step 4: review, then send.
    expect(find.text('Étape 4 sur 4'), findsOneWidget);
    expect(find.text('Santé'), findsOneWidget);
    expect(find.text('1234567A'), findsOneWidget);
    await tester.tap(find.byKey(const Key('org-register-next')));
    await tester.pumpAndSettle();
    final post = h.adapter.requests.lastWhere((r) => r.method == 'POST');
    expect(post.path, '/api/v1/orgs');
    expect(post.json, {
      'name': 'Clinique X',
      'kind': 'health',
      'identifier_type': 'mf',
      'identifier': '1234567A',
      'capacity': 80,
      'floors': null,
      'receives_public': false,
      'address': 'Avenue Habib Bourguiba',
      'location': {'lat': 36.8, 'lon': 10.18},
      'manager': {'full_name': 'Karim Trabelsi', 'phone': '+21620123456'},
      'contact_email': null,
      'kind_fields': {'beds': 40, 'generator': true},
    });
    expect(find.text('Enregistrement envoyé'), findsOneWidget);
    expect(find.text('En cours d’examen'), findsWidgets);
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
    expect(find.text('Expired training in the safety team'), findsOneWidget);
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
    await tester.ensureVisible(find.byKey(const Key('org-section-team')));
    await tester.tap(find.byKey(const Key('org-section-team')));
    await tester.pumpAndSettle();
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
    GoRouter.of(tester.element(find.byType(ReportQueuedScreen)))
        .go(Routes.home);
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

  test('kind labels: twelve since P2a (addition 12)', () {
    const expected = {
      'ar': ['صحية', 'صناعية', 'تربوية', 'سياحية', 'أخرى'],
      'fr': ['Santé', 'Industrielle', 'Éducation', 'Tourisme', 'Autre'],
      'en': ['Health', 'Industrial', 'Education', 'Tourism', 'Other'],
    };
    for (final entry in expected.entries) {
      final l10n = lookupAppLocalizations(Locale(entry.key));
      expect([
        l10n.orgKindHealth,
        l10n.orgKindIndustrial,
        l10n.orgKindEducation,
        l10n.orgKindTourism,
        l10n.orgKindOther,
      ], entry.value);
    }
  });
}
