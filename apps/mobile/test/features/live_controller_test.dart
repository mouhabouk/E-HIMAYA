import 'dart:io';

import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/location/location_service.dart';
import 'package:ehimaya/core/power/high_power.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/security/locked_alert.dart';
import 'package:ehimaya/core/sync/sync_engine.dart';
import 'package:ehimaya/features/live/live_controller.dart';
import 'package:ehimaya/features/live/live_policies.dart';
import 'package:ehimaya/features/live/live_publisher.dart';
import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/live_rig.dart';

final _t0 = DateTime.utc(2026, 10, 19, 10, 15);

/// Runs [body] in fake time with a fresh rig.
void liveTest(
  String name,
  void Function(FakeAsync async, LiveRig rig) body, {
  bool locked = false,
  bool batterySaver = false,
  NetworkKind network = NetworkKind.unmetered,
  void Function(LiveRig rig)? setUp,
}) {
  test(name, () {
    fakeAsync((async) {
      final rig = LiveRig(
        clock: () => _t0.add(async.elapsed),
        locked: locked,
        batterySaver: batterySaver,
        network: network,
      );
      setUp?.call(rig);
      body(async, rig);
      // Whatever the test left running is stopped, then everything is released.
      rig.controller.stop();
      async.elapse(const Duration(seconds: 10));
      rig.dispose();
      async.flushMicrotasks();
      async.elapse(const Duration(seconds: 1));
    });
  });
}

const existing = LiveTarget.existing(
  clientUuid: 'c-1',
  serverId: 'rep-9',
  trackingCode: 'EH-26-11-0000009',
  category: ReportCategory.fire,
);

bool _highPower(LiveRig rig) => rig.container.read(highPowerActiveProvider);

void main() {
  group('start', () {
    liveTest('new report: queued, sent, stream opened, WHIP published, live', (
      async,
      rig,
    ) {
      rig.controller.start(
        const LiveTarget.newReport(category: ReportCategory.flood),
      );
      async.elapse(const Duration(milliseconds: 100));

      expect(rig.server.reportsCreated, 1);
      final reportBody =
          rig.requests('POST', r'/api/v1/reports$').single.json! as Map;
      expect(reportBody['category'], 'flood');
      expect(rig.requests('POST', r'/reports/rep-1/streams$'), hasLength(1));
      final whip = rig.server.whipPosts.single;
      expect(whip.uri.toString(), 'https://media.test/live/st-1/whip');
      expect(whip.header('Authorization'), 'Bearer tok-st-1');
      expect(whip.text, contains('a=ice-ufrag'));

      final s = rig.state;
      expect(s.phase, LivePhase.live);
      expect(s.streamId, 'st-1');
      expect(s.reportServerId, 'rep-1');
      expect(s.reportClientUuid, isNotNull);
      expect(s.trackingCode, startsWith('EH-'));
      expect(s.startedAt, isNotNull);
      expect(s.simulated, isFalse);
      // Back camera by default; screen kept on; high-power exception open.
      expect(rig.publisher.front, isFalse);
      expect(rig.device.screenOn, [true]);
      expect(_highPower(rig), isTrue);
    });

    liveTest('existing report: no new report, stream on its server id', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.server.reportsCreated, 0);
      expect(rig.requests('POST', r'/reports/rep-9/streams$'), hasLength(1));
      expect(rig.state.phase, LivePhase.live);
      expect(rig.state.trackingCode, 'EH-26-11-0000009');
    });

    liveTest('the simulated flag of the API is kept for the amber band', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.state.simulated, isTrue);
    }, setUp: (rig) => rig.server.simulated = true);

    liveTest('quality starts lower on mobile data', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.state.quality, LiveQuality.medium);
      expect(rig.publisher.qualities.first, LiveQuality.medium);
    }, network: NetworkKind.metered);
  });

  group('stop', () {
    liveTest('one tap: stop API + WHIP DELETE, camera released, power back', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 5));
      final publisher = rig.publisher;
      rig.controller.stop();
      async.elapse(const Duration(milliseconds: 100));

      expect(rig.server.stops, ['st-1']);
      expect(
        rig.server.whipDeletes.single.toString(),
        'https://media.test/live/st-1/whip/session-1',
      );
      expect(
        rig.adapter.requests
            .where((r) => r.method == 'DELETE')
            .single
            .header('Authorization'),
        'Bearer tok-st-1',
      );
      expect(publisher.disposed, isTrue);
      expect(rig.state.phase, LivePhase.ended);
      expect(rig.state.endReason, LiveEndReason.userStopped);
      expect(rig.state.endedAt!.difference(rig.state.startedAt!).inSeconds, 5);
      expect(rig.device.screenOn.last, isFalse);
      expect(_highPower(rig), isFalse);

      // Nothing keeps running after the stream: no more positions.
      final sent = rig.server.locations['st-1']!.length;
      async.elapse(const Duration(minutes: 1));
      expect(rig.server.locations['st-1']!.length, sent);
    });

    liveTest('stopping while still connecting frees the stream at once', (
      async,
      rig,
    ) {
      rig.autoConnect = false;
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.state.phase, LivePhase.connecting);
      rig.controller.stop();
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.server.stops, ['st-1']);
      expect(rig.state.endReason, LiveEndReason.userStopped);
    });

    liveTest('the operator ends the stream: seen by the status poll', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 3));
      rig.server.operatorStops('st-1');
      async.elapse(const Duration(seconds: 10));
      expect(rig.state.phase, LivePhase.ended);
      expect(rig.state.endReason, LiveEndReason.operatorStopped);
      // Already stopped by the server: no stop request from the app, the WHIP session is closed.
      expect(rig.server.stops, isEmpty);
      expect(rig.server.whipDeletes, hasLength(1));
      expect(rig.publishers.single.disposed, isTrue);
      expect(_highPower(rig), isFalse);
    });

    liveTest('max_duration_s ends the stream locally', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 29));
      expect(rig.state.phase, LivePhase.live);
      async.elapse(const Duration(seconds: 2));
      expect(rig.state.phase, LivePhase.ended);
      expect(rig.state.endReason, LiveEndReason.maxDuration);
      expect(rig.server.stops, ['st-1']);
    }, setUp: (rig) => rig.server.maxDurationS = 30);

    liveTest('the lock screen taking over stops the stream', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 2));
      rig.device.locked = true;
      rig.container.read(lockedAlertProvider.notifier).refresh();
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.state.phase, LivePhase.ended);
      expect(rig.state.endReason, LiveEndReason.locked);
      expect(rig.server.stops, ['st-1']);
    });
  });

  group('location', () {
    liveTest('sent at once, then every location_interval_s while live', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      expect(rig.server.locations['st-1'], hasLength(1));
      expect(rig.server.locations['st-1']!.first, {
        'lat': 36.8,
        'lon': 10.18,
        'accuracy_m': 8.0,
      });
      async.elapse(const Duration(seconds: 25));
      expect(rig.server.locations['st-1'], hasLength(3));
    });

    liveTest('the server cadence is floored at 3 s', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 10));
      // 0, 3, 6, 9 s.
      expect(rig.server.locations['st-1'], hasLength(4));
    }, setUp: (rig) => rig.server.locationIntervalS = 1);

    liveTest('location refused: the stream goes on without positions', (
      async,
      rig,
    ) {
      rig.location.availability = LocationAvailability.denied;
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 30));
      expect(rig.state.phase, LivePhase.live);
      expect(rig.state.locationShared, isFalse);
      expect(rig.server.locations, isEmpty);
    });

    liveTest('the high-power cadence ignores the battery saver', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 21));
      expect(rig.server.locations['st-1'], hasLength(3));
      // …but the quality is capped.
      expect(rig.state.quality, LiveQuality.medium);
    }, batterySaver: true);
  });

  group('network loss and fallback', () {
    liveTest('a dropped path reconnects with a new stream on the same report', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 5));
      final startedAt = rig.state.startedAt;
      rig.publisher.emit(PublisherConnection.failed);
      async.flushMicrotasks();
      expect(rig.state.phase, LivePhase.reconnecting);
      expect(rig.state.reconnectAttempt, 1);
      async.elapse(const Duration(seconds: 3));
      expect(rig.server.stops, ['st-1']);
      expect(rig.requests('POST', r'/reports/rep-9/streams$'), hasLength(2));
      expect(rig.server.whipPosts.last.uri.path, '/live/st-2/whip');
      expect(rig.state.phase, LivePhase.live);
      expect(rig.state.streamId, 'st-2');
      expect(rig.state.reconnectAttempt, 0);
      // Elapsed time counts from the first start; the camera was kept open.
      expect(rig.state.startedAt, startedAt);
      expect(rig.publishers, hasLength(1));
      async.elapse(const Duration(seconds: 10));
      expect(rig.server.locations['st-2'], isNotEmpty);
    });

    liveTest('a short "disconnected" that recovers does not reconnect', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 2));
      rig.publisher.emit(PublisherConnection.disconnected);
      async.elapse(const Duration(seconds: 3));
      rig.publisher.emit(PublisherConnection.connected);
      async.elapse(const Duration(seconds: 10));
      expect(rig.state.phase, LivePhase.live);
      expect(rig.server.streamsCreated, 1);
    });

    liveTest('reconnections exhausted → failed with the clip fallback', (
      async,
      rig,
    ) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 2));
      rig.server.whipErrors.addAll(const [
        FakeResponse.network(),
        FakeResponse.network(),
        FakeResponse.network(),
      ]);
      rig.publisher.emit(PublisherConnection.failed);
      async.elapse(const Duration(seconds: 30));
      expect(rig.state.phase, LivePhase.failed);
      expect(rig.state.failure, LiveFailure.connectionFailed);
      expect(rig.state.canFallback, isTrue);
      expect(rig.server.whipPosts, hasLength(4));
      expect(rig.publisher.disposed, isTrue);
      expect(rig.device.screenOn.last, isFalse);
      expect(_highPower(rig), isFalse);
    });

    liveTest('no reconnection against the operator', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 2));
      rig.server.operatorStops('st-1');
      rig.publisher.emit(PublisherConnection.failed);
      async.elapse(const Duration(seconds: 5));
      expect(rig.state.endReason, LiveEndReason.operatorStopped);
      expect(rig.server.streamsCreated, 1);
    });

    liveTest('WebRTC never connects: retried, then failed', (async, rig) {
      rig.autoConnect = false;
      rig.controller.start(existing);
      async.elapse(const Duration(minutes: 3));
      expect(rig.state.phase, LivePhase.failed);
      expect(rig.state.failure, LiveFailure.connectionFailed);
      expect(rig.server.streamsCreated, 4);
    });

    liveTest('report not reachable (offline) → failed, clip still possible', (
      async,
      rig,
    ) {
      rig.server.reportsOffline = true;
      rig.controller.start(const LiveTarget.newReport());
      async.elapse(const Duration(seconds: 30));
      expect(rig.state.phase, LivePhase.failed);
      expect(rig.state.failure, LiveFailure.reportNotSent);
      expect(rig.state.reportClientUuid, isNotNull);
      expect(rig.state.canFallback, isTrue);
      expect(rig.server.streamsCreated, 0);
      expect(_highPower(rig), isFalse);
    });

    liveTest('weak network at the lowest quality is flagged', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(milliseconds: 100));
      rig.publisher.nextSample = const LiveNetworkSample(
        availableOutgoingBitrate: 60000,
        fractionLost: 0.2,
      );
      async.elapse(const Duration(seconds: 20));
      expect(rig.state.quality, LiveQuality.low);
      expect(rig.publisher.qualities.last, LiveQuality.low);
      async.elapse(const Duration(seconds: 40));
      expect(rig.state.quality, LiveQuality.minimal);
      expect(rig.state.weakNetwork, isTrue);
      // The stream is not stopped by itself: the user decides.
      expect(rig.state.phase, LivePhase.live);
    });
  });

  group('refusals', () {
    liveTest('no position for a new report', (async, rig) {
      rig.location.point = null;
      rig.controller.start(const LiveTarget.newReport());
      async.elapse(const Duration(seconds: 10));
      expect(rig.state.failure, LiveFailure.noLocation);
      expect(rig.state.canFallback, isFalse);
      expect(rig.server.reportsCreated, 0);
    });

    liveTest('camera or microphone refused', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 1));
      expect(rig.state.failure, LiveFailure.permissionDenied);
      expect(rig.server.streamsCreated, 0);
      expect(rig.device.screenOn.last, isFalse);
      expect(_highPower(rig), isFalse);
    }, setUp: (rig) => rig.mediaError = const MediaPermissionDenied());

    liveTest('409 stream_already_active', (async, rig) {
      rig.server.startErrors.add(
        const FakeResponse(409, json: {'detail': 'stream_already_active'}),
      );
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 1));
      expect(rig.state.failure, LiveFailure.alreadyActive);
      expect(rig.state.apiError, ApiErrorCode.streamAlreadyActive);
      expect(rig.server.whipPosts, isEmpty);
    });

    liveTest('429 rate limited', (async, rig) {
      rig.server.startErrors.add(
        const FakeResponse(429, json: {'detail': 'rate_limited'}),
      );
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 1));
      expect(rig.state.failure, LiveFailure.rateLimited);
    });

    liveTest('not available from the locked alert view', (async, rig) {
      rig.controller.start(existing);
      async.elapse(const Duration(seconds: 1));
      expect(rig.state.failure, LiveFailure.locked);
      expect(rig.publishers, isEmpty);
      expect(rig.server.streamsCreated, 0);
    }, locked: true);
  });

  test(
    'the clip fallback is attached to the report and marked urgent',
    () async {
      final tmp = await Directory.systemTemp.createTemp('live_clip');
      final rig = LiveRig(
        clock: () => _t0,
        mediaDir: Directory('${tmp.path}/media'),
        timings: const LiveTimings(reportWait: Duration.zero),
      );
      addTearDown(() async {
        await rig.dispose();
        await tmp.delete(recursive: true);
      });
      rig.server.reportsOffline = true;
      await rig.controller.start(const LiveTarget.newReport());
      expect(rig.state.failure, LiveFailure.reportNotSent);

      final clip = File('${tmp.path}/clip.mp4')
        ..writeAsBytesSync(List.filled(64, 7));
      final uuid = await rig.controller.attachClip(
        clip.path,
        mime: 'video/mp4',
      );
      expect(uuid, rig.state.reportClientUuid);
      final media = await rig.db.mediaForReport(uuid);
      expect(media, hasLength(1));
      expect(media.single.kind, 'video');
      expect(media.single.mime, 'video/mp4');
      expect(media.single.state, MediaState.pending);
      expect(rig.container.read(urgentMediaReportsProvider), contains(uuid));
    },
  );
}
