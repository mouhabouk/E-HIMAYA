// covers: phase B1 "contact us" (docs/phase-b/design.md §2ter): emergency banner, rules of the form,
// request number, "my requests" with the Office's answer.
import 'dart:async';

import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/contact/contact_models.dart';
import 'package:ehimaya/features/settings/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

Map<String, Object?> _request({String status = 'received', String? answer}) => {
  'id': 'c1',
  'number': 'CT-2026-000042',
  'kind': 'access_info',
  'status': status,
  'subject': 'Budget des centres',
  'message': 'Je souhaite consulter le budget des centres de Sfax.',
  'gouvernorat_code': 61,
  'created_at': '2026-10-23T09:00:00Z',
  'due_at': '2026-11-12T09:00:00Z',
  'answer': answer,
  'answered_at': answer == null ? null : '2026-10-24T09:00:00Z',
  'history': [
    {
      'action': 'created',
      'status': 'received',
      'gouvernorat_code': 61,
      'at': '2026-10-23T09:00:00Z',
    },
  ],
};

void main() {
  test('models and rules', () {
    final r = MyContactRequest.fromJson(
      _request(status: 'answered', answer: 'Oui'),
    );
    expect(r.kind, ContactKind.accessInfo);
    expect(r.status, ContactStatus.answered);
    expect(r.history.single.status, ContactStatus.received);
    expect(ContactRules.nameRequired(ContactKind.accessInfo), isTrue);
    expect(ContactRules.gouvernoratRequired(ContactKind.hazard), isTrue);
    expect(ContactRules.gouvernoratRequired(ContactKind.question), isFalse);
    expect(ContactKind.fromWire('nope'), ContactKind.question);
  });

  testWidgets('send a request, get its number, read the answer', (
    tester,
  ) async {
    Map<String, Object?>? sent;
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      api: (r) {
        if (r.path == '/api/v1/geo/gouvernorats') {
          return const FakeResponse(
            200,
            json: [
              {
                'code': 61,
                'name': 'Sfax',
                'name_ar': 'صفاقس',
                'name_fr': 'Sfax',
              },
            ],
          );
        }
        if (r.path == '/api/v1/contact' && r.method == 'POST') {
          sent = r.json! as Map<String, Object?>;
          return FakeResponse(201, json: _request());
        }
        if (r.path == '/api/v1/me/contact') {
          return FakeResponse(
            200,
            json: {
              'items': [
                _request(
                  status: 'answered',
                  answer: 'The budget is published on our site.',
                ),
              ],
            },
          );
        }
        return defaultApiResponse(r);
      },
    );
    unawaited(
      GoRouter.of(tester.element(find.byType(Scaffold).first))
          .push(Routes.contact),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('contact-emergency-banner')), findsOneWidget);
    await tester.tap(find.byKey(const Key('contact-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled.last, Uri.parse('tel:198'));

    // Access to information: the name becomes required.
    await tester.tap(find.byKey(const Key('contact-kind')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Access to information (law 2016-22)').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('contact-access-info-hint')), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('contact-subject')),
      'Budget des centres',
    );
    await tester.enterText(
      find.byKey(const Key('contact-message')),
      'Je souhaite consulter le budget des centres de Sfax.',
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('contact-send')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    // Fully on screen: the taller design-system cards can leave it at the edge.
    await tester.ensureVisible(find.byKey(const Key('contact-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('contact-send')));
    await tester.pumpAndSettle();
    expect(sent, isNull);
    expect(find.text('Required.'), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('contact-name')),
      'Karim Trabelsi',
    );
    await tester.enterText(find.byKey(const Key('contact-phone')), '22333444');
    await tester.scrollUntilVisible(
      find.byKey(const Key('contact-send')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    // Fully on screen: the taller design-system cards can leave it at the edge.
    await tester.ensureVisible(find.byKey(const Key('contact-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('contact-send')));
    await tester.pumpAndSettle();
    expect(sent!['kind'], 'access_info');
    expect(sent!['phone'], '+21622333444');
    expect(sent!['email'], isNull);
    expect(find.byKey(const Key('contact-sent')), findsOneWidget);
    expect(find.text('CT-2026-000042'), findsOneWidget);

    await tester.tap(find.text('See my requests'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('answer-CT-2026-000042')), findsOneWidget);
    expect(find.text('Answered'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('settings lead to contact us', (tester) async {
    await pumpApp(tester, prefs: onboardedPrefs(locale: 'en'));
    unawaited(
      GoRouter.of(tester.element(find.byType(Scaffold).first))
          .push(Routes.settings),
    );
    await tester.pumpAndSettle();
    expect(find.byType(SettingsScreen), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('settings-contact')),
      200,
    );
    // Fully on screen: the taller design-system cards can leave it at the edge.
    await tester.ensureVisible(find.byKey(const Key('settings-contact')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings-contact')), findsOneWidget);
    await unmountApp(tester);
  });
}
