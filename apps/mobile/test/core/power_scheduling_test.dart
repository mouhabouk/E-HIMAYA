import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('BatterySaverPolicy', () {
    const policy = BatterySaverPolicy();
    BatteryReading at(int level, {bool charging = false, bool save = false}) =>
        BatteryReading(level: level, charging: charging, systemPowerSave: save);

    test('on/off override the battery', () {
      expect(
        policy.isActive(
          mode: BatterySaverMode.on,
          reading: at(100, charging: true),
          wasActive: false,
        ),
        isTrue,
      );
      expect(
        policy.isActive(
          mode: BatterySaverMode.off,
          reading: at(3),
          wasActive: true,
        ),
        isFalse,
      );
    });

    test('auto: enters at 20 %, leaves only at 30 % (hysteresis)', () {
      bool auto(int level, bool was) => policy.isActive(
        mode: BatterySaverMode.auto,
        reading: at(level),
        wasActive: was,
      );
      expect(auto(21, false), isFalse);
      expect(auto(20, false), isTrue);
      expect(auto(25, true), isTrue, reason: 'no flapping above 20 %');
      expect(auto(25, false), isFalse);
      expect(auto(30, true), isFalse);
    });

    test('auto: charging turns it off, the system saver turns it on', () {
      expect(
        policy.isActive(
          mode: BatterySaverMode.auto,
          reading: at(5, charging: true),
          wasActive: true,
        ),
        isFalse,
      );
      expect(
        policy.isActive(
          mode: BatterySaverMode.auto,
          reading: at(80, save: true),
          wasActive: false,
        ),
        isTrue,
      );
    });

    test('auto without a reading stays off', () {
      expect(
        policy.isActive(
          mode: BatterySaverMode.auto,
          reading: null,
          wasActive: true,
        ),
        isFalse,
      );
      expect(
        policy.isActive(
          mode: BatterySaverMode.auto,
          reading: const BatteryReading(level: null, charging: false),
          wasActive: false,
        ),
        isFalse,
      );
    });

    test('mode names round-trip, unknown means auto', () {
      for (final m in BatterySaverMode.values) {
        expect(BatterySaverMode.fromName(m.name), m);
      }
      expect(BatterySaverMode.fromName(null), BatterySaverMode.auto);
      expect(BatterySaverMode.fromName('bogus'), BatterySaverMode.auto);
    });
  });

  group('PollSchedule (exponential back-off)', () {
    test(
      'alerts with push: 15 min, 30 min in saver, failures double to 30',
      () {
        const s = AlertPolling.withPush;
        expect(
          s.next(failures: 0, batterySaver: false),
          const Duration(minutes: 15),
        );
        expect(
          s.next(failures: 0, batterySaver: true),
          const Duration(minutes: 30),
        );
        expect(
          s.next(failures: 1, batterySaver: false),
          const Duration(minutes: 30),
        );
        expect(
          s.next(failures: 9, batterySaver: false),
          const Duration(minutes: 30),
        );
      },
    );

    test('alerts without push stay frequent: 5 min, 10 in saver, cap 15', () {
      final s = AlertPolling.of(pushAvailable: false);
      expect(
        s.next(failures: 0, batterySaver: false),
        const Duration(minutes: 5),
      );
      expect(
        s.next(failures: 0, batterySaver: true),
        const Duration(minutes: 10),
      );
      expect(
        s.next(failures: 1, batterySaver: false),
        const Duration(minutes: 10),
      );
      expect(
        s.next(failures: 2, batterySaver: false),
        const Duration(minutes: 15),
      );
      expect(
        s.next(failures: 40, batterySaver: true),
        const Duration(minutes: 15),
      );
    });

    test('the base period is never cut by a smaller cap', () {
      const s = PollSchedule(
        normal: Duration(minutes: 10),
        saver: Duration(minutes: 20),
        maxBackoff: Duration(minutes: 5),
      );
      expect(
        s.next(failures: 3, batterySaver: true),
        const Duration(minutes: 20),
      );
    });
  });

  test('AdaptiveInterval grows while idle, snaps back on activity', () {
    final i = AdaptiveInterval(
      min: const Duration(seconds: 45),
      max: const Duration(minutes: 10),
    );
    expect(i.current, const Duration(seconds: 45));
    expect(i.idle(), const Duration(seconds: 90));
    expect(i.idle(), const Duration(seconds: 180));
    expect(i.idle(), const Duration(seconds: 360));
    expect(i.idle(), const Duration(minutes: 10));
    expect(i.idle(), const Duration(minutes: 10));
    expect(i.activity(), const Duration(seconds: 45));
  });

  test('distanceMeters (haversine)', () {
    const tunis = GeoPoint(lat: 36.8065, lon: 10.1815);
    const sfax = GeoPoint(lat: 34.7406, lon: 10.7603);
    expect(distanceMeters(tunis, tunis), 0);
    expect(distanceMeters(tunis, sfax), closeTo(235000, 5000));
    // ~0.001° of latitude ≈ 111 m.
    expect(
      distanceMeters(sfax, const GeoPoint(lat: 34.7416, lon: 10.7603)),
      closeTo(111, 2),
    );
  });

  group('LocationCoalescer', () {
    const here = GeoPoint(lat: 34.7406, lon: 10.7603);
    const near = GeoPoint(lat: 34.7410, lon: 10.7603); // ~45 m
    const away = GeoPoint(lat: 34.7420, lon: 10.7603); // ~155 m
    const far = GeoPoint(lat: 34.7440, lon: 10.7603); // ~380 m
    final t0 = DateTime.utc(2026, 10, 19, 10);

    test('first fix is sent; stationary fixes are not', () {
      final c = LocationCoalescer();
      expect(c.shouldSend(here, t0), isTrue);
      c.markSent(here, t0);
      expect(c.shouldSend(near, t0.add(const Duration(minutes: 5))), isFalse);
    });

    test('a move of 100 m is sent, but never within 30 s', () {
      final c = LocationCoalescer()..markSent(here, t0);
      expect(c.shouldSend(away, t0.add(const Duration(seconds: 10))), isFalse);
      expect(c.shouldSend(away, t0.add(const Duration(seconds: 30))), isTrue);
    });

    test('heartbeat every 15 min (30 in battery saver)', () {
      final c = LocationCoalescer()..markSent(here, t0);
      final at15 = t0.add(const Duration(minutes: 15));
      expect(c.shouldSend(here, at15), isTrue);
      expect(c.shouldSend(here, at15, batterySaver: true), isFalse);
      expect(
        c.shouldSend(
          here,
          t0.add(const Duration(minutes: 30)),
          batterySaver: true,
        ),
        isTrue,
      );
    });

    test('battery saver needs 250 m', () {
      final c = LocationCoalescer()..markSent(here, t0);
      final t = t0.add(const Duration(minutes: 1));
      expect(c.shouldSend(away, t, batterySaver: true), isFalse);
      expect(c.shouldSend(far, t, batterySaver: true), isTrue);
    });

    test('reset forgets the last send', () {
      final c = LocationCoalescer()..markSent(here, t0);
      c.reset();
      expect(c.lastSent, isNull);
      expect(c.shouldSend(here, t0), isTrue);
    });
  });

  group('MediaUploadPolicy', () {
    const policy = MediaUploadPolicy();
    final queued = DateTime.utc(2026, 10, 19, 10);
    const big = 20 * 1024 * 1024;

    bool may({
      bool sos = false,
      int size = big,
      NetworkKind network = NetworkKind.metered,
      bool saver = true,
      Duration waited = const Duration(minutes: 1),
    }) => policy.mayUpload(
      sos: sos,
      sizeBytes: size,
      network: network,
      batterySaver: saver,
      queuedAt: queued,
      now: queued.add(waited),
    );

    test('never delays SOS media, nor anything outside battery saver', () {
      expect(may(sos: true), isTrue);
      expect(may(saver: false), isTrue);
    });

    test('in saver, a large file on mobile data waits for Wi-Fi', () {
      expect(may(), isFalse);
      expect(may(network: NetworkKind.none), isFalse);
      expect(may(network: NetworkKind.unmetered), isTrue);
      expect(may(size: 2 * 1024 * 1024), isTrue);
    });

    test('… but at most 30 minutes', () {
      expect(may(waited: const Duration(minutes: 29)), isFalse);
      expect(may(waited: const Duration(minutes: 30)), isTrue);
    });
  });
}
