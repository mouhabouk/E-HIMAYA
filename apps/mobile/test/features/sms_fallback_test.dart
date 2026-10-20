import 'dart:convert';

import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/features/report/sms_fallback.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const uuid = '3F2A9C1D-7b4e-4c1a-9d2e-0123456789ab';

  String body({
    ReportCategory category = ReportCategory.fire,
    double lat = 36.8065,
    double lon = 10.1815,
    double? acc = 11.2,
    String clientUuid = uuid,
  }) => smsReportBody(
    category: category,
    location: GeoPoint(lat: lat, lon: lon, accuracyM: acc),
    clientUuid: clientUuid,
  );

  group('smsReportBody (FR-A-048)', () {
    test('exact compact format', () {
      expect(body(), 'EH1 fire 36.80650,10.18150 12m 3f2a9c1d');
    });

    test('category wire names, 5 decimals, rounding', () {
      expect(
        body(
          category: ReportCategory.trafficAccident,
          lat: 33.123456789,
          lon: 9.000004,
          acc: 3,
        ),
        'EH1 traffic_accident 33.12346,9.00000 3m 3f2a9c1d',
      );
      expect(
        body(category: ReportCategory.sos, acc: 0.2),
        'EH1 sos 36.80650,10.18150 1m 3f2a9c1d',
      );
    });

    test('accuracy: unknown is 0, huge is clamped', () {
      expect(body(acc: null), endsWith(' 0m 3f2a9c1d'));
      expect(body(acc: double.nan), endsWith(' 0m 3f2a9c1d'));
      expect(body(acc: -4), endsWith(' 0m 3f2a9c1d'));
      expect(body(acc: 250000), endsWith(' 99999m 3f2a9c1d'));
    });

    test('ASCII only, single spaces, matches the gateway grammar', () {
      final grammar = RegExp(
        r'^EH1 [a-z_]+ -?\d{1,3}\.\d{5},-?\d{1,3}\.\d{5} \d{1,5}m [0-9a-f]{8}$',
      );
      for (final c in ReportCategory.values) {
        final b = body(category: c);
        expect(grammar.hasMatch(b), isTrue, reason: b);
        expect(b.codeUnits.every((u) => u >= 0x20 && u < 0x7f), isTrue);
        expect(b.contains('  '), isFalse);
      }
    });

    test('rejects a client_uuid that is not hex', () {
      expect(() => body(clientUuid: 'u1'), throwsArgumentError);
      expect(() => body(clientUuid: 'zzzzzzzz-1111'), throwsArgumentError);
    });
  });

  group('SMS number and URI', () {
    test('only well-formed numbers are kept', () {
      expect(normalizeSmsNumber(''), isNull);
      expect(normalizeSmsNumber('abc'), isNull);
      expect(normalizeSmsNumber('12'), isNull);
      expect(normalizeSmsNumber('+216 71 000 000'), '+21671000000');
      expect(normalizeSmsNumber('85-198'), '85198');
    });

    test('body is percent-encoded (no "+" for spaces)', () {
      final uri = smsUri('+21671000000', 'EH1 fire 36.80650,10.18150 12m ab');
      expect(uri.scheme, 'sms');
      expect(uri.path, '+21671000000');
      expect(uri.query, 'body=EH1%20fire%2036.80650%2C10.18150%2012m%20ab');
      expect(uri.queryParameters['body'], 'EH1 fire 36.80650,10.18150 12m ab');
    });
  });

  test('smsBodyForRow reads the frozen payload of a queued report', () {
    final now = DateTime.utc(2026, 10, 20);
    PendingReport row(Object? location, {String category = 'flood'}) =>
        PendingReport(
          clientUuid: uuid.toLowerCase(),
          category: category,
          payload: jsonEncode({'client_uuid': uuid, 'location': location}),
          tempCode: 'TMP-ABCDEF',
          state: ReportState.queued,
          attempts: 0,
          createdAt: now,
          updatedAt: now,
        );
    expect(
      smsBodyForRow(row({'lat': 35.5, 'lon': 11.04, 'accuracy_m': 30})),
      'EH1 flood 35.50000,11.04000 30m 3f2a9c1d',
    );
    expect(smsBodyForRow(row(null)), isNull);
    expect(
      smsBodyForRow(row({'lat': 35.5, 'lon': 11.04}, category: 'nope')),
      isNull,
    );
  });
}
