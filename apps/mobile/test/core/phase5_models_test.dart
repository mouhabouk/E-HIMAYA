import 'dart:convert';
import 'dart:io';

import 'package:ehimaya/core/http/notify_models.dart';
import 'package:ehimaya/core/http/volunteer_models.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/phase5_fixtures.dart';

void main() {
  group('volunteer', () {
    test('parses the application and readiness', () {
      final v = Volunteer.fromJson(
        volunteerJson(ready: true, readyUntil: '2026-10-19T18:00:00Z'),
      );
      expect(v.status, VolunteerStatus.approved);
      expect(v.skills, [VolunteerSkill.firstAid, VolunteerSkill.diving]);
      expect(v.isReadyAt(DateTime.utc(2026, 10, 19, 17)), isTrue);
      expect(v.isReadyAt(DateTime.utc(2026, 10, 19, 18, 1)), isFalse);
      expect(v.version, 2);
    });

    test('period bounds are whole local days', () {
      final v = Volunteer.fromJson(
        volunteerJson(periodFrom: '2026-10-10', periodTo: '2026-10-20'),
      );
      expect(v.inPeriod(DateTime(2026, 10, 9, 23, 59)), isFalse);
      expect(v.inPeriod(DateTime(2026, 10, 10)), isTrue);
      expect(v.inPeriod(DateTime(2026, 10, 20, 23, 59)), isTrue);
      expect(v.inPeriod(DateTime(2026, 10, 21)), isFalse);
      final open = Volunteer.fromJson(volunteerJson(periodFrom: '2026-10-10'));
      expect(open.inPeriod(DateTime(2030)), isTrue);
    });

    test('input keeps the contract order and drops empty texts', () {
      final json = VolunteerInput(
        skills: {VolunteerSkill.medical, VolunteerSkill.firstAid},
        availability: VolunteerAvailability.intermittent,
        periodFrom: DateTime(2026, 11, 2),
        otherSkill: 'ignored without the other skill',
        notes: '  ',
        version: 3,
      ).toJson();
      expect(json, {
        'skills': ['first_aid', 'medical'],
        'other_skill': null,
        'availability': 'intermittent',
        'period_from': '2026-11-02',
        'period_to': null,
        'notes': null,
        'version': 3,
      });
      final other = VolunteerInput(
        skills: {VolunteerSkill.other},
        availability: VolunteerAvailability.continuous,
        periodFrom: DateTime(2026, 11, 2),
        periodTo: DateTime(2027, 1, 31),
        otherSkill: ' Langue des signes ',
      ).toJson();
      expect(other['other_skill'], 'Langue des signes');
      expect(other['period_to'], '2027-01-31');
      expect(other.containsKey('version'), isFalse);
    });

    test('call-out actions depend on both statuses', () {
      final sent = MyCallout.fromJson(calloutJson());
      expect(sent.canRespond, isTrue);
      expect(sent.canArrive, isFalse);
      expect(sent.distanceM, 2350);
      expect(sent.skill, VolunteerSkill.firefighting);
      final accepted = MyCallout.fromJson(
        calloutJson(status: 'filled', myStatus: 'accepted', eta: 12),
      );
      expect(accepted.canRespond, isFalse);
      expect(accepted.canArrive, isTrue);
      final cancelled = MyCallout.fromJson(
        calloutJson(status: 'cancelled', myStatus: 'accepted'),
      );
      expect(cancelled.canArrive, isFalse);
    });
  });

  group('alerts and inbox', () {
    test('empty translations fall back to Arabic', () {
      final a = ActiveAlert.fromJson(alertJson());
      expect(a.title.of('fr'), 'Alerte pluies abondantes');
      expect(a.title.of('en'), 'تنبيه أمطار غزيرة');
      expect(a.severity, AlertSeverity.high);
      expect(a.hazard, AlertHazard.heavyRain);
      expect(a.gouvernoratCodes, [61]);
      expect(a.isNational, isFalse);
      expect(a.source['id'], a.id);
    });

    test('national and polygon areas', () {
      expect(ActiveAlert.fromJson(alertJson(codes: [])).isNational, isTrue);
      final zone = ActiveAlert.fromJson({
        ...alertJson(),
        'area': {
          'gouvernorat_codes': <int>[],
          'polygon': {'type': 'Polygon', 'coordinates': []},
        },
      });
      expect(zone.hasPolygon, isTrue);
      expect(zone.isNational, isFalse);
    });

    test('inbox items: information and alerts', () {
      final info = InboxItem.fromJson(inboxItemJson('i1'));
      expect(info.isAlert, isFalse);
      expect(info.topic, NotificationTopic.awareness);
      expect(info.severity, isNull);
      final alert = InboxItem.fromJson(inboxItemJson('i2', kind: 'alert'));
      expect(alert.isAlert, isTrue);
      expect(alert.severity, AlertSeverity.medium);
    });
  });

  group('safety tips', () {
    test('API shape, sorted by position, language fallback', () {
      final tips = SafetyTips.fromJson(tipsJson());
      expect(tips.revision, 3);
      expect(tips.items.map((t) => t.hazard), [
        TipHazard.fire,
        TipHazard.flood,
      ]);
      final flood = tips.items[1];
      expect(flood.textFor('fr').title, 'Inondation');
      expect(flood.textFor('en').title, 'فيضان');
      expect(tips.items[0].textFor('fr').doItems, ['اتصل بالرقم 198']);
    });

    test('the bundled copy is the server seed and is complete', () {
      final raw = File('assets/safety_tips.json').readAsStringSync();
      expect(
        raw,
        File('../../services/api/seed/safety_tips.json').readAsStringSync(),
      );
      final tips = SafetyTips.fromJson(jsonDecode(raw));
      expect(tips.revision, 0);
      expect(tips.items, hasLength(greaterThanOrEqualTo(9)));
      for (final tip in tips.items) {
        for (final lang in ['ar', 'fr', 'en']) {
          final text = tip.content[lang]!;
          expect(text.title, isNotEmpty, reason: '${tip.hazard} $lang');
          expect(text.doItems, isNotEmpty, reason: '${tip.hazard} $lang');
        }
      }
    });
  });

  group('push payloads', () {
    test('route of each kind', () {
      PushPayload p(Map<String, Object?> data) => PushPayload.parse(data)!;
      expect(
        p({'type': 'alert', 'id': 'a1', 'severity': 'high'}).route,
        Routes.alert('a1'),
      );
      expect(p({'type': 'alert'}).route, Routes.notifications);
      expect(
        p({'type': 'alert_cancelled', 'id': 'a1'}).route,
        Routes.notifications,
      );
      expect(p({'type': 'info', 'id': 'm1'}).route, Routes.notifications);
      expect(p({'type': 'callout', 'callout_id': 'c1'}).route, Routes.callouts);
      expect(
        p({
          'type': 'report_status',
          'tracking_code': 'EH-ABC234',
          'status': 'closed',
        }).route,
        Routes.reports,
      );
    });

    test('unknown or malformed payloads are ignored', () {
      expect(PushPayload.parse({'type': 'marketing'}), isNull);
      expect(PushPayload.parse({}), isNull);
      final p = PushPayload.parse({'type': 'callout', 'n': 3, 'x': null})!;
      expect(p.data, {'type': 'callout', 'n': '3'});
      expect(p.kind.urgent, isTrue);
      expect(PushKind.info.urgent, isFalse);
    });
  });
}
