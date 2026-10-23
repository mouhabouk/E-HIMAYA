import 'package:flutter/material.dart';

/// Colour palettes of the app (phase A, addition 1). [office] is the default: the colours of the
/// Civil Protection logo, darkened to reach WCAG AA contrast on light surfaces.
enum AppPalette { office, red, blue, green }

/// Colours of the Office's logo.
abstract final class BrandColors {
  static const blue = Color(0xFF1F3D99);
  static const orange = Color(0xFFE07B00);
  static const green = Color(0xFF1B7F2A);
  static const red = Color(0xFFC62828);
}

/// The SOS colour stays the same red in every palette and brightness, white label (5.9:1).
const sosRed = Color(0xFFC62828);

ColorScheme _scheme(AppPalette palette, Brightness brightness) =>
    switch (palette) {
      AppPalette.office => ColorScheme.fromSeed(
        seedColor: BrandColors.blue,
        brightness: brightness,
        secondary: brightness == Brightness.light
            ? const Color(0xFF8A4B00)
            : const Color(0xFFFFB86B),
        tertiary: brightness == Brightness.light
            ? BrandColors.green
            : const Color(0xFF8BD88F),
      ),
      AppPalette.red => ColorScheme.fromSeed(
        seedColor: const Color(0xFFB3261E),
        brightness: brightness,
      ),
      AppPalette.blue => ColorScheme.fromSeed(
        seedColor: const Color(0xFF1565C0),
        brightness: brightness,
      ),
      AppPalette.green => ColorScheme.fromSeed(
        seedColor: const Color(0xFF2E7D32),
        brightness: brightness,
      ),
    };

ThemeData buildTheme(
  Brightness brightness, [
  AppPalette palette = AppPalette.office,
]) {
  // Material 3 tonal palettes keep body text at WCAG AA in both brightnesses.
  final scheme = _scheme(palette, brightness);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    brightness: brightness,
    // Minimum 48x48 dp touch targets everywhere (WCAG 2.2 target size, Material guidance).
    materialTapTargetSize: MaterialTapTargetSize.padded,
    visualDensity: VisualDensity.standard,
    inputDecorationTheme: const InputDecorationTheme(
      border: OutlineInputBorder(),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: const Size(64, 52)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(minimumSize: const Size(64, 52)),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(minimumSize: const Size(48, 48)),
    ),
    listTileTheme: const ListTileThemeData(minVerticalPadding: 12),
  );
}
