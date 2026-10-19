import 'package:dio/dio.dart';
import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/org_fixtures.dart';

void main() {
  test('GET /orgs/mine rows', () {
    final org = MyOrg.fromJson({
      'id': orgId,
      'name': 'Société X',
      'kind': 'industrial',
      'status': 'active',
      'my_role': 'member',
      'alerts_count': 3,
    });
    expect(org.isActive, isTrue);
    expect(org.myRole, 'member');
    expect(org.alertsCount, 3);
    // Round trip through the offline cache.
    final again = MyOrg.fromJson(org.toJson());
    expect(again.id, orgId);
    expect(again.name, 'Société X');
    expect(again.status, 'active');
    expect(
      MyOrg.fromJson({
        'id': 'x',
        'name': 'Y',
        'kind': 'hotel',
        'status': 'pending_review',
      }).isActive,
      isFalse,
    );
  });

  test('statuses and kinds of the contract', () {
    expect(OrgStatus.values.map((s) => s.wire).toList(), [
      'pending_review',
      'active',
      'rejected',
      'suspended',
    ]);
    expect(OrgKind.values.map((k) => k.wire).toList(), [
      'industrial',
      'educational',
      'hotel',
      'government',
      'private',
      'other',
    ]);
    expect(OrgStatus.fromWire('pending_review'), OrgStatus.pendingReview);
    expect(OrgKind.fromWire('nope'), isNull);
  });

  test('GET /orgs/{id}/summary', () {
    final s = OrgSummary.fromJson(summaryJson());
    expect(s.name, 'Société X');
    expect(s.kind, 'industrial');
    expect(s.capacity, 420);
    expect(s.location!.lat, 34.70);
    expect(s.classification!.family, 'industrial');
    expect(s.classification!.category, isNull);
    expect(s.classification!.provisional, isTrue);
    expect(s.team, hasLength(2));
    expect(s.team.first.teamRole, 'representative');
    expect(s.team.first.phone, '+21698123456');
    expect(s.team.last.phone, isNull);
    expect(s.team.last.trainingStatus, 'expired');
    expect(s.hazmatCount, 1);
    expect(s.hazmat.single.unNumber, '1090');
    expect(s.hazmat.single.quantity, 2.5);
    expect(s.hazmat.single.unit, 't');
    expect(s.alertsCount, 2);
    expect(OrgSummary.fromJson(s.source).name, 'Société X');
  });

  test('erp classification has a category', () {
    final c = OrgClassification.fromJson({'family': 'erp', 'category': 3});
    expect(c!.category, 3);
    expect(OrgClassification.fromJson(null), isNull);
  });

  test('Report.organization (null when sent by the user)', () {
    final base = {
      'id': 'r1',
      'tracking_code': 'EH-26-61-0004821',
      'client_uuid': 'u1',
      'category': 'fire',
      'status': 'received',
      'media': <Object?>[],
    };
    final mine = ServerReport.fromJson({...base, 'organization': null});
    expect(mine.organization, isNull);
    final forOrg = ServerReport.fromJson({
      ...base,
      'organization': {'id': orgId, 'name': 'Société X'},
    });
    expect(forOrg.organization!.id, orgId);
    expect(forOrg.organization!.name, 'Société X');
    // Older servers without the field.
    expect(ServerReport.fromJson(base).organization, isNull);
  });

  test('org_not_found / org_not_active are not mistaken for other codes', () {
    final h = Headers();
    final notFound = ApiException.fromResponse(404, {
      'detail': 'org_not_found',
    }, h);
    expect(notFound.code, ApiErrorCode.orgNotFound);
    expect(notFound.isTransient, isFalse);
    final notActive = ApiException.fromResponse(409, {
      'detail': 'org_not_active',
    }, h);
    // A bare 409 means client_uuid_conflict: this one must not.
    expect(notActive.code, ApiErrorCode.orgNotActive);
    expect(
      ApiException.fromResponse(403, {'detail': 'org_role_required'}, h).code,
      ApiErrorCode.orgRoleRequired,
    );
  });

  test('API calls: paths, query and parsing', () async {
    final adapter = FakeAdapter((r) {
      switch (r.path) {
        case '/api/v1/orgs/mine':
          return const FakeResponse(
            200,
            json: [
              {
                'id': orgId,
                'name': 'Société X',
                'kind': 'industrial',
                'status': 'active',
                'my_role': 'admin',
                'alerts_count': 0,
              },
            ],
          );
        case '/api/v1/orgs/$orgId/summary':
          return FakeResponse(200, json: summaryJson());
        case '/api/v1/orgs/$orgId/reports':
          return const FakeResponse(
            200,
            json: {
              'items': [
                {
                  'id': 'r1',
                  'tracking_code': 'EH-26-61-0004821',
                  'category': 'chemical_leak',
                  'status': 'in_progress',
                  'text': 'Fuite',
                  'received_at': '2026-10-19T10:15:02Z',
                  'updated_at': '2026-10-19T10:20:00Z',
                  'reporter_display_name': 'amel',
                },
              ],
              'next_cursor': 'abc',
            },
          );
      }
      return const FakeResponse(404, json: {'detail': 'org_not_found'});
    });
    final api = EHimayaApi(
      Dio(BaseOptions(baseUrl: 'http://api.test'))..httpClientAdapter = adapter,
    );
    final mine = await api.myOrgs();
    expect(mine.single.myRole, 'admin');
    final summary = await api.orgSummary(orgId);
    expect(summary.team, hasLength(2));
    final page = await api.orgReports(orgId, cursor: 'c1');
    expect(page.items.single.trackingCode, 'EH-26-61-0004821');
    expect(page.items.single.status, 'in_progress');
    expect(page.items.single.reporterDisplayName, 'amel');
    expect(page.items.single.receivedAt, DateTime.utc(2026, 10, 19, 10, 15, 2));
    expect(page.nextCursor, 'abc');
    expect(adapter.requests.last.uri.queryParameters, {
      'limit': '50',
      'cursor': 'c1',
    });
    await expectLater(
      api.orgSummary('other'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          ApiErrorCode.orgNotFound,
        ),
      ),
    );
  });
}
