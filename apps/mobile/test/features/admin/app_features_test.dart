import 'package:ehimaya/features/admin/app_features.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('phase 5: the windows the administrator closed, and their message', () {
    final f = AppFeatures.fromJson({
      'hidden': ['citizen_guide', 'citizen_reports.video'],
      'announcement': {'tone': 'warn', 'ar': 'صيانة', 'fr': '', 'en': 'Upkeep'},
    });
    expect(f.shows('citizen_guide'), isFalse);
    expect(f.shows('citizen_reports.video'), isFalse);
    expect(f.shows('citizen_reports.send'), isTrue);
    expect(f.shows('citizen_volunteer'), isTrue);
    expect(f.warn, isTrue);
    expect(f.messageIn('en'), 'Upkeep');
    expect(f.messageIn('fr'), 'صيانة');
    // Nothing closed and no message when the server says nothing.
    const none = AppFeatures();
    expect(none.shows('citizen_guide'), isTrue);
    expect(none.messageIn('ar'), isNull);
    expect(
      AppFeatures.fromJson({'hidden': [], 'announcement': null}).text,
      isNull,
    );
  });
}
