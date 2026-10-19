import 'package:flutter/material.dart';

/// Civil-protection orange/red seed. Contrast of text on surfaces is handled by Material 3
/// tonal palettes (WCAG AA for body text in both brightnesses).
const _seed = Color(0xFFB3261E);

/// The SOS colour stays the same red in light and dark themes, white label (contrast 5.9:1).
const sosRed = Color(0xFFC62828);

ThemeData buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: _seed, brightness: brightness);
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
