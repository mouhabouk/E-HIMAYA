import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/features/live/live_policies.dart';
import 'package:flutter_test/flutter_test.dart';

const bad = LiveNetworkSample(
  availableOutgoingBitrate: 100000,
  fractionLost: 0.15,
);
const great = LiveNetworkSample(
  availableOutgoingBitrate: 5000000,
  fractionLost: 0,
  roundTripTime: Duration(milliseconds: 60),
);

void main() {
  group('LiveQuality', () {
    test('720p at most, lower tiers scale down and slow down', () {
      expect(LiveQuality.captureHeight, 720);
      expect(LiveQuality.high.scaleDown, 1);
      for (final q in LiveQuality.values.skip(1)) {
        final up = q.higher!;
        expect(q.maxBitrate, lessThan(up.maxBitrate));
        expect(q.scaleDown, greaterThan(up.scaleDown));
        expect(q.maxFramerate, lessThanOrEqualTo(up.maxFramerate));
      }
      // 3G-friendly floor.
      expect(LiveQuality.minimal.maxBitrate, lessThanOrEqualTo(200000));
    });

    test(
      'initial tier: Wi-Fi high, mobile data medium, battery saver capped',
      () {
        expect(
          LiveQuality.initial(
            network: NetworkKind.unmetered,
            batterySaver: false,
          ),
          LiveQuality.high,
        );
        expect(
          LiveQuality.initial(
            network: NetworkKind.metered,
            batterySaver: false,
          ),
          LiveQuality.medium,
        );
        expect(
          LiveQuality.initial(
            network: NetworkKind.unmetered,
            batterySaver: true,
          ),
          LiveQuality.medium,
        );
      },
    );
  });

  group('AdaptiveBitratePolicy', () {
    test('steps down after consecutive bad samples, not after one', () {
      final p = AdaptiveBitratePolicy(initial: LiveQuality.high);
      expect(p.next(bad).quality, LiveQuality.high);
      expect(p.next(bad).quality, LiveQuality.medium);
      expect(p.next(great).quality, LiveQuality.medium);
    });

    test('a single good sample in between resets the count', () {
      final p = AdaptiveBitratePolicy(initial: LiveQuality.high);
      p.next(bad);
      p.next(const LiveNetworkSample(availableOutgoingBitrate: 3000000));
      expect(p.next(bad).quality, LiveQuality.high);
    });

    test('steps up slowly when the link is clearly good', () {
      final p = AdaptiveBitratePolicy(initial: LiveQuality.low);
      for (var i = 0; i < 3; i++) {
        expect(p.next(great).quality, LiveQuality.low);
      }
      expect(p.next(great).quality, LiveQuality.medium);
    });

    test('never above the ceiling (battery saver)', () {
      final p = AdaptiveBitratePolicy(
        initial: LiveQuality.medium,
        ceiling: LiveQuality.medium,
      );
      for (var i = 0; i < 20; i++) {
        expect(p.next(great).quality, LiveQuality.medium);
      }
      p.ceiling = LiveQuality.low;
      expect(p.next(great).quality, LiveQuality.low);
    });

    test('weak network only once the lowest tier keeps failing', () {
      final p = AdaptiveBitratePolicy(initial: LiveQuality.minimal);
      expect(p.next(bad).weakNetwork, isFalse);
      expect(p.next(bad).weakNetwork, isFalse);
      expect(p.next(bad).weakNetwork, isFalse);
      final d = p.next(bad);
      expect(d.weakNetwork, isTrue);
      expect(d.quality, LiveQuality.minimal);
      expect(p.next(great).weakNetwork, isFalse);
    });

    test('high RTT alone is bad', () {
      final p = AdaptiveBitratePolicy(initial: LiveQuality.medium);
      const slow = LiveNetworkSample(roundTripTime: Duration(seconds: 2));
      p.next(slow);
      expect(p.next(slow).quality, LiveQuality.low);
    });
  });

  group('LiveLocationThrottle', () {
    final t0 = DateTime.utc(2026, 10, 19, 10);

    test('one send per interval, one at a time', () {
      final t = LiveLocationThrottle(const Duration(seconds: 10));
      expect(t.shouldSend(t0), isTrue);
      t.begin(t0);
      expect(t.shouldSend(t0.add(const Duration(seconds: 20))), isFalse);
      t.end();
      expect(t.shouldSend(t0.add(const Duration(seconds: 9))), isFalse);
      expect(t.shouldSend(t0.add(const Duration(seconds: 10))), isTrue);
    });

    test('never faster than the 3 s the server accepts', () {
      final t = LiveLocationThrottle(const Duration(seconds: 1));
      expect(t.interval, const Duration(seconds: 3));
      t
        ..begin(t0)
        ..end();
      expect(t.shouldSend(t0.add(const Duration(seconds: 2))), isFalse);
      expect(t.shouldSend(t0.add(const Duration(seconds: 3))), isTrue);
      t.reset();
      expect(t.shouldSend(t0), isTrue);
    });
  });

  test('LiveReconnectPolicy: growing delays, then gives up', () {
    const p = LiveReconnectPolicy();
    expect(p.delayFor(1), const Duration(seconds: 2));
    expect(p.delayFor(2), const Duration(seconds: 4));
    expect(p.delayFor(3), const Duration(seconds: 8));
    expect(p.delayFor(4), isNull);
    expect(p.delayFor(0), isNull);
    expect(
      const LiveReconnectPolicy(maxAttempts: 6).delayFor(6),
      const Duration(seconds: 10),
    );
  });
}
