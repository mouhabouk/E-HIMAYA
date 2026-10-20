import 'package:ehimaya/core/http/rewards_models.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/rewards/rewards_providers.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/rewards_fixtures.dart';

void main() {
  group('RewardsSummary', () {
    test('reads the documented fields', () {
      final s = RewardsSummary.fromJson(
        rewardsJson(paused: true, pendingPoints: 40, historyNextCursor: 'c2'),
      );
      expect(s.balance, 320);
      expect(s.paused, isTrue);
      expect(s.pendingPoints, 40);
      expect(s.dailyCap, 200);
      expect(s.currentBadge, BadgeLevel.bronze);
      expect(s.nextBadge!.level, BadgeLevel.silver);
      expect(s.nextBadge!.missingPoints, 180);
      expect(s.progress, closeTo(320 / 500, 1e-9));
      expect(s.history, hasLength(3));
      expect(s.history.first.reason, PointsReason.accurateCategory);
      expect(s.history.first.multiplier, 1.5);
      expect(s.history.last.capped, isTrue);
      expect(s.historyNextCursor, 'c2');
      expect(s.certificates.single.distinction, 'vigilant_citizen');
      expect(s.certificates.single.year, 2026);
    });

    test('points of one report add all its rows', () {
      final s = RewardsSummary.fromJson(rewardsJson());
      expect(s.pointsForReport(trackingCode: 'EH-26-11-0000042'), 75);
      expect(s.pointsForReport(reportId: 'r1'), 75);
      expect(s.pointsForReport(trackingCode: 'EH-26-11-0000999'), isNull);
    });

    test('tolerates unknown values and missing fields', () {
      final s = RewardsSummary.fromJson({
        'balance': 10,
        'badges': [
          {'level': 'platinum'},
          {'level': 'silver'},
        ],
        'history': [
          {'id': 1, 'delta': 10, 'reason': 'future_reason'},
          'garbage',
        ],
        'certificates': [
          {'code': 'no-id'},
        ],
      });
      expect(s.badges.single.level, BadgeLevel.silver);
      // No current_badge field: the highest confirmed badge.
      expect(s.currentBadge, BadgeLevel.silver);
      expect(s.history.single.reason, isNull);
      expect(s.certificates, isEmpty);
      expect(s.nextBadge, isNull);
      expect(s.progress, isNull);
      expect(s.paused, isFalse);
      expect(s.anonymous, isFalse);
    });
  });

  group('RewardsCache', () {
    test('keeps the copy for its owner only, with its date', () async {
      final store = MemorySecureStore();
      final cache = RewardsCache(store);
      final at = DateTime.utc(2026, 10, 19, 8, 30);
      await cache.write(
        'sub:alice',
        RewardsSummary.fromJson(rewardsJson(balance: 77)),
        at,
      );
      final copy = await cache.read('sub:alice');
      expect(copy!.summary.balance, 77);
      expect(copy.savedAt, at);
      expect(await cache.read('sub:bob'), isNull);
    });

    test('a corrupted copy is ignored', () async {
      final store = MemorySecureStore({SecureStoreKeys.rewardsCache: '{oops'});
      expect(await RewardsCache(store).read('sub:alice'), isNull);
    });
  });
}
