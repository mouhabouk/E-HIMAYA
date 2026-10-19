import 'package:flutter/widgets.dart';

/// Material icons that point in a reading direction but are not flagged
/// `matchTextDirection` by Flutter: mirrored here so they flip in Arabic (RTL).
/// (chevron_right, send, arrow_back… already flip on their own.)
abstract final class DirectionalIcons {
  static const login = IconData(
    0xe3b2,
    fontFamily: 'MaterialIcons',
    matchTextDirection: true,
  );
  static const logout = IconData(
    0xe3b3,
    fontFamily: 'MaterialIcons',
    matchTextDirection: true,
  );
}
