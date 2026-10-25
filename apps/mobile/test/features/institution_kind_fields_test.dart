import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/features/institution/kind_fields.dart';
import 'package:ehimaya/features/institution/org_text.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final en = lookupAppLocalizations(const Locale('en'));

  test('every kind has a label, a look and its fields in three languages', () {
    for (final lang in ['ar', 'fr', 'en']) {
      final l10n = lookupAppLocalizations(Locale(lang));
      final labels = {
        for (final k in OrgKind.values) orgKindText(l10n, k.wire),
      };
      expect(labels, hasLength(12), reason: lang);
      for (final specs in kindFields.values) {
        for (final f in specs) {
          expect(
            kindFieldText(l10n, f.key),
            isNot(f.key),
            reason: '$lang ${f.key}',
          );
        }
      }
    }
    expect(kindFields.keys.toSet(), {for (final k in OrgKind.values) k.wire});
    expect(orgKindText(en, 'unknown_kind'), 'Other');
  });

  test('form answers become the API body; bad numbers are caught', () {
    final beds = kindFields['health']!.firstWhere((f) => f.key == 'beds');
    expect(kindFieldError(en, beds, '120'), isNull);
    expect(kindFieldError(en, beds, 'many'), en.orgInvalidNumber);
    expect(kindFieldError(en, beds, '20000'), en.orgInvalidNumber);
    expect(kindFieldError(en, beds, ''), isNull);
    expect(
      kindFieldsToJson('health', {
        'beds': '120',
        'generator': true,
        'helipad': false,
        'icu': null,
        'rooms': '3',
        'reception_phone': ' ',
      }),
      {'beds': 120, 'generator': true, 'helipad': false},
    );
  });

  test('the visibility of each field follows the server', () {
    final health = {for (final f in kindFields['health']!) f.key: f.visibility};
    expect(health['reception_phone'], FieldVisibility.public);
    expect(health['beds'], FieldVisibility.orgOffice);
    expect(health['non_ambulatory'], FieldVisibility.incident);
  });
}
