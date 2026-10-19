import 'package:ehimaya/core/ui/directional_icons.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('directional icons used by the app mirror in RTL', () {
    for (final icon in [
      Icons.chevron_right,
      Icons.send,
      Icons.arrow_back,
      DirectionalIcons.login,
      DirectionalIcons.logout,
    ]) {
      expect(icon.matchTextDirection, isTrue, reason: '$icon');
    }
    expect(DirectionalIcons.login.codePoint, Icons.login.codePoint);
    expect(DirectionalIcons.logout.codePoint, Icons.logout.codePoint);
  });
}
