import 'package:flutter/material.dart';

import 'tokens.dart';

/// Brand colours of the app (docs/design-system.md §2.0, Yamen 2026-11-08): white stays the base
/// colour; royal blue (default) or royal red fills the frame around the screen ([BrandFrame]) and
/// gives the primary colour. The category colours of [Tone] and the SOS red never change.
enum AppPalette {
  blue,
  red;

  /// The stored choice. Older values of phase A: `red` stays red; `office`, `blue` and `green`
  /// become royal blue.
  static AppPalette fromStored(String? value) =>
      value == 'red' ? AppPalette.red : AppPalette.blue;
}

/// Colours of the Office's logo, as the design system's vivid hues.
abstract final class BrandColors {
  static const blue = Hue.navy;
  static const orange = Hue.orange;
  static const green = Hue.green;
  static const red = Hue.red;

  static const royalBlue = Hue.navy;
  static const royalRed = Color(0xFF9B1B2C);
  static const gold = Color(0xFFC9A24A);
}

/// Colour of the frame around the screen: the royal colour, or its night shade in the dark mode.
Color brandFrameColor(AppPalette palette, Brightness brightness) {
  final dark = brightness == Brightness.dark;
  return switch (palette) {
    AppPalette.blue => dark ? const Color(0xFF0B1A3F) : BrandColors.royalBlue,
    AppPalette.red => dark ? const Color(0xFF3A0910) : BrandColors.royalRed,
  };
}

/// The SOS colour stays the same red in every palette and brightness, white label (5.2:1).
const sosRed = Hue.red;

Color _primary(AppPalette palette, Brightness brightness) {
  final dark = brightness == Brightness.dark;
  return switch (palette) {
    AppPalette.blue => dark ? const Color(0xFF8FA8FF) : BrandColors.royalBlue,
    AppPalette.red => dark ? const Color(0xFFFF8A95) : BrandColors.royalRed,
  };
}

ColorScheme _scheme(AppPalette palette, Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final n = dark ? Neutrals.dark : Neutrals.light;
  final primary = _primary(palette, brightness);
  final onPrimary = dark ? const Color(0xFF0E1426) : Colors.white;
  final seeded = ColorScheme.fromSeed(
    seedColor: primary,
    brightness: brightness,
  );
  return seeded.copyWith(
    primary: primary,
    onPrimary: onPrimary,
    secondary: dark ? const Color(0xFFFFA733) : Hue.orangeStrong,
    onSecondary: dark ? const Color(0xFF0E1426) : Colors.white,
    tertiary: dark ? const Color(0xFF4CC772) : Hue.green,
    onTertiary: dark ? const Color(0xFF0E1426) : Colors.white,
    error: dark ? const Color(0xFFFF6B6B) : Hue.red,
    onError: dark ? const Color(0xFF0E1426) : Colors.white,
    surface: n.card,
    onSurface: n.ink,
    onSurfaceVariant: n.muted,
    surfaceContainerLowest: n.card,
    surfaceContainerLow: n.card,
    surfaceContainer: n.page,
    surfaceContainerHigh: dark
        ? const Color(0xFF1C2541)
        : const Color(0xFFEDF0F6),
    surfaceContainerHighest: dark
        ? const Color(0xFF222C4A)
        : const Color(0xFFE8ECF3),
    outline: dark ? const Color(0xFF6B7591) : const Color(0xFF8A93A6),
    outlineVariant: n.line,
  );
}

ThemeData buildTheme(
  Brightness brightness, [
  AppPalette palette = AppPalette.blue,
]) {
  final scheme = _scheme(palette, brightness);
  final n = brightness == Brightness.dark ? Neutrals.dark : Neutrals.light;
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    brightness: brightness,
    fontFamily: appFontFamily,
  );
  final text = base.textTheme.apply(bodyColor: n.ink, displayColor: n.ink);
  RoundedRectangleBorder rounded(double r) =>
      RoundedRectangleBorder(borderRadius: BorderRadius.circular(r));
  const buttonText = TextStyle(
    fontFamily: appFontFamily,
    fontSize: 16,
    fontWeight: FontWeight.w700,
  );
  return base.copyWith(
    scaffoldBackgroundColor: n.page,
    textTheme: text.copyWith(
      headlineSmall: text.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
      titleLarge: text.titleLarge?.copyWith(
        fontSize: 22,
        fontWeight: FontWeight.w700,
      ),
      titleMedium: text.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      titleSmall: text.titleSmall?.copyWith(fontWeight: FontWeight.w700),
      bodySmall: text.bodySmall?.copyWith(color: n.muted),
      labelLarge: text.labelLarge?.copyWith(fontWeight: FontWeight.w600),
    ),
    // Minimum 48x48 dp touch targets everywhere (WCAG 2.2 target size, Material guidance).
    materialTapTargetSize: MaterialTapTargetSize.padded,
    visualDensity: VisualDensity.standard,
    appBarTheme: AppBarTheme(
      backgroundColor: n.card,
      foregroundColor: n.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 1,
      shadowColor: n.line,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: appFontFamily,
        fontSize: 22,
        fontWeight: FontWeight.w700,
        color: n.ink,
      ),
      shape: Border(bottom: BorderSide(color: n.line)),
    ),
    cardTheme: CardThemeData(
      color: n.card,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Radii.card),
        side: BorderSide(color: n.line),
      ),
    ),
    dividerTheme: DividerThemeData(color: n.line, space: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: n.card,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.tile),
        borderSide: BorderSide(color: scheme.outline),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.tile),
        borderSide: BorderSide(color: scheme.outline),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.tile),
        borderSide: BorderSide(color: scheme.primary, width: 2),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 52),
        shape: rounded(Radii.button),
        textStyle: buttonText,
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        minimumSize: const Size(64, 52),
        shape: rounded(Radii.button),
        textStyle: buttonText,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 52),
        shape: rounded(Radii.button),
        side: BorderSide(color: scheme.outline),
        textStyle: buttonText,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 48),
        textStyle: buttonText.copyWith(fontSize: 15),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        backgroundColor: scheme.surfaceContainerHighest,
        selectedBackgroundColor: n.card,
        selectedForegroundColor: scheme.primary,
        foregroundColor: n.muted,
        side: BorderSide.none,
        textStyle: buttonText.copyWith(fontSize: 15),
        shape: const StadiumBorder(),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      shape: const StadiumBorder(),
      side: BorderSide(color: n.line),
      labelStyle: TextStyle(
        fontFamily: appFontFamily,
        fontWeight: FontWeight.w600,
        color: n.ink,
      ),
    ),
    listTileTheme: ListTileThemeData(
      minVerticalPadding: 12,
      titleTextStyle: TextStyle(
        fontFamily: appFontFamily,
        fontSize: 16,
        fontWeight: FontWeight.w700,
        color: n.ink,
      ),
      subtitleTextStyle: TextStyle(
        fontFamily: appFontFamily,
        fontSize: 13,
        fontWeight: FontWeight.w500,
        color: n.muted,
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: n.card,
      surfaceTintColor: Colors.transparent,
      indicatorColor: scheme.primary.withValues(alpha: 0.12),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: n.card,
      surfaceTintColor: Colors.transparent,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: n.card,
      surfaceTintColor: Colors.transparent,
      shape: rounded(20),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: rounded(Radii.tile),
    ),
  );
}
