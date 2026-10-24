import 'package:flutter/material.dart';

/// Design tokens of the e-Himaya design system (docs/design-system.md §2): vivid fills, a cool grey
/// page with white cards, one category colour map shared with the portal and the dashboard.
/// Contrast of every pair is checked in the design document (WCAG 2.2 AA).
abstract final class Hue {
  static const navy = Color(0xFF1F3FA0);
  static const red = Color(0xFFD7141A);
  static const orange = Color(0xFFF08C00);
  static const orangeStrong = Color(0xFFC25E00);
  static const green = Color(0xFF188038);
  static const purple = Color(0xFF7838A0);
  static const teal = Color(0xFF00806A);
  static const amber = Color(0xFFF5B400);
  static const pink = Color(0xFFC2185B);
  static const slate = Color(0xFF5B6478);
  static const sky = Color(0xFF1976D2);
}

/// Neutral surfaces and text, light and dark.
@immutable
class Neutrals {
  const Neutrals._({
    required this.ink,
    required this.muted,
    required this.page,
    required this.card,
    required this.line,
  });

  final Color ink;
  final Color muted;
  final Color page;
  final Color card;
  final Color line;

  static const light = Neutrals._(
    ink: Color(0xFF182038),
    muted: Color(0xFF5B6478),
    page: Color(0xFFF3F5FA),
    card: Color(0xFFFFFFFF),
    line: Color(0xFFE3E7EF),
  );

  static const dark = Neutrals._(
    ink: Color(0xFFE8ECF5),
    muted: Color(0xFFA6AFC4),
    page: Color(0xFF0E1426),
    card: Color(0xFF161E35),
    line: Color(0xFF26304D),
  );

  static Neutrals of(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? dark : light;
}

/// Category colours (design §2.3): an item keeps the same colour in the three apps. Never the only
/// sign of meaning: every tile has its label, every pill its word.
enum Tone { red, navy, purple, green, amber, teal, slate, pink, sky, orange }

/// Fill, glyph on the fill, soft tint and the text on that tint, per brightness.
@immutable
class ToneColors {
  const ToneColors(this.fill, this.onFill, this.tint, this.onTint);

  final Color fill;
  final Color onFill;
  final Color tint;
  final Color onTint;
}

const _ink = Color(0xFF182038);
const _deep = Color(0xFF0E1426);

const _lightTones = {
  Tone.red: ToneColors(
    Hue.red,
    Colors.white,
    Color(0xFFFDE8E8),
    Color(0xFFB3121A),
  ),
  Tone.navy: ToneColors(Hue.navy, Colors.white, Color(0xFFE8EDFA), Hue.navy),
  Tone.purple: ToneColors(
    Hue.purple,
    Colors.white,
    Color(0xFFF2EAF8),
    Color(0xFF5E2A80),
  ),
  Tone.green: ToneColors(
    Hue.green,
    Colors.white,
    Color(0xFFE6F4EA),
    Color(0xFF166B2E),
  ),
  Tone.amber: ToneColors(Hue.amber, _ink, Color(0xFFFFF3D6), Color(0xFF7A4B00)),
  Tone.teal: ToneColors(
    Hue.teal,
    Colors.white,
    Color(0xFFE0F3EF),
    Color(0xFF00695A),
  ),
  Tone.slate: ToneColors(
    Hue.slate,
    Colors.white,
    Color(0xFFEEF0F4),
    Color(0xFF3E4657),
  ),
  Tone.pink: ToneColors(
    Hue.pink,
    Colors.white,
    Color(0xFFFCE7EF),
    Color(0xFF9C1248),
  ),
  Tone.sky: ToneColors(
    Hue.sky,
    Colors.white,
    Color(0xFFE3F0FC),
    Color(0xFF0D5AA7),
  ),
  Tone.orange: ToneColors(
    Hue.orange,
    _ink,
    Color(0xFFFFF0DC),
    Color(0xFF8A4600),
  ),
};

const _darkTones = {
  Tone.red: ToneColors(
    Color(0xFFFF6B6B),
    _deep,
    Color(0x2EFF6B6B),
    Color(0xFFFFB3B3),
  ),
  Tone.navy: ToneColors(
    Color(0xFF8FA8FF),
    _deep,
    Color(0x2E8FA8FF),
    Color(0xFFC7D3FF),
  ),
  Tone.purple: ToneColors(
    Color(0xFFC49BE6),
    _deep,
    Color(0x2EC49BE6),
    Color(0xFFE2CCF3),
  ),
  Tone.green: ToneColors(
    Color(0xFF4CC772),
    _deep,
    Color(0x2E4CC772),
    Color(0xFFA9E8BC),
  ),
  Tone.amber: ToneColors(
    Color(0xFFFFC933),
    _deep,
    Color(0x2EFFC933),
    Color(0xFFFFE08A),
  ),
  Tone.teal: ToneColors(
    Color(0xFF4DD0B8),
    _deep,
    Color(0x2E4DD0B8),
    Color(0xFFA6EADD),
  ),
  Tone.slate: ToneColors(
    Color(0xFFA6AFC4),
    _deep,
    Color(0x2EA6AFC4),
    Color(0xFFD5DAE5),
  ),
  Tone.pink: ToneColors(
    Color(0xFFF06292),
    _deep,
    Color(0x2EF06292),
    Color(0xFFF8B4CB),
  ),
  Tone.sky: ToneColors(
    Color(0xFF64B5F6),
    _deep,
    Color(0x2E64B5F6),
    Color(0xFFB5DAFA),
  ),
  Tone.orange: ToneColors(
    Color(0xFFFFA733),
    _deep,
    Color(0x2EFFA733),
    Color(0xFFFFD199),
  ),
};

extension ToneOf on Tone {
  ToneColors colors(BuildContext context) =>
      (Theme.of(context).brightness == Brightness.dark
      ? _darkTones
      : _lightTones)[this]!;
}

/// Radii and spacing (design §2.5).
abstract final class Radii {
  static const card = 16.0;
  static const button = 14.0;
  static const tile = 12.0;
}

/// Bundled font (SIL OFL 1.1), Arabic and Latin in one family.
const appFontFamily = 'IBMPlexSansArabic';
