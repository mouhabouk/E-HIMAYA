import 'dart:io';

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_notifications.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/safety/safety_models.dart';
import 'package:ehimaya/features/safety/safety_providers.dart';
import 'package:ehimaya/features/safety/safety_reminders.dart';
import 'package:flutter_test/flutter_test.dart';

const _labels = SosLabels(
  position: 'Position',
  accuracy: 'Accuracy',
  time: 'Time',
  battery: 'Battery',
  noPosition: 'Position not available.',
);

EmergencyContact _contact(int id, String phone, {String groups = ','}) =>
    EmergencyContact(
      id: id,
      name: 'C$id',
      phone: phone,
      groups: groups,
      position: id,
      createdAt: DateTime(2026, 10, 23),
    );

void main() {
  group('SOS message (addition 5)', () {
    test('text: the user\'s words, position link, accuracy, time, battery', () {
      final text = sosMessageText(
        template: '  I need help.  ',
        labels: _labels,
        at: DateTime(2026, 10, 23, 9, 5),
        position: const GeoPoint(lat: 36.80651, lon: 10.18149, accuracyM: 12.2),
        battery: 41,
        liveLink: Uri.parse('https://portal.test/live#tok'),
      );
      expect(text.split('\n'), [
        'I need help.',
        'Position: https://www.openstreetmap.org/?mlat=36.80651&mlon=10.18149#map=17/36.80651/10.18149',
        'Accuracy: ± 13 m',
        'https://portal.test/live#tok',
        'Time: 09:05',
        'Battery: 41%',
      ]);
    });

    test('no position: said plainly, no link', () {
      final text = sosMessageText(
        template: 'Help',
        labels: _labels,
        at: DateTime(2026, 10, 23, 23, 59),
      );
      expect(text, 'Help\nPosition not available.\nTime: 23:59');
    });

    test('SMS to every number at once, WhatsApp one chat or the picker', () {
      final sms = smsGroupUri(['+21620000001', '+21698000002'], 'a b&c');
      expect(sms.toString(), 'sms:+21620000001,+21698000002?body=a%20b%26c');
      expect(
        whatsAppUri('+21620000001', 'hi').toString(),
        'https://wa.me/21620000001?text=hi',
      );
      expect(whatsAppShareUri('x y').toString(), 'https://wa.me/?text=x%20y');
    });

    test('phone numbers the SMS and WhatsApp apps accept', () {
      expect(normalizeContactPhone('20 123 456'), '+21620123456');
      expect(normalizeContactPhone('0021620123456'), '+21620123456');
      expect(normalizeContactPhone('216-20-123-456'), '+21620123456');
      expect(normalizeContactPhone('+33 6 12 34 56 78'), '+33612345678');
      expect(normalizeContactPhone('12'), isNull);
      expect(normalizeContactPhone('call me'), isNull);
    });

    test('linked contacts are matched by number', () {
      final links = [
        SafetyLink(id: 'L1', phone: '+21620123456', createdAt: DateTime(2026)),
        SafetyLink(id: 'L2', createdAt: DateTime(2026)),
      ];
      final matched = linkedContacts([
        _contact(1, '20 123 456'),
        _contact(2, '+21698000000'),
      ], links);
      expect(matched, {1: 'L1'});
    });

    test('groups are kept as ,id, lists', () {
      var g = ',';
      g = withGroup(g, 3, true);
      g = withGroup(g, 7, true);
      expect(inGroup(g, 3), isTrue);
      expect(inGroup(g, 7), isTrue);
      expect(inGroup(g, 37), isFalse);
      g = withGroup(g, 3, false);
      expect(inGroup(g, 3), isFalse);
      expect(withGroup(g, 7, false), ',');
    });
  });

  test(
    'live link: the token stays in the fragment (never sent to a server)',
    () {
      expect(
        liveLink('https://portal.ehimaya.tn/', 'abc').toString(),
        'https://portal.ehimaya.tn/live#abc',
      );
      expect(liveLink('https://p.test', 'abc').fragment, 'abc');
    },
  );

  test('medical file: only the filled fields, round trip', () {
    expect(const MedicalFile().isEmpty, isTrue);
    final f = MedicalFile.fromJson({
      'sex': 'female',
      'birth_date': '1984-03-02',
      'blood_group': 'AB-',
      'allergies': '  ',
      'medications': 'insuline',
    });
    expect(f.toJson(), {
      'sex': 'female',
      'birth_date': '1984-03-02',
      'blood_group': 'AB-',
      'medications': 'insuline',
    });
    expect(MedicalFile.fromJson(f.toJson()).toJson(), f.toJson());
  });

  test(
    'safety-check reminders: 10 min and 1 min before, only in the future',
    () {
      final due = DateTime(2026, 10, 23, 12);
      expect(reminderTimes(due, DateTime(2026, 10, 23, 11)).map((r) => r.$1), [
        LocalSafetyReminders.tenMinutesId,
        LocalSafetyReminders.oneMinuteId,
      ]);
      expect(
        reminderTimes(due, DateTime(2026, 10, 23, 11, 55)).map((r) => r.$1),
        [LocalSafetyReminders.oneMinuteId],
      );
      expect(reminderTimes(due, DateTime(2026, 10, 23, 12, 1)), isEmpty);
    },
  );

  group('safety pushes', () {
    PushPayload p(String type, [Map<String, String> data = const {}]) =>
        PushPayload.parse({'type': type, ...data})!;

    test('each kind opens its screen', () {
      expect(p('safety_alert', {'id': 'A1'}).route, Routes.safetyAlert('A1'));
      expect(p('safety_alert').route, Routes.safety);
      expect(p('safety_link').route, Routes.safetyLinked);
      expect(p('safety_check_fired').route, Routes.safetyCheck);
      expect(p('safety_check_reminder').route, Routes.safetyCheck);
      expect(p('safety_history_viewed').route, Routes.safetyLocationHistory);
    });

    test(
      'a linked contact\'s alert rings through Do Not Disturb once opted in',
      () {
        final alert = p('safety_alert', {'id': 'A1'});
        expect(pushChannelFor(alert, null, true), criticalChannelId);
        expect(pushChannelFor(alert, null, false), alertChannelId);
        expect(pushChannelFor(p('safety_link'), null, true), defaultChannelId);
        expect(alert.severe, isFalse, reason: 'never over the lock screen');
      },
    );
  });

  test(
    'local database 1 → 2: the safety tables are added, queued reports kept',
    () async {
      final dir = await Directory.systemTemp.createTemp('ehimaya-db');
      addTearDown(() => dir.delete(recursive: true));
      final file = File('${dir.path}/app.db');

      // A version-1 file: today's schema without the phase B2 tables.
      var db = AppDatabase(NativeDatabase(file));
      await db
          .into(db.pendingReports)
          .insert(
            PendingReportsCompanion.insert(
              clientUuid: 'u-1',
              category: 'fire',
              payload: '{}',
              tempCode: 'TMP-1',
              createdAt: DateTime(2026),
              updatedAt: DateTime(2026),
            ),
          );
      for (final t in [
        'emergency_contacts',
        'contact_groups',
        'safety_alert_history',
        'medical_profiles',
      ]) {
        await db.customStatement('DROP TABLE $t');
      }
      await db.customStatement('PRAGMA user_version = 1');
      await db.close();

      db = AppDatabase(NativeDatabase(file));
      addTearDown(db.close);
      expect((await db.reportByUuid('u-1'))?.tempCode, 'TMP-1');
      final id = await db.addContact(
        EmergencyContactsCompanion.insert(
          name: 'Karim',
          phone: '+21698765432',
          createdAt: DateTime(2026),
        ),
      );
      expect((await db.allContacts()).single.id, id);
      await db.saveMedical(
        MedicalProfilesCompanion.insert(
          id: const Value(1),
          data: '{"blood_group":"O+"}',
          consentVersion: SafetyRules.medicalConsentVersion,
          consentAt: DateTime(2026),
          updatedAt: DateTime(2026),
        ),
      );
      expect(medicalOf(await db.medical())?.bloodGroup, 'O+');
      final version = await db.customSelect('PRAGMA user_version').getSingle();
      expect(version.data.values.single, 2);
    },
  );
}
