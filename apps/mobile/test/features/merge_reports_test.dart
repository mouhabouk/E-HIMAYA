import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/features/reports/reports_providers.dart';
import 'package:flutter_test/flutter_test.dart';

PendingReport local(String uuid, {String? code, String state = 'queued'}) =>
    PendingReport(
      clientUuid: uuid,
      category: 'fire',
      payload: '{}',
      tempCode: 'TMP-AAAAAA',
      serverTrackingCode: code,
      state: state,
      attempts: 0,
      createdAt: DateTime.utc(2026, 10, 19, 10),
      updatedAt: DateTime.utc(2026, 10, 19, 10),
    );

ServerReport server(String id, String uuid, String status) =>
    ServerReport.fromJson({
      'id': id,
      'tracking_code': 'EH-26-61-000000$id',
      'client_uuid': uuid,
      'category': 'flood',
      'status': status,
      'created_at': '2026-10-18T10:00:00Z',
      'media': [],
    });

void main() {
  test('local rows show the temp code until the server code is known', () {
    final items = mergeReports(local: [local('u1')], media: [], server: []);
    expect(items.single.trackingCode, 'TMP-AAAAAA');
    expect(items.single.isTemporary, isTrue);
    expect(items.single.status, isNull);
  });

  test('server wins for status and tracking code; server-only rows listed', () {
    final items = mergeReports(
      local: [local('u1', code: 'EH-26-61-0000001', state: 'synced')],
      media: [],
      server: [server('1', 'u1', 'in_progress'), server('2', 'u2', 'closed')],
    );
    expect(items, hasLength(2));
    final first = items.firstWhere((i) => i.clientUuid == 'u1');
    expect(first.status, ReportStatus.inProgress);
    expect(first.trackingCode, 'EH-26-61-0000001');
    expect(first.isTemporary, isFalse);
    expect(items.any((i) => i.status == ReportStatus.closed), isTrue);
  });
}
