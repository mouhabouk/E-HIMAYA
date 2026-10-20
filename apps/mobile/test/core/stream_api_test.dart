import 'package:dio/dio.dart';
import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/http/stream_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/live_fakes.dart';

void main() {
  late FakeAdapter adapter;
  late EHimayaApi api;

  setUp(() {
    adapter = FakeAdapter((_) => const FakeResponse(500));
    api = EHimayaApi(
      Dio(BaseOptions(baseUrl: 'http://api.test'))..httpClientAdapter = adapter,
    );
  });

  test('POST /reports/{id}/streams parses the grant', () async {
    adapter.handler = (r) => FakeResponse(201, json: grantJson('st-1'));
    final grant = await api.startStream('rep-1');
    expect(adapter.requests.single.method, 'POST');
    expect(adapter.requests.single.path, '/api/v1/reports/rep-1/streams');
    expect(grant.streamId, 'st-1');
    expect(grant.path, 'live/st-1');
    expect(grant.whipUrl, Uri.parse('https://media.test/live/st-1/whip'));
    expect(grant.publishToken, 'tok-st-1');
    expect(grant.maxDuration, const Duration(seconds: 900));
    expect(grant.locationInterval, const Duration(seconds: 10));
    expect(grant.simulated, isFalse);
    expect(grant.expiresAt, isNotNull);
  });

  test('simulated and missing cadences fall back to the contract defaults', () {
    final grant = LiveStreamGrant.fromJson({
      ...grantJson('st-2', simulated: true),
      'max_duration_s': null,
      'location_interval_s': 0,
    });
    expect(grant.simulated, isTrue);
    expect(grant.maxDuration, LiveStreamGrant.defaultMaxDuration);
    expect(grant.locationInterval, LiveStreamGrant.defaultLocationInterval);
  });

  test('409 stream_already_active and report_closed are typed', () async {
    adapter.handler = (r) =>
        const FakeResponse(409, json: {'detail': 'stream_already_active'});
    await expectLater(
      api.startStream('rep-1'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          ApiErrorCode.streamAlreadyActive,
        ),
      ),
    );
    adapter.handler = (r) =>
        const FakeResponse(409, json: {'detail': 'report_closed'});
    await expectLater(
      api.startStream('rep-1'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          ApiErrorCode.reportClosed,
        ),
      ),
    );
  });

  test('location body, stop and status', () async {
    adapter.handler = (r) => switch (r.path) {
      '/api/v1/streams/st-1/location' => const FakeResponse(204),
      '/api/v1/streams/st-1/stop' => FakeResponse(
        200,
        json: streamInfoJson(
          'st-1',
          status: 'ended',
          reason: 'publisher_stopped',
        ),
      ),
      _ => FakeResponse(
        200,
        json: streamInfoJson('st-1', status: 'ended', reason: 'staff_stopped'),
      ),
    };
    await api.postStreamLocation(
      'st-1',
      const GeoPoint(lat: 36.8, lon: 10.18, accuracyM: 12),
    );
    expect(adapter.requests.last.json, {
      'lat': 36.8,
      'lon': 10.18,
      'accuracy_m': 12.0,
    });
    final stopped = await api.stopStream('st-1');
    expect(stopped?.endReason, LiveEndReasonWire.publisherStopped);
    final info = await api.getStream('st-1');
    expect(adapter.requests.last.method, 'GET');
    expect(info.status, LiveStreamStatus.ended);
    expect(info.status!.isActive, isFalse);
    expect(info.endReason, LiveEndReasonWire.staffStopped);
  });

  test('409 stream_not_active on a late position', () async {
    adapter.handler = (r) =>
        const FakeResponse(409, json: {'detail': 'stream_not_active'});
    await expectLater(
      api.postStreamLocation('st-1', const GeoPoint(lat: 36.8, lon: 10.1)),
      throwsA(
        isA<ApiException>().having(
          (e) => e.code,
          'code',
          ApiErrorCode.streamNotActive,
        ),
      ),
    );
  });
}
