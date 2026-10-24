import 'dart:convert';

import 'package:drift/drift.dart' show Value;
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/safety/safety_models.dart';
import 'package:ehimaya/features/safety/safety_reminders.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';

Future<void> go(WidgetTester tester, String location) async {
  final context = tester.element(find.byType(Scaffold).first);
  ProviderScope.containerOf(context).read(routerProvider).go(location);
  await tester.pumpAndSettle();
}

class FakeReminders implements SafetyReminders {
  final scheduled = <DateTime>[];
  int cancelled = 0;

  @override
  Future<void> schedule(DateTime dueAt, ReminderTexts texts) async =>
      scheduled.add(dueAt);

  @override
  Future<void> cancel() async => cancelled++;
}

const _link = {
  'id': 'link-1',
  'first_name': 'Hela',
  'phone': '+21620123456',
  'created_at': '2026-10-23T08:00:00Z',
};

Map<String, Object?> _alert({bool mine = false}) => {
  'id': 'alert-1',
  'kind': 'sos',
  'mine': mine,
  'sender_first_name': 'Hela',
  'sender_phone': '+21620123456',
  'message': 'Je suis bloquée près du pont.',
  'position': {
    'lat': 36.8,
    'lon': 10.18,
    'accuracy_m': 15.0,
    'at': '2026-10-23T08:30:00Z',
  },
  'battery': 23,
  'created_at': '2026-10-23T08:30:00Z',
  'expires_at': '2026-10-24T08:30:00Z',
  'seen': false,
  'live': null,
};

FakeResponse _safetyApi(SeenRequest r) => switch ((r.method, r.path)) {
  ('GET', '/api/v1/safety/links') => const FakeResponse(
    200,
    json: {
      'items': [_link],
    },
  ),
  ('POST', '/api/v1/safety/alerts') => const FakeResponse(
    201,
    json: {
      'id': 'alert-9',
      'recipients': 1,
      'created_at': '2026-10-23T09:00:00Z',
    },
  ),
  ('GET', '/api/v1/safety/alerts') => const FakeResponse(
    200,
    json: {'items': []},
  ),
  ('GET', '/api/v1/safety/alerts/alert-1') => FakeResponse(200, json: _alert()),
  ('POST', '/api/v1/safety/alerts/alert-1/seen') => const FakeResponse(204),
  ('GET', '/api/v1/safety/invitations/ABCD-EFGH') => const FakeResponse(
    200,
    json: {
      'first_name': 'Karim',
      'phone_hint': '•• •• 32',
      'expires_at': '2026-10-24T09:00:00Z',
    },
  ),
  ('POST', '/api/v1/safety/invitations/ABCD-EFGH/accept') => const FakeResponse(
    201,
    json: _link,
  ),
  ('GET', '/api/v1/safety/checks/current') => const FakeResponse(
    200,
    json: null,
  ),
  ('POST', '/api/v1/safety/checks') => const FakeResponse(
    201,
    json: {
      'id': 'check-1',
      'due_at': '2026-10-23T10:00:00Z',
      'status': 'active',
      'created_at': '2026-10-23T09:00:00Z',
      'alert_id': null,
      'contacts': 1,
    },
  ),
  ('GET', '/api/v1/safety/history') => const FakeResponse(
    200,
    json: {
      'available': false,
      'enabled': false,
      'until': null,
      'notice_version': '7b-2026-10',
    },
  ),
  _ => defaultApiResponse(r),
};

Future<void> _addContact(AppDatabase db, String name, String phone) => db
    .addContact(
      EmergencyContactsCompanion.insert(
        name: name,
        phone: phone,
        createdAt: DateTime(2026),
      ),
    )
    .then((_) {});

void main() {
  testWidgets(
    'settings lead to the safety hub; the location history stays hidden',
    (tester) async {
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        api: _safetyApi,
      );
      await go(tester, Routes.settings);
      await tester.scrollUntilVisible(
        find.byKey(const Key('settings-safety')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('settings-safety')));
      await tester.pumpAndSettle();
      expect(find.text('Personal safety'), findsOneWidget);
      expect(find.byKey(const Key('safety-contacts')), findsOneWidget);
      expect(find.byKey(const Key('safety-location-history')), findsNothing);
      await unmountApp(tester);
    },
  );

  testWidgets('a contact chosen in the system picker is kept on the phone', (
    tester,
  ) async {
    final device = FakeDeviceServices()
      ..picked = const PickedContact(name: 'Karim', phone: '98 765 432');
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [deviceServicesProvider.overrideWithValue(device)],
    );
    await go(tester, Routes.safetyContacts);
    await tester.tap(find.byKey(const Key('contacts-add')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('contacts-pick')));
    await tester.pumpAndSettle();
    expect(find.text('Karim'), findsOneWidget);
    await tester.tap(find.byKey(const Key('contact-save')));
    await tester.pumpAndSettle();
    final saved = await h.db.allContacts();
    expect(saved.single.name, 'Karim');
    expect(saved.single.phone, '+21698765432');

    // A group, and the contact put in it.
    await tester.tap(find.byKey(const Key('groups-add')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('group-name')), 'Family');
    await tester.tap(find.byKey(const Key('group-save')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(Key('contact-menu-${saved.single.id}')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Groups').last);
    await tester.pumpAndSettle();
    await tester.tap(find.byType(CheckboxListTile));
    await tester.tap(find.byKey(const Key('contact-groups-save')));
    await tester.pumpAndSettle();
    final groupId = (await h.db.select(h.db.contactGroups).get()).single.id;
    expect(inGroup((await h.db.allContacts()).single.groups, groupId), isTrue);
    await unmountApp(tester);
  });

  testWidgets(
    'SOS message: linked contacts alerted in the app, then the SMS app with every number',
    (tester) async {
      final opened = <Uri>[];
      final h = await pumpApp(
        tester,
        prefs: {
          ...registeredPrefs(locale: 'en'),
          'safety.sos_cancel_window': false,
          'safety.sos_template': 'Help me',
        },
        session: testSession,
        api: _safetyApi,
        opened: opened,
        overrides: [
          deviceServicesProvider.overrideWithValue(
            FakeDeviceServices(
              reading: const BatteryReading(level: 64, charging: false),
            ),
          ),
        ],
      );
      await _addContact(h.db, 'Hela', '20 123 456');
      await _addContact(h.db, 'Sami', '+21655000111');
      await tester.tap(find.byKey(const Key('home-sos-message')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('sos-send')));
      await tester.pumpAndSettle();

      final sent = h.adapter.requests.singleWhere(
        (r) => r.method == 'POST' && r.path == '/api/v1/safety/alerts',
      );
      final body = sent.json! as Map<String, Object?>;
      expect(body['message'], 'Help me');
      expect(body['link_ids'], isNull, reason: 'everyone: every link');
      expect(body['battery'], 64);
      expect((body['location']! as Map)['lat'], 36.8);
      final sms = opened.singleWhere((u) => u.scheme == 'sms');
      expect(sms.path, '+21620123456,+21655000111');
      expect(Uri.decodeComponent(sms.query), contains('Help me'));
      expect(Uri.decodeComponent(sms.query), contains('openstreetmap.org'));
      expect(find.byKey(const Key('sos-sent-app')), findsOneWidget);
      expect(find.byKey(const Key('sos-sent-sms')), findsOneWidget);

      final history = await h.db.select(h.db.safetyAlertHistory).get();
      expect(history.single.kind, 'sos_message');
      expect(history.single.channels, 'app,sms');
      expect(history.single.serverId, 'alert-9');

      // WhatsApp afterwards, one contact at a time.
      await tester.scrollUntilVisible(
        find.byKey(const Key('sos-whatsapp-share')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('sos-whatsapp-share')));
      expect(opened.last.host, 'wa.me');
      await unmountApp(tester);
    },
  );

  testWidgets(
    'SOS message: the 5-second window cancels before anything is sent',
    (tester) async {
      final opened = <Uri>[];
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        opened: opened,
        overrides: [
          deviceServicesProvider.overrideWithValue(FakeDeviceServices()),
        ],
      );
      await _addContact(h.db, 'Hela', '+21620123456');
      await go(tester, Routes.safetySend);
      await tester.tap(find.byKey(const Key('sos-send')));
      await tester.pump();
      expect(find.text('Sending in 5 s…'), findsOneWidget);
      await tester.pump(const Duration(seconds: 2));
      expect(find.text('Sending in 3 s…'), findsOneWidget);
      await tester.tap(find.byKey(const Key('sos-cancel')));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 5));
      expect(opened, isEmpty);
      expect(
        h.adapter.requests.where((r) => r.path.startsWith('/api/v1/safety')),
        isEmpty,
      );
      expect(
        (await h.db.select(h.db.safetyAlertHistory).get()).single.status,
        'cancelled',
      );

      // Without the window, a guest's message goes by SMS only.
      await tester.tap(find.byKey(const Key('sos-send')));
      await tester.pump(const Duration(seconds: 6));
      await tester.pumpAndSettle();
      expect(opened.single.scheme, 'sms');
      await unmountApp(tester);
    },
  );

  testWidgets('linking with a code: preview, then accept', (tester) async {
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: _safetyApi,
    );
    await go(tester, Routes.safetyLinked);
    expect(find.text('Hela'), findsOneWidget);
    await tester.tap(find.byKey(const Key('linked-enter-code')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('code-field')), 'ABCD-EFGH');
    await tester.tap(find.byKey(const Key('code-check')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Karim · •• •• 32'), findsOneWidget);
    await tester.tap(find.byKey(const Key('code-accept')));
    await tester.pumpAndSettle();
    expect(
      h.adapter.requests.where(
        (r) =>
            r.method == 'POST' &&
            r.path == '/api/v1/safety/invitations/ABCD-EFGH/accept',
      ),
      hasLength(1),
    );
    expect(find.text('You are now linked.'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('a guest is asked to create an account before linking', (
    tester,
  ) async {
    await pumpApp(tester, prefs: onboardedPrefs(locale: 'en'));
    await go(tester, Routes.safetyLinked);
    expect(find.byKey(const Key('safety-registration-needed')), findsOneWidget);
    expect(find.byKey(const Key('linked-invite')), findsNothing);
    await unmountApp(tester);
  });

  testWidgets('received alert: message, position, battery; call and 198', (
    tester,
  ) async {
    // A tall screen: the whole alert fits (the map would take a scroll gesture).
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: _safetyApi,
    );
    await go(tester, Routes.safetyAlert('alert-1'));
    expect(find.text('Hela a besoin d’aide'), findsOneWidget);
    expect(find.text('Je suis bloquée près du pont.'), findsOneWidget);
    expect(find.textContaining('batterie 23 %'), findsOneWidget);
    expect(
      h.adapter.requests.where(
        (r) => r.path == '/api/v1/safety/alerts/alert-1/seen',
      ),
      hasLength(1),
    );
    await tester.tap(find.byKey(const Key('alert-call')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('alert-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled, [
      Uri(scheme: 'tel', path: '+21620123456'),
      Uri(scheme: 'tel', path: '198'),
    ]);
    await unmountApp(tester);
  });

  testWidgets('safety check: started with reminders 10 and 1 minutes before', (
    tester,
  ) async {
    final reminders = FakeReminders();
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: _safetyApi,
      overrides: [
        safetyRemindersProvider.overrideWithValue(reminders),
        deviceServicesProvider.overrideWithValue(FakeDeviceServices()),
      ],
    );
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    await go(tester, Routes.safetyCheck);
    await tester.tap(find.byKey(const Key('check-minutes-120')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('check-start')));
    await tester.pumpAndSettle();
    final body =
        h.adapter.requests
                .singleWhere(
                  (r) =>
                      r.method == 'POST' && r.path == '/api/v1/safety/checks',
                )
                .json!
            as Map<String, Object?>;
    expect(body['minutes'], 120);
    expect(body['message'], isNotEmpty);
    expect(reminders.scheduled, [DateTime.utc(2026, 10, 23, 10)]);
    expect(
      (await h.db.select(h.db.safetyAlertHistory).get()).single.kind,
      'safety_check',
    );
    await unmountApp(tester);
  });

  testWidgets(
    'medical file: own consent, saved on the phone, locked, deleted',
    (tester) async {
      tester.view.physicalSize = const Size(1080, 3200);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      final device = FakeDeviceServices();
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        overrides: [deviceServicesProvider.overrideWithValue(device)],
      );
      await go(tester, Routes.safetyMedical);
      final create = tester.widget<FilledButton>(
        find.ancestor(
          of: find.text('Create my medical file'),
          matching: find.byType(FilledButton),
        ),
      );
      expect(create.onPressed, isNull, reason: 'consent first');
      await tester.tap(find.byKey(const Key('medical-consent')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('medical-create')));
      await tester.pumpAndSettle();
      expect(
        (await h.db.medical())?.consentVersion,
        SafetyRules.medicalConsentVersion,
      );

      await tester.enterText(
        find.byKey(const Key('medical-allergies')),
        'penicillin',
      );
      await tester.scrollUntilVisible(
        find.byKey(const Key('medical-save')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('medical-save')));
      await tester.pumpAndSettle();
      final saved = jsonDecode((await h.db.medical())!.data) as Map;
      expect(saved, {'allergies': 'penicillin'});

      // Lock: the phone's own lock is asked first.
      await tester.tap(find.byKey(const Key('medical-lock')));
      await tester.pumpAndSettle();
      expect(device.credentialRequests, 1);
      expect((await h.db.medical())!.locked, isTrue);

      await tester.scrollUntilVisible(
        find.byKey(const Key('medical-delete')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.byKey(const Key('medical-delete')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('medical-delete-confirm')));
      await tester.pumpAndSettle();
      expect(await h.db.medical(), isNull);
      expect(find.byKey(const Key('medical-consent')), findsOneWidget);
      await unmountApp(tester);
    },
  );

  testWidgets('a locked medical file asks for the phone lock before it opens', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final device = FakeDeviceServices()..credential = false;
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [deviceServicesProvider.overrideWithValue(device)],
    );
    await h.db.saveMedical(
      MedicalProfilesCompanion.insert(
        id: const Value(1),
        data: '{"blood_group":"O+"}',
        consentVersion: SafetyRules.medicalConsentVersion,
        consentAt: DateTime(2026),
        locked: const Value(true),
        updatedAt: DateTime(2026),
      ),
    );
    await go(tester, Routes.safetyMedical);
    expect(find.text('Your medical file is locked.'), findsOneWidget);
    await tester.tap(find.byKey(const Key('medical-unlock')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('medical-save')), findsNothing);
    device.credential = true;
    await tester.tap(find.byKey(const Key('medical-unlock')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('medical-save')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('a report carries the medical file only when ticked', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [
        deviceServicesProvider.overrideWithValue(FakeDeviceServices()),
      ],
    );
    await h.db.saveMedical(
      MedicalProfilesCompanion.insert(
        id: const Value(1),
        data: '{"blood_group":"AB-","medications":"insulin"}',
        consentVersion: SafetyRules.medicalConsentVersion,
        consentAt: DateTime(2026),
        updatedAt: DateTime(2026),
      ),
    );
    await go(tester, Routes.newReportFor(ReportCategory.medical));
    final box = find.byKey(const Key('report-attach-medical'));
    await tester.scrollUntilVisible(
      box,
      200,
      scrollable: find.byType(Scrollable).first,
    );
    expect(tester.widget<CheckboxListTile>(box).value, isFalse);
    await tester.tap(box);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const Key('report-submit')),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.byKey(const Key('report-submit')));
    await tester.pumpAndSettle();
    final queued = (await h.db.select(h.db.pendingReports).get()).single;
    final payload = jsonDecode(queued.payload) as Map<String, Object?>;
    expect(payload['medical'], {
      'blood_group': 'AB-',
      'medications': 'insulin',
    });
    await unmountApp(tester);
  });
}
