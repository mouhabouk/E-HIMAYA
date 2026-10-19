import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

Map<String, Object?> _load(String lang) =>
    jsonDecode(File('lib/l10n/app_$lang.arb').readAsStringSync())
        as Map<String, Object?>;

Set<String> _messageKeys(Map<String, Object?> arb) =>
    arb.keys.where((k) => !k.startsWith('@')).toSet();

final _placeholder = RegExp(r'\{(\w+)[,}]');

void main() {
  final en = _load('en');
  final langs = {'ar': _load('ar'), 'fr': _load('fr'), 'en': en};

  test('every key exists in ar, fr and en', () {
    final reference = _messageKeys(en);
    for (final entry in langs.entries) {
      final keys = _messageKeys(entry.value);
      expect(
        reference.difference(keys),
        isEmpty,
        reason: 'missing in ${entry.key}',
      );
      expect(
        keys.difference(reference),
        isEmpty,
        reason: 'extra in ${entry.key}',
      );
    }
  });

  test('no empty translation', () {
    for (final entry in langs.entries) {
      for (final key in _messageKeys(entry.value)) {
        expect(
          (entry.value[key]! as String).trim(),
          isNotEmpty,
          reason: '${entry.key}.$key',
        );
      }
    }
  });

  test('placeholders declared in the template are used in every language', () {
    for (final key in _messageKeys(en)) {
      final meta = en['@$key'] as Map<String, Object?>?;
      final placeholders =
          (meta?['placeholders'] as Map<String, Object?>?)?.keys.toSet() ??
          const <String>{};
      for (final entry in langs.entries) {
        final used = _placeholder
            .allMatches(entry.value[key]! as String)
            .map((m) => m.group(1)!)
            .toSet();
        expect(used, containsAll(placeholders), reason: '${entry.key}.$key');
      }
    }
  });

  test('locales are declared', () {
    expect(langs['ar']!['@@locale'], 'ar');
    expect(langs['fr']!['@@locale'], 'fr');
    expect(langs['en']!['@@locale'], 'en');
  });

  test('the charter cites Organic Law 2004-63 in every language', () {
    for (final entry in langs.entries) {
      expect(entry.value['charterLawBody'] as String, contains('2004'));
      expect(entry.value['charterLawBody'] as String, contains('63'));
    }
  });
}
