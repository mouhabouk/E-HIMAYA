import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/app_prefs.dart';

/// Languages of the app: Arabic (default, RTL), French and English.
const supportedLanguageCodes = ['ar', 'fr', 'en'];

class AppSettings {
  const AppSettings({required this.locale, required this.themeMode});

  final Locale locale;
  final ThemeMode themeMode;

  AppSettings copyWith({Locale? locale, ThemeMode? themeMode}) => AppSettings(
    locale: locale ?? this.locale,
    themeMode: themeMode ?? this.themeMode,
  );
}

/// Language and theme, persisted in [AppPrefs].
class SettingsController extends Notifier<AppSettings> {
  @override
  AppSettings build() {
    final prefs = ref.watch(appPrefsProvider);
    final code = prefs.localeCode;
    return AppSettings(
      locale: Locale(supportedLanguageCodes.contains(code) ? code! : 'ar'),
      themeMode:
          ThemeMode.values.asNameMap()[prefs.themeMode] ?? ThemeMode.system,
    );
  }

  Future<void> setLanguage(String code) async {
    if (!supportedLanguageCodes.contains(code)) return;
    await ref.read(appPrefsProvider).setLocaleCode(code);
    state = state.copyWith(locale: Locale(code));
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    await ref.read(appPrefsProvider).setThemeMode(mode.name);
    state = state.copyWith(themeMode: mode);
  }
}

final settingsProvider = NotifierProvider<SettingsController, AppSettings>(
  SettingsController.new,
);

/// Current UI language code (`ar` | `fr` | `en`): also the language of report text (FR-A-040).
final localeCodeProvider = Provider<String>(
  (ref) => ref.watch(settingsProvider).locale.languageCode,
);
