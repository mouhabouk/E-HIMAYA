import 'package:ehimaya/core/push/push_dedup.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_notifications.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:flutter_test/flutter_test.dart';

PushPayload _p(Map<String, String> data) => PushPayload.parse(data)!;

void main() {
  final t0 = DateTime.utc(2026, 10, 19, 10);

  test('subject = the server tag / apns-collapse-id "<type>:<id>"', () {
    expect(
      pushSubject(_p({'type': 'alert', 'id': 'a1', 'severity': 'high'})),
      'alert:a1',
    );
    expect(
      pushSubject(_p({'type': 'alert_cancelled', 'id': 'a1'})),
      'alert_cancelled:a1',
    );
    expect(
      pushSubject(_p({'type': 'callout', 'callout_id': 'c1'})),
      'callout:c1',
    );
    expect(
      pushSubject(
        _p({
          'type': 'report_status',
          'report_id': 'r1',
          'tracking_code': 'EH-1',
          'redacted': '1',
        }),
      ),
      'report_status:r1',
    );
    expect(pushSubject(_p({'type': 'info', 'id': 'n1'})), 'info:n1');
  });

  test('ids are stable, positive 31-bit, and differ per subject', () {
    final a = _p({'type': 'callout', 'callout_id': 'c1'});
    final b = _p({'type': 'callout', 'callout_id': 'c2'});
    expect(notificationIdFor(a), notificationIdFor(a));
    expect(notificationIdFor(a), isNot(notificationIdFor(b)));
    for (final p in [a, b]) {
      expect(notificationIdFor(p), inInclusiveRange(0, 0x7fffffff));
    }
    // FNV-1a of "callout:c1" (pinned: must not change between releases).
    expect(notificationIdFor(a), 0x5cad4f5b);
  });

  test('report status: a new status is a new event of the same subject', () {
    final received = _p({
      'type': 'report_status',
      'report_id': 'r1',
      'status': 'received',
    });
    final closed = _p({
      'type': 'report_status',
      'report_id': 'r1',
      'status': 'closed',
    });
    expect(notificationIdFor(received), notificationIdFor(closed));
    expect(pushEventKey(received), isNot(pushEventKey(closed)));
  });

  group('PushDeduper', () {
    test('a repeated push within the window does not ring again', () {
      final d = PushDeduper();
      final p = _p({'type': 'alert', 'id': 'a1', 'severity': 'medium'});
      expect(d.firstTime(p, t0), isTrue);
      expect(d.firstTime(p, t0.add(const Duration(minutes: 5))), isFalse);
      // Upgraded severity is news.
      expect(
        d.firstTime(
          _p({'type': 'alert', 'id': 'a1', 'severity': 'high'}),
          t0.add(const Duration(minutes: 6)),
        ),
        isTrue,
      );
    });

    test('forgets after the window', () {
      final d = PushDeduper(window: const Duration(minutes: 30));
      final p = _p({'type': 'info', 'id': 'n1'});
      expect(d.firstTime(p, t0), isTrue);
      expect(d.firstTime(p, t0.add(const Duration(minutes: 30))), isTrue);
    });

    test('bounded memory: oldest entries are dropped', () {
      final d = PushDeduper(capacity: 2);
      final a = _p({'type': 'info', 'id': 'a'});
      final b = _p({'type': 'info', 'id': 'b'});
      final c = _p({'type': 'info', 'id': 'c'});
      expect(d.firstTime(a, t0), isTrue);
      expect(d.firstTime(b, t0), isTrue);
      expect(d.firstTime(c, t0), isTrue);
      expect(d.firstTime(a, t0), isTrue, reason: 'a was evicted');
      expect(d.firstTime(c, t0), isFalse);
    });
  });

  group('pushChannelFor (versioned channels)', () {
    final alert = _p({'type': 'alert', 'id': 'a1', 'severity': 'medium'});
    final severe = _p({'type': 'alert', 'id': 'a2', 'severity': 'high'});
    final info = _p({'type': 'info', 'id': 'n1'});

    test('the legacy alerts id maps to the current versioned channel', () {
      expect(alertChannelId, isNot('ehimaya_alerts'));
      expect(pushChannelFor(alert, 'ehimaya_alerts'), alertChannelId);
      expect(pushChannelFor(alert, alertChannelId), alertChannelId);
      expect(pushChannelFor(info, defaultChannelId), defaultChannelId);
      expect(pushChannelFor(info, 'bogus'), defaultChannelId);
      expect(pushChannelFor(alert), alertChannelId);
    });

    test('severe alerts use the DND channel only after the opt-in', () {
      expect(pushChannelFor(severe, 'ehimaya_alerts'), alertChannelId);
      expect(pushChannelFor(severe, 'ehimaya_alerts', true), criticalChannelId);
      expect(pushChannelFor(alert, criticalChannelId), alertChannelId);
      expect(pushChannelFor(alert, criticalChannelId, true), criticalChannelId);
      expect(pushChannelFor(alert, null, true), alertChannelId);
    });
  });

  test('payload flags: severe, redacted', () {
    expect(_p({'type': 'alert', 'severity': 'high'}).severe, isTrue);
    expect(_p({'type': 'alert', 'severity': 'medium'}).severe, isFalse);
    expect(_p({'type': 'callout', 'redacted': '1'}).redacted, isTrue);
    expect(_p({'type': 'callout'}).redacted, isFalse);
  });
}
