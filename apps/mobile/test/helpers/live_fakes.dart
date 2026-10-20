import 'dart:async';

import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/features/live/live_policies.dart';
import 'package:ehimaya/features/live/live_publisher.dart';
import 'package:flutter/material.dart';

import 'fake_http.dart';

Map<String, Object?> grantJson(
  String id, {
  bool simulated = false,
  int maxDurationS = 900,
  int locationIntervalS = 10,
}) => {
  'stream_id': id,
  'path': 'live/$id',
  'whip_url': 'https://media.test/live/$id/whip',
  'publish_token': 'tok-$id',
  'expires_at': '2026-10-19T10:25:00Z',
  'max_duration_s': maxDurationS,
  'location_interval_s': locationIntervalS,
  'simulated': simulated,
};

Map<String, Object?> streamInfoJson(
  String id, {
  String status = 'live',
  String? reason,
}) => {
  'stream_id': id,
  'status': status,
  'started_at': '2026-10-19T10:15:00Z',
  'ended_at': status == 'live' || status == 'pending'
      ? null
      : '2026-10-19T10:20:00Z',
  'end_reason': reason,
};

const sdpOffer = 'v=0\r\na=ice-ufrag:uf\r\na=ice-pwd:pw\r\na=mid:0\r\n';
const sdpAnswer = 'v=0\r\no=- 1 1 IN IP4 10.0.0.1\r\n';

/// API + tusd + MediaMTX (WHIP) in one fake, as the contract describes them.
class FakeLiveServer {
  int reportsCreated = 0;
  int streamsCreated = 0;
  final created = <String>[];
  final stops = <String>[];
  final locations = <String, List<Object?>>{};
  final whipPosts = <SeenRequest>[];
  final whipDeletes = <Uri>[];

  /// Next answers of `POST …/streams` (when empty: a new grant).
  final startErrors = <FakeResponse>[];

  /// Next answers of the WHIP POST (when empty: 201 with an answer).
  final whipErrors = <FakeResponse>[];

  /// Status answered by `GET /streams/{id}`, per stream (default `live`).
  final status = <String, Map<String, Object?>>{};
  bool reportsOffline = false;
  bool simulated = false;
  int maxDurationS = 900;
  int locationIntervalS = 10;

  FakeResponse handle(SeenRequest r) {
    final path = r.path;
    if (r.uri.host == 'media.test') return _whip(r);
    if (path == '/api/v1/reports' && r.method == 'POST') {
      if (reportsOffline) return const FakeResponse.network();
      reportsCreated++;
      final body = r.json! as Map;
      return FakeResponse(
        201,
        json: {
          'id': 'rep-$reportsCreated',
          'tracking_code': 'EH-26-11-000000$reportsCreated',
          'client_uuid': body['client_uuid'],
          'category': body['category'],
          'status': 'received',
          'location': body['location'],
          'media': const [],
        },
      );
    }
    if (path == '/api/v1/reports/mine') {
      return const FakeResponse(200, json: {'items': [], 'next_before': null});
    }
    if (path == '/api/v1/consents') return const FakeResponse(201);
    final start = RegExp(r'^/api/v1/reports/([^/]+)/streams$').firstMatch(path);
    if (start != null && r.method == 'POST') {
      if (startErrors.isNotEmpty) return startErrors.removeAt(0);
      final id = 'st-${++streamsCreated}';
      created.add(id);
      return FakeResponse(
        201,
        json: grantJson(
          id,
          simulated: simulated,
          maxDurationS: maxDurationS,
          locationIntervalS: locationIntervalS,
        ),
      );
    }
    final m = RegExp(r'^/api/v1/streams/([^/]+)(/(location|stop))?$')
        .firstMatch(path);
    if (m != null) {
      final id = m.group(1)!;
      switch (m.group(3)) {
        case 'location':
          final current = status[id]?['status'] as String? ?? 'live';
          if (current != 'live' && current != 'pending') {
            return const FakeResponse(
              409,
              json: {'detail': 'stream_not_active'},
            );
          }
          (locations[id] ??= []).add(r.json);
          return const FakeResponse(204);
        case 'stop':
          stops.add(id);
          status[id] ??= streamInfoJson(
            id,
            status: 'ended',
            reason: 'publisher_stopped',
          );
          return FakeResponse(200, json: status[id]);
        default:
          return FakeResponse(200, json: status[id] ?? streamInfoJson(id));
      }
    }
    return const FakeResponse(404, json: {'detail': 'not_found'});
  }

  FakeResponse _whip(SeenRequest r) {
    switch (r.method) {
      case 'POST':
        whipPosts.add(r);
        if (whipErrors.isNotEmpty) return whipErrors.removeAt(0);
        return FakeResponse(
          201,
          text: sdpAnswer,
          headers: {'Location': '${r.uri.path}/session-${whipPosts.length}'},
        );
      case 'DELETE':
        whipDeletes.add(r.uri);
        return const FakeResponse(200);
      default:
        return const FakeResponse(405);
    }
  }

  /// The operator ends [id] from the dashboard.
  void operatorStops(String id) =>
      status[id] = streamInfoJson(id, status: 'ended', reason: 'staff_stopped');
}

/// Camera and peer connection stand-in.
class FakeLivePublisher implements LivePublisher {
  FakeLivePublisher({this.autoConnect = true});

  /// Connected right after the answer is applied.
  bool autoConnect;
  Object? openError;
  bool opened = false;
  bool disposed = false;
  int offers = 0;
  int connectionsClosed = 0;
  final answers = <String>[];
  final qualities = <LiveQuality>[];
  bool muted = false;
  bool front = false;
  LiveNetworkSample? nextSample;
  final _connection = StreamController<PublisherConnection>.broadcast();
  final _late = StreamController<String>.broadcast();

  void emit(PublisherConnection c) => _connection.add(c);

  @override
  Stream<PublisherConnection> get connection => _connection.stream;

  @override
  Stream<String> get lateCandidates => _late.stream;

  @override
  Future<void> openMedia({required bool frontCamera}) async {
    final error = openError;
    if (error != null) throw error;
    opened = true;
    front = frontCamera;
  }

  @override
  Future<String> createOffer({
    required LiveQuality quality,
    Duration gatherFor = const Duration(seconds: 3),
  }) async {
    offers++;
    qualities.add(quality);
    return sdpOffer;
  }

  @override
  Future<void> applyAnswer(String sdp) async {
    answers.add(sdp);
    if (autoConnect) {
      scheduleMicrotask(() => emit(PublisherConnection.connected));
    }
  }

  @override
  Future<void> setQuality(LiveQuality quality) async => qualities.add(quality);

  @override
  Future<LiveNetworkSample?> sample() async => nextSample;

  @override
  Future<bool> switchCamera() async => front = !front;

  @override
  Future<void> setMuted(bool muted) async => this.muted = muted;

  @override
  Future<void> closeConnection() async => connectionsClosed++;

  @override
  Future<void> dispose() async {
    disposed = true;
    unawaited(_connection.close());
    unawaited(_late.close());
  }

  @override
  Widget preview(BuildContext context) =>
      const ColoredBox(key: Key('fake-preview'), color: Colors.black);
}

/// Position source for the live tests: a fixed point, or none.
class LiveFakeLocation extends LocationService {
  LiveFakeLocation({
    this.point = const GeoPoint(lat: 36.8, lon: 10.18, accuracyM: 8),
  });

  GeoPoint? point;
  LocationAvailability availability = LocationAvailability.granted;
  int fixes = 0;

  @override
  Future<LocationAvailability> ensurePermission() async => availability;

  @override
  Future<GeoPoint?> current({Duration timeout = Duration.zero}) async {
    fixes++;
    return point;
  }

  @override
  Future<GeoPoint?> lastKnown() async => point;
}
